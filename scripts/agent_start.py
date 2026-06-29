#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

# Script flow:
# 1. Inspect the target repo, changed files, kit state, backlog, and docs context.
# 2. Recommend review personas and checks that match the detected change set.
# 3. Allocate a new local run directory under .agent-workflows/runs.
# 4. Write a receipt template and human-readable brief for the review run.
#
# Function guide:
# - run/git_output/optional_git_output/repo_root/git_status collect repo facts.
# - parse_status_paths/read_json/read_text/command_summary normalize inputs.
# - extract_section/first_heading/truncate summarize local documentation.
# - latest_adr/kit_context/target_version_context/backlog_context gather governance context.
# - review_risk/classify_review_risk/should_consider_version_bump choose review scope.
# - load_persona_manifest/specialist_matches/recommend_personas choose personas.
# - ensure_runs_gitignore/build_receipt_template/allocate_run_dir create run artifacts.
# - format_check_lines/format_persona_lines/build_brief/parse_docs_impact/main produce CLI output.

VALID_MODES = {
    "bootstrap",
    "drift",
    "pull-request",
    "release-gate",
    "learning-comments",
    "test-first",
    "verification",
}

DEFAULT_REVIEW_PERSONAS = [
    "doc-code-delta",
    "ai-code-slop",
    "test-behavior-risk",
    "reuse-architecture",
]


@dataclass(frozen=True)
class RiskRule:
    id: str
    tier: str
    personas: tuple[str, ...]
    patterns: tuple[str, ...]
    reason: str


TIER_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

RISK_RULES = (
    RiskRule(
        id="auth-or-secrets",
        tier="high",
        personas=("security-privacy", "test-behavior-risk"),
        patterns=("auth", "login", "session", "permission", "secret", "token", "credential", ".env"),
        reason="auth, permission, token, credential, or secret-handling path",
    ),
    RiskRule(
        id="data-deletion-or-destructive",
        tier="critical",
        personas=("security-privacy", "api-data-contracts", "test-behavior-risk"),
        patterns=("delete", "destroy", "purge", "truncate", "wipe", "drop", "reset"),
        reason="destructive data operation path or name",
    ),
    RiskRule(
        id="migration-or-persistence",
        tier="high",
        personas=("api-data-contracts", "test-behavior-risk"),
        patterns=("migration", "migrations/", "database", "db/", "schema", "schemas/", ".sql", "model"),
        reason="migration, schema, database, or persisted data path",
    ),
    RiskRule(
        id="public-api-or-contract",
        tier="high",
        personas=("api-data-contracts", "doc-code-delta", "test-behavior-risk"),
        patterns=("api/", "openapi", "graphql", "webhook", "contract", "public", "sdk", "client"),
        reason="public API, generated client, webhook, or contract path",
    ),
    RiskRule(
        id="ci-build-release",
        tier="medium",
        personas=("dependencies-build", "runtime-observability"),
        patterns=(
            ".github/workflows",
            "ci/",
            "build",
            "release",
            "dockerfile",
            "containerfile",
            "makefile",
            "package.json",
            "pyproject.toml",
            "requirements",
        ),
        reason="CI, build, packaging, or release path",
    ),
    RiskRule(
        id="runtime-or-ops",
        tier="medium",
        personas=("runtime-observability",),
        patterns=("deploy", "infra", "terraform", "helm", "service", "scheduler", "cron", "runbook", "ops/"),
        reason="runtime, deployment, scheduling, or operations path",
    ),
    RiskRule(
        id="docs-contract",
        tier="medium",
        personas=("doc-code-delta",),
        patterns=("agents.md", "review.md", "doc-contract", "documentation-contract", "adr/", "docs/adr"),
        reason="agent instruction, docs contract, or ADR path",
    ),
    RiskRule(
        id="frontend-user-flow",
        tier="medium",
        personas=("frontend-ux", "test-behavior-risk"),
        patterns=("frontend", "components/", "pages/", "routes/", ".tsx", ".jsx", ".vue", ".svelte", ".css"),
        reason="frontend or user-flow path",
    ),
)

SPECIALIST_RULES = [
    (
        "security-privacy",
        ["auth", "secret", "token", "credential", "permission", "privacy", ".env"],
    ),
    (
        "api-data-contracts",
        ["api/", "openapi", "schema", "schemas/", "migration", "migrations/", "database", "db/", "sql"],
    ),
    (
        "dependencies-build",
        ["package.json", "package-lock.json", "pnpm-lock", "yarn.lock", "requirements", "pyproject.toml", "setup.py", "dockerfile", "makefile", ".github/workflows", "build", "ci/"],
    ),
    (
        "runtime-observability",
        ["deploy", "infra", "terraform", "helm", "service", "scheduler", "cron", "logging", "metrics", "observability", "runbook"],
    ),
    (
        "frontend-ux",
        ["frontend", "components/", "pages/", "routes/", ".tsx", ".jsx", ".vue", ".svelte", ".css"],
    ),
]


def run(cmd, cwd, check=False):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )
    except OSError as exc:
        return {
            "command": " ".join(cmd),
            "result": "blocked",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "command": " ".join(cmd),
        "result": "pass" if result.returncode == 0 else "fail",
        "exit_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def git_output(args, cwd):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def optional_git_output(args, cwd, default=""):
    try:
        return git_output(args, cwd)
    except Exception:
        return default


def repo_root():
    try:
        return Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()
    except Exception as exc:
        raise SystemExit(f"agent-start must run inside a git repository: {exc}") from exc


def parse_status_paths(status_output):
    paths = []
    for line in status_output.splitlines():
        if not line:
            continue
        value = line[3:].strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1].strip()
        if value:
            paths.append(value)
    return sorted(set(paths))


def match_risk_rules(path):
    lowered = path.lower().replace("\\", "/")
    return [rule for rule in RISK_RULES if any(pattern in lowered for pattern in rule.patterns)]


def review_risk_tier(triggers):
    if not triggers:
        return "low"
    return max((trigger["tier"] for trigger in triggers), key=lambda tier: TIER_ORDER[tier])


def review_trust_profile(tier, triggers):
    rule_ids = {trigger["rule_id"] for trigger in triggers}
    if "data-deletion-or-destructive" in rule_ids:
        return "untrusted-pr"
    if "auth-or-secrets" in rule_ids:
        return "read-only-review"
    if tier in {"high", "critical"}:
        return "read-only-review"
    return "read-only-review"


def review_risk_guidance(tier, triggers):
    guidance = [
        "Reviewers are read-only by default: no file writes, git mutations, PR mutations, account mutations, or non-allowlisted network calls.",
    ]
    if tier in {"high", "critical"}:
        guidance.append("Use specialist reviewers and require concrete file, command, docs, or runtime evidence before accepting findings.")
    if any(trigger["rule_id"] == "auth-or-secrets" for trigger in triggers):
        guidance.append("Do not expose secrets, tokens, cookies, private URLs, request bodies, or personal data in prompts or receipts.")
    if any(trigger["rule_id"] == "data-deletion-or-destructive" for trigger in triggers):
        guidance.append("Require human approval and rollback or recovery evidence before any write-capable follow-up.")
    if not triggers:
        guidance.append("No high-risk path trigger matched; keep the default small reviewer set unless the user request widens scope.")
    return guidance


def classify_review_risk(changed_files):
    triggers = []
    for path in changed_files:
        for rule in match_risk_rules(path):
            triggers.append(
                {
                    "path": path,
                    "rule_id": rule.id,
                    "tier": rule.tier,
                    "reason": rule.reason,
                    "personas": list(rule.personas),
                }
            )
    tier = review_risk_tier(triggers)
    return {
        "schema_version": 1,
        "risk_tier": tier,
        "trust_profile": review_trust_profile(tier, triggers),
        "triggers": triggers,
        "guidance": review_risk_guidance(tier, triggers),
        "policy_docs": [
            "docs/ops/agent-tool-network-allowlist.md",
            ".agent-workflows/agent-permission-policy.json",
            ".codex/prompts/policies/review-risk-classifier.md",
            ".codex/prompts/policies/read-only-reviewer-sandbox.md",
            ".codex/prompts/policies/local-private-review.md",
            ".codex/prompts/policies/browser-research-agent.md",
        ],
    }


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        return {"_error": f"Invalid JSON: {exc}"}


def read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        return None


def command_summary(command_result):
    return {
        "command": command_result["command"],
        "result": command_result["result"],
        "exit_code": command_result["exit_code"],
        "stdout": command_result["stdout"][-4000:],
        "stderr": command_result["stderr"][-4000:],
    }


def extract_section(text, heading):
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower() == f"## {heading.lower()}":
            start = index + 1
            break
    if start is None:
        return ""

    collected = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if stripped:
            collected.append(stripped)
    return " ".join(collected)


def first_heading(text, fallback):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def truncate(value, limit=600):
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def latest_adr(root):
    adr_dir = root / "docs" / "adr"
    if not adr_dir.is_dir():
        return None

    candidates = [
        path
        for path in adr_dir.glob("*.md")
        if path.name != "0000-template.md" and not path.name.startswith("0000-")
    ]
    if not candidates:
        return None

    path = sorted(candidates, key=lambda item: item.name)[-1]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "path": str(path.relative_to(root)),
            "title": path.stem,
            "status": "unreadable",
            "summary": "ADR is not valid UTF-8.",
            "constraints": "",
        }

    decision = extract_section(text, "Decision")
    consequences = extract_section(text, "Consequences")
    context = extract_section(text, "Context")
    return {
        "path": str(path.relative_to(root)),
        "title": first_heading(text, path.stem),
        "status": truncate(extract_section(text, "Status"), 120) or "unknown",
        "summary": truncate(decision or context or text),
        "constraints": truncate(consequences or decision),
    }


def kit_context(root):
    receipt = read_json(root / ".doc-contract-kit" / "install.json")
    manifest = read_json(root / ".doc-contract-kit" / "manifest.json")
    updates_dir = root / ".doc-contract-kit" / "updates"
    update_reports = []
    if updates_dir.is_dir():
        update_reports = [
            str(path.relative_to(root))
            for path in sorted(updates_dir.glob("*/update-report.md"), reverse=True)[:5]
        ]

    if not isinstance(receipt, dict):
        return {
            "status": "not-installed",
            "installed_version": None,
            "source_version": None,
            "source_ref": None,
            "prompt_snapshot": None,
            "preset": None,
            "profiles": [],
            "last_updated_at": None,
            "manifest_present": isinstance(manifest, dict),
            "managed_file_count": 0,
            "target_owned_file_count": 0,
            "recent_update_reports": update_reports,
            "update_command": "make kit-refresh KIT=/path/to/repo-contract-kit",
        }

    files = manifest.get("files", []) if isinstance(manifest, dict) else []
    prompt_snapshot = receipt.get("prompt_snapshot") or (manifest.get("prompt_snapshot") if isinstance(manifest, dict) else None)
    return {
        "status": "managed" if isinstance(manifest, dict) else "legacy-no-manifest",
        "installed_version": receipt.get("kit_version"),
        "source_version": receipt.get("source_version") or receipt.get("kit_version"),
        "source_ref": receipt.get("source_ref") or receipt.get("source_commits", {}).get("repo-contract-kit"),
        "prompt_snapshot": prompt_snapshot if isinstance(prompt_snapshot, dict) else None,
        "preset": receipt.get("preset"),
        "profiles": receipt.get("profiles", []),
        "last_updated_at": receipt.get("last_updated_at") or receipt.get("installed_at"),
        "manifest_present": isinstance(manifest, dict),
        "managed_file_count": sum(1 for item in files if isinstance(item, dict) and item.get("managed")),
        "target_owned_file_count": sum(1 for item in files if isinstance(item, dict) and item.get("owner") == "target"),
        "recent_update_reports": update_reports,
        "update_command": "make kit-refresh KIT=/path/to/repo-contract-kit",
    }


def target_version_context(root):
    value = read_text(root / "VERSION")
    return {
        "current": value,
        "version_file": "VERSION" if value is not None else None,
        "changelog_file": "CHANGELOG.md" if (root / "CHANGELOG.md").exists() else None,
        "versioning_doc": "docs/versioning.md" if (root / "docs" / "versioning.md").exists() else None,
    }


def backlog_context(root):
    path = root / "docs" / "backlog.md"
    text = read_text(path)
    open_items = []
    done_items = []
    if text:
        for line in text.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            if lowered.startswith("- [ ] "):
                open_items.append(stripped[6:].strip())
            elif lowered.startswith("- [x] "):
                done_items.append(stripped[6:].strip())

    prompt_path = ".codex/prompts/task-packet.md"
    schema_path = "schemas/task-packet.schema.json"
    return {
        "mirror_present": text is not None,
        "mirror_path": "docs/backlog.md" if text is not None else None,
        "open_items": open_items[:10],
        "open_item_count": len(open_items),
        "done_item_count": len(done_items),
        "task_packet_prompt": prompt_path if (root / prompt_path).exists() else None,
        "task_packet_schema": schema_path if (root / schema_path).exists() else None,
        "guidance": (
            "Backlog prioritisation belongs in the repository planning source or external planning tool; docs/backlog.md is the portable repo mirror. "
            "Convert one selected backlog item into a task packet before implementation."
            if text is not None
            else "No docs/backlog.md mirror found. Use the current user request, issue, or accepted finding as the task source."
        ),
    }


def should_consider_version_bump(docs_impact, changed_files):
    categories = set()
    if isinstance(docs_impact, dict):
        categories = {
            item.get("category")
            for item in docs_impact.get("categories", [])
            if isinstance(item, dict) and item.get("category")
        }
    if categories.intersection({"api", "cli", "config", "ops"}):
        return True

    behavior_patterns = (
        "src/",
        "app/",
        "lib/",
        "api/",
        "cli/",
        "config/",
        "schema/",
        "schemas/",
        "package.json",
        "pyproject.toml",
    )
    ignored_patterns = ("docs/", "README.md", "CHANGELOG.md", "VERSION", "tests/")
    for path in changed_files:
        normalized = path.replace("\\", "/")
        if normalized.startswith(ignored_patterns) or normalized in ignored_patterns:
            continue
        lowered = normalized.lower()
        if lowered.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb")):
            return True
        if any(pattern in lowered for pattern in behavior_patterns):
            return True
    return False


def load_persona_manifest(root):
    manifest_path = root / ".codex" / "prompts" / "personas" / "manifest.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        return manifest_path, None
    personas = manifest.get("personas")
    if not isinstance(personas, list):
        return manifest_path, None
    return manifest_path, {persona.get("id"): persona for persona in personas if isinstance(persona, dict)}


def specialist_matches(changed_files):
    haystack = "\n".join(path.lower() for path in changed_files)
    matches = []
    for persona, patterns in SPECIALIST_RULES:
        if any(pattern in haystack for pattern in patterns):
            matches.append(persona)
    return matches


def recommend_personas(root, mode, changed_files, review_risk, warnings):
    manifest_path, personas_by_id = load_persona_manifest(root)
    if mode == "learning-comments":
        return [], [".codex/prompts/codebase-learning-comments.md"]
    if mode == "test-first":
        return [], [".codex/prompts/tdd/README.md"]
    if mode == "verification":
        return [], [".codex/prompts/verification-sentinel.md"]

    if not personas_by_id:
        warnings.append(
            "Persona manifest is missing or invalid. Reinstall with repo-contract-kit's `--preset agentic` profile to restore local prompts."
        )
        return [], [".agent-workflows/repo-review.md", ".codex/prompts/multi-agent-repo-review.md"]

    selected = list(DEFAULT_REVIEW_PERSONAS)
    for persona in specialist_matches(changed_files):
        if persona not in selected:
            selected.append(persona)
    for trigger in review_risk.get("triggers", []):
        for persona in trigger.get("personas", []):
            if persona not in selected:
                selected.append(persona)

    recommended = []
    for persona_id in selected:
        persona = personas_by_id.get(persona_id)
        if not persona:
            warnings.append(f"Persona `{persona_id}` is not present in {manifest_path.relative_to(root)}.")
            continue
        prompt = persona.get("prompt", "")
        if prompt and not (root / prompt).exists():
            warnings.append(f"Persona prompt is missing: {prompt}")
        recommended.append(
            {
                "id": persona_id,
                "prompt": prompt,
                "mode": persona.get("mode"),
                "risk_focus": persona.get("risk_focus", []),
                "max_findings": persona.get("max_findings"),
            }
        )

    return recommended, [".agent-workflows/repo-review.md", ".codex/prompts/multi-agent-repo-review.md"]


def ensure_runs_gitignore(runs_root):
    runs_root.mkdir(parents=True, exist_ok=True)
    gitignore = runs_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")


def build_receipt_template(run_id, started_at, mode, repo, changed_files):
    return {
        "schema_version": 1,
        "run": {
            "id": run_id,
            "started_at": started_at,
            "completed_at": None,
            "mode": mode,
            "status": "not-run",
        },
        "tooling": {
            "agent_tool": "manual",
            "agent_tool_version": None,
            "local_only": True,
            "network_used": False,
            "notes": "Replace `manual` with the local coding tool used for the session.",
        },
        "scope": {
            "repo_root": str(repo),
            "base_ref": None,
            "changed_files": changed_files,
            "allowed_files": [],
            "protected_files": [],
        },
        "review_risk": {
            "risk_tier": None,
            "trust_profile": None,
            "triggers": [],
            "network_or_tool_allowlist_checked": False,
            "mutation_boundary_checked": False,
            "data_boundary_checked": False,
        },
        "evidence": {
            "files_inspected": [],
            "commands": [],
            "docs_impact": {
                "checked": False,
                "result": "not-run",
                "categories": [],
                "waiver_reason": None,
            },
            "tests": {
                "result": "not-run",
                "failing_test_evidence": None,
                "passing_test_evidence": None,
                "generated_test_provenance": None,
                "skip_reason": None,
            },
        },
        "findings": [],
        "disposition": {
            "summary": "",
            "next_actions": [],
            "human_approval_required": True,
        },
    }


def allocate_run_dir(runs_root, run_id):
    for index in range(100):
        candidate_id = run_id if index == 0 else f"{run_id}-{index + 1}"
        output_dir = runs_root / candidate_id
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
            return candidate_id, output_dir
        except FileExistsError:
            continue
    raise SystemExit(f"Unable to allocate unique agent-start run directory for {run_id}")


def format_check_lines(checks):
    lines = []
    for check in checks:
        lines.append(f"- `{check['name']}`: {check['result']} (`{check['command']}`)")
    return "\n".join(lines)


def format_persona_lines(personas):
    if not personas:
        return "- No reviewer personas selected for this mode."
    return "\n".join(f"- `{persona['id']}`: {persona.get('prompt')}" for persona in personas)


def build_brief(packet):
    latest = packet["latest_adr"]
    adr_line = "No latest ADR was found."
    if latest:
        adr_line = f"Latest ADR: `{latest['path']}` - {latest['title']}."

    warnings = packet["warnings"] or ["None."]
    warning_lines = "\n".join(f"- {warning}" for warning in warnings)
    kit = packet["kit"]
    versioning = packet["versioning"]
    version_guidance = "- No version bump signal detected from current changed paths."
    if versioning["consider_bump"]:
        version_guidance = (
            "- Behavior/API/config/runtime impact is possible. Run `make version-check` and consider "
            "`make version-bump BUMP=patch|minor|major` after the change scope is accepted."
        )
    backlog = packet["backlog"]
    if backlog["mirror_present"]:
        backlog_guidance = (
            f"- Backlog mirror: `{backlog['mirror_path']}` with {backlog['open_item_count']} open items.\n"
            f"- Task-packet prompt: `{backlog['task_packet_prompt'] or 'missing'}`\n"
            f"- Task-packet schema: `{backlog['task_packet_schema'] or 'missing'}`\n"
            "- For backlog-driven work, select one item and convert it into a task packet before editing."
        )
    else:
        backlog_guidance = (
            "- No backlog mirror was found under docs/backlog.md.\n"
            "- Use an issue, accepted finding, user request, or external planning item as the task source."
        )
    risk = packet["review_risk"]
    if risk["triggers"]:
        trigger_lines = "\n".join(
            f"- `{trigger['path']}`: `{trigger['rule_id']}` ({trigger['tier']}) - {trigger['reason']}"
            for trigger in risk["triggers"][:8]
        )
    else:
        trigger_lines = "- No deterministic risk triggers matched the changed files."
    risk_guidance = "\n".join(f"- {item}" for item in risk["guidance"])
    policy_docs = "\n".join(f"- `{path}`" for path in risk["policy_docs"] if path)

    return f"""# Agent Start Brief

Mode: `{packet['mode']}`
Run ID: `{packet['run_id']}`

Read `AGENTS.md`, `REVIEW.md`, and `.agent-workflows/README.md` first.
Then follow the mode-specific workflow using this packet as your starting context.

Treat latest ADRs as constraints/defaults; use the requested mode/backlog item as the task.
{adr_line}

## Startup Context

- Session packet: `{packet['paths']['session_start']}`
- Receipt template: `{packet['paths']['receipt_template']}`
- Changed files: {len(packet['git']['changed_files'])}
- Dirty working tree: {str(packet['git']['dirty']).lower()}
- Kit status: {kit['status']} (version `{kit['source_version'] or 'unknown'}`)
- Prompt snapshot: `{(kit['prompt_snapshot'] or {}).get('name', 'agent-workflow-kit')}` ref `{(kit['prompt_snapshot'] or {}).get('source_ref', 'unknown')}`
- Target repo version: `{versioning['target_version']['current'] or 'missing'}`
- Review risk tier: `{risk['risk_tier']}` using trust profile `{risk['trust_profile']}`

## Kit And Versioning

- Update status command: `{kit['update_command']}`
- Manifest present: {str(kit['manifest_present']).lower()}
- Managed files: {kit['managed_file_count']}
{version_guidance}

## Backlog And Task Packets

{backlog_guidance}

## Review Risk And Tool Boundary

Triggers:

{trigger_lines}

Guidance:

{risk_guidance}

Policy docs:

{policy_docs}

## Recommended Prompts

{chr(10).join(f"- `{path}`" for path in packet['prompt_paths'])}

## Recommended Personas

{format_persona_lines(packet['recommended_personas'])}

## Discovery Checks

{format_check_lines(packet['checks'])}

## Warnings

{warning_lines}

## Expected Agent Output

Produce evidence-backed findings and update a receipt based on `receipt.template.json`.
Do not edit code until the review findings or implementation scope are clear.
"""


def parse_docs_impact(localize_result, warnings):
    if localize_result["result"] != "pass":
        warnings.append("Docs-impact localization failed; inspect command output in session-start.json.")
        return None
    if not localize_result["stdout"]:
        return None
    try:
        return json.loads(localize_result["stdout"])
    except json.JSONDecodeError:
        warnings.append("Docs-impact localization did not emit valid JSON.")
        return None


def main():
    parser = argparse.ArgumentParser(description="Create a local agent startup packet")
    parser.add_argument("--mode", default=os.environ.get("MODE", "bootstrap"), choices=sorted(VALID_MODES))
    parser.add_argument("--output-root", default=".agent-workflows/runs")
    args = parser.parse_args()

    root = repo_root()
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    head = optional_git_output(["rev-parse", "HEAD"], root, "no-head")
    short_head = optional_git_output(["rev-parse", "--short", "HEAD"], root, "no-head")
    branch = optional_git_output(["branch", "--show-current"], root) or f"detached-{short_head}"
    status_output = git_output(["status", "--porcelain=v1"], root)
    changed_files = parse_status_paths(status_output)
    run_id = f"{timestamp}-{short_head}"

    runs_root = (root / args.output_root).resolve()
    try:
        ensure_runs_gitignore(runs_root)
        run_id, output_dir = allocate_run_dir(runs_root, run_id)
    except OSError as exc:
        raise SystemExit(f"Unable to create agent-start output directory: {exc}") from exc

    warnings = []
    latest = latest_adr(root)
    if not latest:
        warnings.append("No current ADR found under docs/adr/. Continue with repo docs and requested mode.")

    check_doc = command_summary(run([sys.executable, "scripts/check_doc_impact.py", "--working-tree"], root))
    lint_docs = command_summary(run([sys.executable, "scripts/lint_agent_docs.py", "--strict-paths"], root))
    localize = command_summary(run([sys.executable, "scripts/localize_doc_impact.py", "--working-tree", "--json"], root))
    checks = [
        {"name": "docs-check", **check_doc},
        {"name": "agent-docs-lint", **lint_docs},
        {"name": "agent-docs-localize", **localize},
    ]
    for check in checks:
        if check["result"] != "pass":
            warnings.append(f"{check['name']} returned {check['result']}; treat it as session context, not a startup blocker.")

    docs_impact = parse_docs_impact(localize, warnings)
    review_risk = classify_review_risk(changed_files)
    kit = kit_context(root)
    backlog = backlog_context(root)
    versioning = {
        "target_version": target_version_context(root),
        "consider_bump": should_consider_version_bump(docs_impact, changed_files),
        "commands": [
            "make version-status",
            "make version-check",
            "make version-bump BUMP=patch",
        ],
    }
    if kit["status"] == "legacy-no-manifest":
        warnings.append("Kit install receipt exists but manifest is missing. Run `make kit-update KIT=/path/to/repo-contract-kit` once to adopt safely.")
    if not versioning["target_version"]["current"]:
        warnings.append("Target repo VERSION is missing. Install or refresh the versioning profile if this repo should track SemVer locally.")
    if backlog["mirror_present"] and not backlog["task_packet_prompt"]:
        warnings.append("Backlog mirror exists but .codex/prompts/task-packet.md is missing. Install the review-prompts profile to enable backlog-to-task handoff.")
    if backlog["task_packet_prompt"] and not backlog["task_packet_schema"]:
        warnings.append("Task-packet prompt exists but schemas/task-packet.schema.json is missing. Refresh the installed kit files.")
    recommended_personas, prompt_paths = recommend_personas(root, args.mode, changed_files, review_risk, warnings)
    for prompt_path in prompt_paths:
        if not (root / prompt_path).exists():
            warnings.append(
                f"Prompt path is missing: {prompt_path}. Reinstall with repo-contract-kit's `--preset agentic` profile if this repo should self-serve agent workflows."
            )

    session_path = output_dir / "session-start.json"
    receipt_path = output_dir / "receipt.template.json"
    brief_path = output_dir / "agent-brief.md"
    next_commands = [
        "make agent-verify",
        "make agent-docs-localize",
        "make agent-review",
    ]
    if backlog["task_packet_prompt"]:
        next_commands.insert(2, "make agent-task-packet")

    packet = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": started_at,
        "mode": args.mode,
        "repo": {
            "root": str(root),
        },
        "git": {
            "branch": branch,
            "head": head,
            "short_head": short_head,
            "dirty": bool(status_output.strip()),
            "changed_files": changed_files,
        },
        "docs_impact": docs_impact,
        "review_risk": review_risk,
        "kit": kit,
        "backlog": backlog,
        "versioning": versioning,
        "checks": checks,
        "latest_adr": latest,
        "recommended_personas": recommended_personas,
        "prompt_paths": prompt_paths,
        "next_commands": next_commands,
        "paths": {
            "agent_brief": str(brief_path.relative_to(root)),
            "session_start": str(session_path.relative_to(root)),
            "receipt_template": str(receipt_path.relative_to(root)),
        },
        "warnings": warnings,
    }

    receipt = build_receipt_template(run_id, started_at, args.mode, root, changed_files)
    receipt["review_risk"]["risk_tier"] = review_risk["risk_tier"]
    receipt["review_risk"]["trust_profile"] = review_risk["trust_profile"]
    receipt["review_risk"]["triggers"] = review_risk["triggers"]
    brief = build_brief(packet)

    session_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief_path.write_text(brief, encoding="utf-8")

    print("Agent start packet written:")
    print(f" - {brief_path.relative_to(root)}")
    print(f" - {session_path.relative_to(root)}")
    print(f" - {receipt_path.relative_to(root)}")
    print()
    print("Next step:")
    print(f"  Give the agent {brief_path.relative_to(root)} or paste its contents into your local coding tool.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

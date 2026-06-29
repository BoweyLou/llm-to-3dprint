#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

import goal_check
from classify_review_risk import classify_paths as classify_review_paths

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
# - load_persona_manifest/recommend_personas choose personas.
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

FRESHNESS_POLICY_MODES = [
    {
        "id": "report-only",
        "label": "Report only",
        "writes": "none",
        "description": "Default task-start behavior. Report cleanliness, backlog, and kit drift without previewing or applying updates.",
    },
    {
        "id": "dry-run",
        "label": "Dry run",
        "writes": "none",
        "description": "Preview a target install refresh with an explicit dry-run command before any target files change.",
    },
    {
        "id": "auto-update-clean",
        "label": "Auto update clean",
        "writes": "target",
        "description": "Only eligible after explicit approval, a clean checkout, and a stale target install; agent-start never applies it automatically.",
    },
    {
        "id": "maintenance",
        "label": "Maintenance",
        "writes": "global",
        "description": "Reserved for explicit maintenance work that refreshes the global launcher or maintainer checkout.",
    },
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


def classify_review_risk(changed_files):
    result = classify_review_paths(changed_files)
    result["policy_docs"] = [
        "docs/ops/agent-tool-network-allowlist.md",
        ".agent-workflows/agent-permission-policy.json",
        ".codex/prompts/policies/review-risk-classifier.md",
        ".codex/prompts/policies/read-only-reviewer-sandbox.md",
        ".codex/prompts/policies/local-private-review.md",
        ".codex/prompts/policies/browser-research-agent.md",
    ]
    return result


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
            "update_command": "kit update --dry-run && kit update",
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
        "update_command": "kit update --dry-run && kit update",
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
    prompt_path = ".codex/prompts/task-packet.md"
    schema_path = "schemas/task-packet.schema.json"
    try:
        from repo_contract_kit import build_backlog_report

        report = build_backlog_report(root, include_items=False)
    except Exception:
        report = None

    if report and report.get("selected_source"):
        counts = report.get("counts") or {}
        open_items = []
        for item in report.get("open_items") or []:
            item_id = item.get("id") or "unknown"
            title = item.get("title") or item.get("item") or ""
            priority = item.get("priority") or "P2"
            open_items.append(f"{item_id} [{priority}] {title}".strip())
        return {
            "mirror_present": True,
            "mirror_path": report.get("selected_source"),
            "selected_source": report.get("selected_source"),
            "source_contract": report.get("source_contract"),
            "mirror_sources": report.get("mirror_sources") or [],
            "open_items": open_items[:10],
            "open_item_count": counts.get("open", 0) + counts.get("partial", 0) + counts.get("other", 0),
            "done_item_count": counts.get("done", 0),
            "total_item_count": counts.get("total", 0),
            "next_open_item": report.get("next_open_item"),
            "warnings": report.get("warnings") or [],
            "check": report.get("check") or {},
            "task_packet_prompt": prompt_path if (root / prompt_path).exists() else None,
            "task_packet_schema": schema_path if (root / schema_path).exists() else None,
            "guidance": (
                f"Backlog prioritisation belongs in the selected repository planning source `{report.get('selected_source')}` "
                "or an external planning tool. Convert one selected backlog item into a task packet before implementation."
            ),
        }

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

    return {
        "mirror_present": text is not None,
        "mirror_path": "docs/backlog.md" if text is not None else None,
        "selected_source": "docs/backlog.md" if text is not None else None,
        "source_contract": None,
        "mirror_sources": [],
        "open_items": open_items[:10],
        "open_item_count": len(open_items),
        "done_item_count": len(done_items),
        "total_item_count": len(open_items) + len(done_items),
        "next_open_item": None,
        "warnings": [],
        "check": {"passed": text is not None, "errors": [] if text is not None else ["no-backlog-source"]},
        "task_packet_prompt": prompt_path if (root / prompt_path).exists() else None,
        "task_packet_schema": schema_path if (root / schema_path).exists() else None,
        "guidance": (
            "Backlog prioritisation belongs in the repository planning source or external planning tool; docs/backlog.md is the portable repo mirror. "
            "Convert one selected backlog item into a task packet before implementation."
            if text is not None
            else "No docs/backlog.md mirror found. Use the current user request, issue, or accepted finding as the task source."
        ),
    }


def safe_update_modes(root, repo_cleanliness, kit_drift):
    repo_arg = str(root)
    dirty = bool(repo_cleanliness.get("dirty"))
    classification = kit_drift.get("classification") or "unknown"
    next_commands = kit_drift.get("next_commands") or []
    dry_run_commands = [item for item in next_commands if item.get("writes") == "none"]
    target_write_commands = [item for item in next_commands if item.get("writes") == "target"]
    global_write_commands = [item for item in next_commands if item.get("writes") == "global"]

    dry_run_command = (
        dry_run_commands[0]["command"]
        if dry_run_commands
        else f"kit update --dry-run --repo {repo_arg}"
    )
    target_apply_command = target_write_commands[0]["command"] if target_write_commands else f"kit update --repo {repo_arg}"
    global_update_command = global_write_commands[0]["command"] if global_write_commands else "kit update --global"
    stale_target = classification == "stale"
    newer_target = classification == "newer-target"

    modes = []
    for mode in FRESHNESS_POLICY_MODES:
        item = dict(mode)
        item["auto_apply"] = False
        if mode["id"] == "report-only":
            item.update(
                {
                    "enabled": True,
                    "eligible": True,
                    "command": f"kit status --repo {repo_arg}",
                    "reason": "safe default for every task start",
                }
            )
        elif mode["id"] == "dry-run":
            item.update(
                {
                    "enabled": True,
                    "eligible": classification in {"stale", "unknown", "not-installed"},
                    "command": dry_run_command,
                    "reason": "non-mutating preview when target freshness is stale or unknown",
                }
            )
        elif mode["id"] == "auto-update-clean":
            item.update(
                {
                    "enabled": False,
                    "eligible": stale_target and not dirty,
                    "command": target_apply_command,
                    "reason": (
                        "requires explicit approval and a clean checkout"
                        if not dirty
                        else "blocked because the checkout is dirty"
                    ),
                }
            )
        elif mode["id"] == "maintenance":
            item.update(
                {
                    "enabled": False,
                    "eligible": newer_target,
                    "command": global_update_command,
                    "reason": "global-tool refresh belongs to explicit maintenance, not normal task start",
                }
            )
        modes.append(item)
    return modes


def fallback_kit_drift(root, error):
    repo_arg = str(root)
    return {
        "classification": "unknown",
        "reason_code": "startup_freshness_error",
        "reason": f"task-start freshness could not inspect kit drift: {error}",
        "severity": "warning",
        "global_tool": {},
        "target_install": {},
        "comparisons": {
            "version": "unknown",
            "source_ref": "unknown",
            "prompt_snapshot": "unknown",
        },
        "next_commands": [
            {
                "command": f"kit status --repo {repo_arg} --json",
                "reason": "inspect raw target and global kit metadata",
                "writes": "none",
            }
        ],
        "target_repo_writes": {"performed": False, "reason": "task-start freshness is read-only", "paths": []},
        "sidecar_writes": {"performed": False, "reason": "task-start freshness is read-only", "paths": []},
    }


def task_start_freshness(root, status_output, backlog):
    changed_files = parse_status_paths(status_output)
    repo_cleanliness = {
        "dirty": bool(status_output.strip()),
        "changed_file_count": len(changed_files),
        "changed_files": changed_files[:25],
        "omitted_changed_file_count": max(0, len(changed_files) - 25),
    }
    backlog_source = {
        "selected_source": backlog.get("selected_source"),
        "source_contract": backlog.get("source_contract"),
        "open_item_count": backlog.get("open_item_count", 0),
        "done_item_count": backlog.get("done_item_count", 0),
        "total_item_count": backlog.get("total_item_count", 0),
        "next_open_item": backlog.get("next_open_item"),
        "warnings": backlog.get("warnings") or [],
    }

    try:
        import kit_status
        import repo_contract_kit

        install = repo_contract_kit.install_state(root)
        local_kit = kit_status.local_kit_state(repo_contract_kit.ROOT)
        kit_drift = repo_contract_kit.kit_drift_diagnostics(root, install, local_kit)
    except Exception as exc:  # pragma: no cover - defensive fallback for broken installs
        kit_drift = fallback_kit_drift(root, exc)

    modes = safe_update_modes(root, repo_cleanliness, kit_drift)
    recommended_mode = "report-only"
    if kit_drift.get("classification") in {"stale", "unknown", "not-installed"}:
        recommended_mode = "dry-run"
    elif kit_drift.get("classification") == "newer-target":
        recommended_mode = "maintenance"

    return {
        "result": "warning" if kit_drift.get("severity") == "warning" else "ok",
        "policy": {
            "selected": "report-only",
            "recommended": recommended_mode,
            "auto_apply_performed": False,
            "target_repo_writes": {"performed": False, "reason": "agent-start freshness is read-only", "paths": []},
            "sidecar_writes": {"performed": False, "reason": "agent-start freshness is read-only", "paths": []},
        },
        "repo_cleanliness": repo_cleanliness,
        "backlog_source": backlog_source,
        "kit_drift": kit_drift,
        "safe_update_modes": modes,
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

    selected = list(review_risk.get("recommended_personas") or DEFAULT_REVIEW_PERSONAS)

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


def format_freshness_mode_lines(modes):
    lines = []
    for mode in modes:
        enabled = "enabled" if mode.get("enabled") else "approval-required"
        eligible = "eligible" if mode.get("eligible") else "not eligible"
        lines.append(
            f"- `{mode['id']}`: {enabled}, {eligible}, writes `{mode['writes']}`; "
            f"command: `{mode['command']}`"
        )
    return "\n".join(lines)


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
    freshness = packet["task_start_freshness"]
    drift = freshness["kit_drift"]
    if backlog["mirror_present"]:
        backlog_guidance = (
            f"- Backlog source: `{backlog['mirror_path']}` with {backlog['open_item_count']} open items and {backlog['done_item_count']} done items.\n"
            f"- Task-packet prompt: `{backlog['task_packet_prompt'] or 'missing'}`\n"
            f"- Task-packet schema: `{backlog['task_packet_schema'] or 'missing'}`\n"
            "- For backlog-driven work, select one item and convert it into a task packet before editing."
        )
    else:
        backlog_guidance = (
            "- No supported backlog source was found.\n"
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
    area_goal = packet["goal_check"]
    area_summary = area_goal["summary"]
    unknown_paths = area_summary.get("unknown_paths") or []
    conflict_paths = area_summary.get("conflict_paths") or []
    unknown_line = ", ".join(f"`{path}`" for path in unknown_paths[:8]) if unknown_paths else "None."
    conflict_line = ", ".join(f"`{path}`" for path in conflict_paths[:8]) if conflict_paths else "None."

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
- Task-start freshness: `{freshness['result']}`; recommended policy `{freshness['policy']['recommended']}`
- Workflow prompt snapshot ref: `{(kit['prompt_snapshot'] or {}).get('source_ref', 'unknown')}`
- Target repo version: `{versioning['target_version']['current'] or 'missing'}`
- Review risk tier: `{risk['risk_tier']}` using trust profile `{risk['trust_profile']}`
- Goal check: `{area_goal['result']}` from `{area_goal['config'].get('relative_path')}`

## Kit And Versioning

- Update status command: `{kit['update_command']}`
- Manifest present: {str(kit['manifest_present']).lower()}
- Managed files: {kit['managed_file_count']}
- Kit drift: `{drift.get('classification', 'unknown')}` ({drift.get('reason', 'unknown')})
{version_guidance}

## Task Start Freshness

- Repo clean: {str(not freshness['repo_cleanliness']['dirty']).lower()} ({freshness['repo_cleanliness']['changed_file_count']} changed files)
- Backlog source: `{freshness['backlog_source']['selected_source'] or 'none'}`
- Global kit version: `{(drift.get('global_tool') or {}).get('version') or 'unknown'}`
- Target install version: `{(drift.get('target_install') or {}).get('version') or 'unknown'}`
- Selected policy: `{freshness['policy']['selected']}`; recommended next mode: `{freshness['policy']['recommended']}`

Safe update modes:

{format_freshness_mode_lines(freshness['safe_update_modes'])}

## Backlog And Task Packets

{backlog_guidance}

## Goal And Area Check

- Repo goal: {area_goal['repo_goal'] or '(not declared)'}
- Summary: aligned {area_summary.get('aligned', 0)}, extends {area_summary.get('extends', 0)}, conflict {area_summary.get('conflict', 0)}, unknown {area_summary.get('unknown', 0)}
- Unknown paths: {unknown_line}
- Conflict paths: {conflict_line}
- Command: `make goal-check`

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
    goal_report = goal_check.build_goal_check_report(root, changed_files)
    goal_summary = goal_check.compact_goal_summary(goal_report)
    kit = kit_context(root)
    backlog = backlog_context(root)
    freshness = task_start_freshness(root, status_output, backlog)
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
        warnings.append("Kit install receipt exists but manifest is missing. Run `kit update --dry-run` then `kit update` once to adopt safely.")
    if freshness["kit_drift"].get("classification") in {"stale", "newer-target", "unknown"}:
        warnings.append(
            "Task-start freshness found kit drift; use the recommended non-mutating or maintenance command before write-capable work."
        )
    if not versioning["target_version"]["current"]:
        warnings.append("Target repo VERSION is missing. Install or refresh the versioning profile if this repo should track SemVer locally.")
    if backlog["mirror_present"] and not backlog["task_packet_prompt"]:
        warnings.append("Backlog mirror exists but .codex/prompts/task-packet.md is missing. Install the review-prompts profile to enable backlog-to-task handoff.")
    if backlog["task_packet_prompt"] and not backlog["task_packet_schema"]:
        warnings.append("Task-packet prompt exists but schemas/task-packet.schema.json is missing. Refresh the installed kit files.")
    if not goal_summary["config"].get("exists"):
        warnings.append("Area-contract config is missing; goal-check will report changed paths as unknown.")
    if goal_summary["summary"].get("unknown"):
        warnings.append("Goal-check found changed paths with no matching area contract.")
    if goal_summary["summary"].get("conflict"):
        warnings.append("Goal-check found changed paths marked as conflict with the repo goal.")
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
        "goal_check": goal_summary,
        "kit": kit,
        "backlog": backlog,
        "task_start_freshness": freshness,
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

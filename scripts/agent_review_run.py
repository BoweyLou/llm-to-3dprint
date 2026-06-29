#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Script flow:
# 1. Load the most recent agent-start run directory and its review inputs.
# 2. Run selected review personas through the configured local agent command.
# 3. Parse and validate each persona result plus the synthesis result.
# 4. Write a structured receipt that captures findings, commands, and caveats.
#
# Function guide:
# - run/git_output/repo_root/git_status wrap shell and git operations.
# - read_json/write_json/relative/latest_run_dir handle filesystem state.
# - load_personas/selected_persona_ids/load_permission_policy/policy_summary prepare review configuration.
# - prompt_header/synthesis_prompt build prompts sent to the local agent.
# - extract_json_from_text/extract_json_from_stream_events/extract_fenced_json/extract_balanced_json recover JSON output.
# - validate_persona_payload/validate_synthesis_payload check model output shape.
# - manual_persona_result/manual_synthesis_result provide fallback records.
# - run_amp/load_receipt_template/build_receipt/main orchestrate the review run.

VALID_REVIEW_MODES = {"bootstrap", "drift", "pull-request", "release-gate"}
DEFAULT_PERSONAS = [
    "doc-code-delta",
    "ai-code-slop",
    "test-behavior-risk",
    "reuse-architecture",
]


def run(cmd, cwd, input_text=None, timeout=None):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            cmd,
            124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTimed out after {timeout} seconds.",
        )
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 127, stdout="", stderr=str(exc))


def git_output(args, cwd):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def repo_root():
    return Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()


def git_status(root):
    return git_output(["status", "--porcelain=v1"], root)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing required JSON file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path, root):
    return str(path.resolve().relative_to(root.resolve()))


def latest_run_dir(root, mode):
    runs_root = root / ".agent-workflows" / "runs"
    runs = sorted(path for path in runs_root.iterdir() if path.is_dir()) if runs_root.is_dir() else []
    candidates = [
        path
        for path in runs
        if (path / "session-start.json").exists()
        and read_json(path / "session-start.json").get("mode") == mode
    ]
    if candidates:
        return candidates[-1]

    result = run([sys.executable, "scripts/agent_start.py", "--mode", mode], root)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "agent_start.py failed")

    runs = sorted(path for path in runs_root.iterdir() if path.is_dir()) if runs_root.is_dir() else []
    candidates = [
        path
        for path in runs
        if (path / "session-start.json").exists()
        and read_json(path / "session-start.json").get("mode") == mode
    ]
    if not candidates:
        raise SystemExit("agent_start.py completed but no session-start.json was created")
    return candidates[-1]


def load_personas(root):
    manifest_path = root / ".codex" / "prompts" / "personas" / "manifest.json"
    manifest = read_json(manifest_path)
    personas = manifest.get("personas", [])
    if not isinstance(personas, list):
        raise SystemExit(f"Invalid persona manifest: {manifest_path}")
    return {persona["id"]: persona for persona in personas if isinstance(persona, dict) and "id" in persona}


def selected_persona_ids(packet, personas_by_id, requested):
    if requested:
        ids = [item.strip() for item in requested.split(",") if item.strip()]
    else:
        ids = [persona.get("id") for persona in packet.get("recommended_personas", []) if persona.get("id")]
        if not ids:
            ids = list(DEFAULT_PERSONAS)

    missing = [persona_id for persona_id in ids if persona_id not in personas_by_id]
    if missing:
        raise SystemExit(f"Unknown persona id(s): {', '.join(missing)}")
    return ids


def load_permission_policy(root, trust_profile):
    path = root / ".agent-workflows" / "agent-permission-policy.json"
    if not path.exists():
        return None, [f"Missing permission policy: {path}"]
    policy = read_json(path)
    profiles = {
        profile.get("name"): profile
        for profile in policy.get("profiles", [])
        if isinstance(profile, dict) and profile.get("name")
    }
    profile_name = trust_profile or policy.get("default_profile") or "read-only-review"
    profile = profiles.get(profile_name)
    if not profile:
        return None, [f"Unknown permission profile: {profile_name}"]

    errors = []
    filesystem = profile.get("filesystem", {})
    git = profile.get("git", {})
    browser = profile.get("browser", {})
    mcp = profile.get("mcp", {})
    if filesystem.get("write") not in {"deny", "approval-required"}:
        errors.append(f"{profile_name}: filesystem.write must not be allow for review runner")
    if filesystem.get("delete") != "deny":
        errors.append(f"{profile_name}: filesystem.delete must be deny for review runner")
    for action in ["stage", "commit", "push"]:
        if git.get(action) != "deny":
            errors.append(f"{profile_name}: git.{action} must be deny for review runner")
    if browser.get("account_mutation") != "deny":
        errors.append(f"{profile_name}: browser.account_mutation must be deny")
    if browser.get("captcha_bypass") != "deny":
        errors.append(f"{profile_name}: browser.captcha_bypass must be deny")
    if mcp.get("write_tools") != "deny":
        errors.append(f"{profile_name}: mcp.write_tools must be deny for review runner")
    return profile, errors


def policy_summary(policy_profile):
    if not policy_profile:
        return "No permission policy loaded."
    return json.dumps(
        {
            "name": policy_profile.get("name"),
            "trust_level": policy_profile.get("trust_level"),
            "filesystem": policy_profile.get("filesystem", {}),
            "git": policy_profile.get("git", {}),
            "browser": policy_profile.get("browser", {}),
            "network": policy_profile.get("network", {}),
            "mcp": policy_profile.get("mcp", {}),
            "ci": policy_profile.get("ci", {}),
        },
        indent=2,
        sort_keys=True,
    )


def prompt_header(root, run_id, mode, persona, permission_profile):
    prompt_path = persona.get("prompt")
    persona_prompt = (root / prompt_path).read_text(encoding="utf-8")
    return f"""You are running as the `{persona['id']}` reviewer for local run `{run_id}`.

Mode: `{mode}`
Repository root: `{root}`

Read-only requirement:
- Do not edit files.
- Do not create commits.
- You may read files, search the repo, and run local read-only checks.
- Return only JSON. Do not wrap the JSON in Markdown.

Permission profile:
{policy_summary(permission_profile)}

Return this JSON shape:
{{
  "schema_version": 1,
  "run_id": "{run_id}",
  "persona_id": "{persona['id']}",
  "status": "complete",
  "findings": [
    {{
      "id": "FINDING_001",
      "priority": "P1",
      "area": "tests",
      "title": "Short title",
      "confidence": "high",
      "evidence": ["path/to/file.ext:line concrete observation"],
      "recommendation": "Smallest useful fix",
      "status": "open",
      "false_positive_notes": "Most plausible reason this might be harmless, or none found."
    }}
  ],
  "notes": []
}}

Use `schemas/session-receipt.schema.json#/properties/findings/items` for each
finding. Return no more than {persona.get('max_findings', 5)} findings.

Persona prompt follows.

---

{persona_prompt}
"""


def synthesis_prompt(root, run_id, mode, persona_results, permission_profile):
    prompt_path = root / ".codex" / "prompts" / "review-synthesis.md"
    synthesis = prompt_path.read_text(encoding="utf-8")
    return f"""You are the review synthesis runner for local run `{run_id}`.

Mode: `{mode}`
Repository root: `{root}`

Read-only requirement:
- Do not edit files.
- Do not create commits.
- Return only JSON matching `schemas/review-synthesis.schema.json`.
- Do not wrap the JSON in Markdown.

Permission profile:
{policy_summary(permission_profile)}

Persona result artifacts:
{json.dumps(persona_results, indent=2, sort_keys=True)}

Synthesis prompt follows.

---

{synthesis}
"""


def extract_json_from_text(text):
    text = text.strip()
    if not text:
        raise ValueError("empty output")

    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get("type") in {"result", "assistant"}:
            return extract_json_from_stream_events([payload])
        return payload
    except json.JSONDecodeError:
        pass

    stream_events = []
    stream_candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        stream_events.append(event)
        if isinstance(event, dict) and event.get("type") == "result":
            result_text = event.get("result") or event.get("error") or ""
            if result_text:
                stream_candidates.append(result_text)
        if isinstance(event, dict) and event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    stream_candidates.append(block.get("text", ""))

    if stream_events:
        try:
            return extract_json_from_stream_events(stream_events)
        except ValueError:
            pass

    for candidate in reversed(stream_candidates):
        try:
            return extract_json_from_text(candidate)
        except ValueError:
            continue

    fenced = extract_fenced_json(text)
    if fenced:
        return json.loads(fenced)

    balanced = extract_balanced_json(text)
    if balanced:
        return json.loads(balanced)

    raise ValueError("no JSON object found in output")


def extract_json_from_stream_events(events):
    stream_candidates = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result":
            result_text = event.get("result") or event.get("error") or ""
            if result_text:
                stream_candidates.append(result_text)
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    stream_candidates.append(block.get("text", ""))
    for candidate in reversed(stream_candidates):
        try:
            return extract_json_from_text(candidate)
        except ValueError:
            continue
    raise ValueError("no JSON result found in stream events")


def extract_fenced_json(text):
    marker = "```"
    start = text.find(marker)
    while start != -1:
        fence_end = text.find("\n", start + len(marker))
        if fence_end == -1:
            return None
        language = text[start + len(marker):fence_end].strip().lower()
        close = text.find(marker, fence_end + 1)
        if close == -1:
            return None
        body = text[fence_end + 1:close].strip()
        if language in {"json", ""} and body.startswith("{"):
            return body
        start = text.find(marker, close + len(marker))
    return None


def extract_balanced_json(text):
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        start = text.find("{", start + 1)
    return None


def validate_persona_payload(payload, persona_id):
    errors = []
    if not isinstance(payload, dict):
        return {"schema_version": 1, "persona_id": persona_id, "status": "invalid", "findings": []}, ["payload is not an object"]

    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
        errors.append("findings is not an array")

    required = {"id", "priority", "area", "title", "confidence", "evidence", "recommendation", "status"}
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"finding {index + 1} is not an object")
            continue
        missing = sorted(required - finding.keys())
        if missing:
            errors.append(f"finding {index + 1} missing required fields: {', '.join(missing)}")
        if not isinstance(finding.get("evidence"), list) or not finding.get("evidence"):
            errors.append(f"finding {index + 1} must include at least one evidence item")

    normalized = {
        "schema_version": payload.get("schema_version", 1),
        "run_id": payload.get("run_id"),
        "persona_id": payload.get("persona_id", persona_id),
        "status": "invalid" if errors else payload.get("status", "complete"),
        "findings": findings,
        "notes": payload.get("notes", []),
        "validation_errors": errors,
    }
    return normalized, errors


def validate_synthesis_payload(payload):
    errors = []
    if not isinstance(payload, dict):
        return {"schema_version": 1, "findings": []}, ["payload is not an object"]
    for field in [
        "schema_version",
        "run",
        "summary",
        "findings",
        "remediation_batches",
        "needs_human_decision",
        "not_recommended",
        "disposition",
    ]:
        if field not in payload:
            errors.append(f"missing required field: {field}")
    if not isinstance(payload.get("summary", []), list):
        errors.append("summary must be an array")
    if not isinstance(payload.get("findings", []), list):
        errors.append("findings must be an array")
    return payload, errors


def manual_persona_result(run_id, persona_id):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "persona_id": persona_id,
        "status": "planned",
        "findings": [],
        "notes": [
            "Prompt generated only. Run this prompt in a local agent and replace this artifact with findings JSON."
        ],
        "validation_errors": [],
    }


def manual_synthesis_result(run_id, mode, persona_artifacts):
    return {
        "schema_version": 1,
        "run": {
            "run_id": run_id,
            "mode": mode,
            "synthesized_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "source_artifacts": persona_artifacts,
        },
        "summary": ["Manual runner generated persona prompts; synthesis has not been executed."],
        "findings": [],
        "remediation_batches": [],
        "needs_human_decision": [],
        "not_recommended": [],
        "disposition": {
            "overall_status": "not-run",
            "summary": "Run the generated persona prompts, then rerun synthesis.",
            "next_actions": ["Run persona prompts and replace planned findings artifacts."],
        },
    }


def run_amp(root, amp_command, prompt, timeout):
    cmd = [amp_command, "--execute", "--stream-json"]
    return run(cmd, root, input_text=prompt, timeout=timeout or None)


def load_receipt_template(run_dir):
    path = run_dir / "receipt.template.json"
    if path.exists():
        return read_json(path)
    return None


def build_receipt(receipt_template, packet, runner_payload, status):
    receipt = receipt_template or {
        "schema_version": 1,
        "run": {"id": packet["run_id"], "started_at": packet["created_at"], "mode": packet["mode"]},
        "tooling": {"agent_tool": "manual", "local_only": True},
        "scope": {"repo_root": packet["repo"]["root"], "changed_files": packet["git"]["changed_files"]},
        "evidence": {"commands": [], "docs_impact": {"checked": False, "result": "not-run"}, "tests": {"result": "not-run"}},
        "findings": [],
        "disposition": {"summary": "", "next_actions": []},
    }
    receipt["run"]["completed_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt["run"]["status"] = status
    receipt["tooling"]["agent_tool"] = runner_payload["agent"]
    receipt["tooling"]["local_only"] = True
    receipt["evidence"]["commands"] = [
        {
            "command": (
                "python3 scripts/agent_review_run.py "
                f"--mode {runner_payload['mode']} --agent {runner_payload['agent']}"
            ),
            "result": "pass" if status in {"pass", "pass-with-caveats"} else status,
            "exit_code": 0 if status in {"pass", "pass-with-caveats"} else None,
            "notes": runner_payload["summary"],
        }
    ]
    receipt["evidence"]["docs_impact"] = {
        "checked": True,
        "result": "not-applicable",
        "categories": [],
        "waiver_reason": "Review artifact generation does not modify product or user documentation.",
    }
    receipt["evidence"]["tests"] = {
        "result": "not-applicable",
        "failing_test_evidence": None,
        "passing_test_evidence": None,
        "generated_test_provenance": None,
        "skip_reason": "Review artifact generation only; no behavior change under test.",
    }
    receipt["findings"] = runner_payload.get("findings", [])
    receipt["disposition"]["summary"] = runner_payload["summary"]
    receipt["disposition"]["next_actions"] = runner_payload["next_actions"]
    return receipt


def main():
    parser = argparse.ArgumentParser(description="Run local read-only persona review artifacts")
    parser.add_argument("--agent", default=os.environ.get("AGENT", "manual"), choices=["manual", "amp"])
    parser.add_argument("--mode", default=os.environ.get("MODE", "bootstrap"), choices=sorted(VALID_REVIEW_MODES))
    parser.add_argument("--run-dir", default=None, help="Existing .agent-workflows/runs/<id> directory")
    parser.add_argument("--personas", default=None, help="Comma-separated persona ids. Defaults to agent-start recommendations.")
    parser.add_argument("--amp-command", default=os.environ.get("AMP", "amp"))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("AGENT_TIMEOUT", "0")))
    parser.add_argument("--trust-profile", default=os.environ.get("AGENT_TRUST_PROFILE", None))
    parser.add_argument("--skip-synthesis", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    permission_profile, policy_errors = load_permission_policy(root, args.trust_profile)
    if policy_errors:
        for error in policy_errors:
            print(f"Permission policy error: {error}")
        return 1

    run_dir = Path(args.run_dir).resolve() if args.run_dir else latest_run_dir(root, args.mode)
    packet = read_json(run_dir / "session-start.json")
    run_id = packet["run_id"]
    personas_by_id = load_personas(root)
    persona_ids = selected_persona_ids(packet, personas_by_id, args.personas)

    before_status = git_status(root)
    runner_dir = run_dir / "review-run"
    personas_dir = runner_dir / "personas"
    persona_results = []
    all_findings = []
    errors = []

    for persona_id in persona_ids:
        persona = personas_by_id[persona_id]
        persona_dir = personas_dir / persona_id
        persona_dir.mkdir(parents=True, exist_ok=True)
        prompt = prompt_header(root, run_id, args.mode, persona, permission_profile)
        prompt_path = persona_dir / "prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        raw_path = persona_dir / ("raw.jsonl" if args.agent == "amp" else "raw.txt")
        findings_path = persona_dir / "findings.json"
        command = None
        exit_code = None
        readonly_violation = False

        if args.agent == "manual":
            payload = manual_persona_result(run_id, persona_id)
            raw_path.write_text("Manual mode: paste prompt.md into your local agent.\n", encoding="utf-8")
        else:
            result = run_amp(root, args.amp_command, prompt, args.timeout)
            command = f"{args.amp_command} --execute --stream-json"
            exit_code = result.returncode
            raw_path.write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode != 0:
                payload = {
                    "schema_version": 1,
                    "run_id": run_id,
                    "persona_id": persona_id,
                    "status": "blocked",
                    "findings": [],
                    "notes": [result.stderr.strip() or result.stdout.strip() or "amp command failed"],
                    "validation_errors": [f"amp exited with {result.returncode}"],
                }
                errors.append(f"{persona_id}: amp exited with {result.returncode}")
            else:
                try:
                    extracted = extract_json_from_text(result.stdout)
                    payload, validation_errors = validate_persona_payload(extracted, persona_id)
                    errors.extend(f"{persona_id}: {error}" for error in validation_errors)
                except Exception as exc:
                    payload = {
                        "schema_version": 1,
                        "run_id": run_id,
                        "persona_id": persona_id,
                        "status": "invalid",
                        "findings": [],
                        "notes": [str(exc)],
                        "validation_errors": [str(exc)],
                    }
                    errors.append(f"{persona_id}: {exc}")

            after_status = git_status(root)
            readonly_violation = after_status != before_status
            if readonly_violation:
                payload["status"] = "failed-read-only"
                payload.setdefault("validation_errors", []).append("git status changed during read-only persona run")
                errors.append(f"{persona_id}: git status changed during read-only run")

        write_json(findings_path, payload)
        findings = payload.get("findings", []) if isinstance(payload, dict) else []
        all_findings.extend(findings)
        persona_results.append(
            {
                "persona_id": persona_id,
                "status": payload.get("status", "unknown"),
                "prompt": relative(prompt_path, root),
                "raw_output": relative(raw_path, root),
                "findings": relative(findings_path, root),
                "finding_count": len(findings),
                "command": command,
                "exit_code": exit_code,
                "readonly_violation": readonly_violation,
                "validation_errors": payload.get("validation_errors", []),
            }
        )

    synthesis_dir = runner_dir / "synthesis"
    synthesis_dir.mkdir(parents=True, exist_ok=True)
    persona_artifacts = [item["findings"] for item in persona_results]
    synth_prompt = synthesis_prompt(root, run_id, args.mode, persona_results, permission_profile)
    synth_prompt_path = synthesis_dir / "prompt.md"
    synth_prompt_path.write_text(synth_prompt, encoding="utf-8")
    synth_raw_path = synthesis_dir / ("raw.jsonl" if args.agent == "amp" else "raw.txt")
    synth_json_path = synthesis_dir / "review-synthesis.json"

    if args.skip_synthesis or args.agent == "manual":
        synthesis_payload = manual_synthesis_result(run_id, args.mode, persona_artifacts)
        synth_raw_path.write_text("Manual mode: run synthesis after persona findings exist.\n", encoding="utf-8")
        synthesis_errors = []
    else:
        synth_result = run_amp(root, args.amp_command, synth_prompt, args.timeout)
        synth_raw_path.write_text(synth_result.stdout + synth_result.stderr, encoding="utf-8")
        if synth_result.returncode != 0:
            synthesis_payload = manual_synthesis_result(run_id, args.mode, persona_artifacts)
            synthesis_payload["disposition"]["overall_status"] = "blocked"
            synthesis_payload["disposition"]["summary"] = synth_result.stderr.strip() or "Amp synthesis failed."
            synthesis_errors = [f"synthesis: amp exited with {synth_result.returncode}"]
            errors.extend(synthesis_errors)
        else:
            try:
                extracted = extract_json_from_text(synth_result.stdout)
                synthesis_payload, synthesis_errors = validate_synthesis_payload(extracted)
                errors.extend(f"synthesis: {error}" for error in synthesis_errors)
            except Exception as exc:
                synthesis_payload = manual_synthesis_result(run_id, args.mode, persona_artifacts)
                synthesis_payload["disposition"]["overall_status"] = "blocked"
                synthesis_payload["disposition"]["summary"] = str(exc)
                synthesis_errors = [str(exc)]
                errors.append(f"synthesis: {exc}")
        if git_status(root) != before_status:
            synthesis_payload["disposition"]["overall_status"] = "fail"
            synthesis_payload["disposition"]["summary"] = "Git status changed during read-only synthesis."
            errors.append("synthesis: git status changed during read-only run")

    write_json(synth_json_path, synthesis_payload)

    status = "pass-with-caveats" if args.agent == "manual" else ("fail" if errors else "pass")
    summary = (
        "Generated persona prompts and placeholder artifacts."
        if args.agent == "manual"
        else ("Review runner completed with validation errors." if errors else "Review runner completed.")
    )
    runner_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "mode": args.mode,
        "agent": args.agent,
        "trust_profile": permission_profile.get("name") if permission_profile else None,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "session_start": relative(run_dir / "session-start.json", root),
        "personas": persona_results,
        "synthesis": {
            "prompt": relative(synth_prompt_path, root),
            "raw_output": relative(synth_raw_path, root),
            "json": relative(synth_json_path, root),
            "validation_errors": synthesis_errors,
        },
        "findings": all_findings,
        "summary": summary,
        "next_actions": [
            "Inspect review-run/personas/*/findings.json.",
            "Inspect review-run/synthesis/review-synthesis.json.",
        ],
        "validation_errors": errors,
    }
    review_run_path = runner_dir / "review-run.json"
    write_json(review_run_path, runner_payload)

    receipt = build_receipt(load_receipt_template(run_dir), packet, runner_payload, status)
    receipt_path = runner_dir / "receipt.json"
    write_json(receipt_path, receipt)

    print("Agent review runner artifacts written:")
    print(f" - {relative(review_run_path, root)}")
    print(f" - {relative(synth_json_path, root)}")
    print(f" - {relative(receipt_path, root)}")
    if args.agent == "manual":
        print("Manual mode generated prompts only. Run with AGENT=amp to execute through Amp.")
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f" - {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

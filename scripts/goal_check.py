#!/usr/bin/env python3
"""Deterministic repo goal and area-contract checks for changed paths."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

CONFIG_FILE = ".agent-workflows/area-contracts.json"
VALID_STATES = {"aligned", "extends", "conflict", "unknown"}


def _repo_root(repo: Path) -> Path:
    return repo.expanduser().resolve()


def config_path_for(repo: Path, config: str = CONFIG_FILE) -> Path:
    path = Path(config).expanduser()
    if path.is_absolute():
        return path
    return _repo_root(repo) / path


def _path_from_repo(repo: Path, value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    had_trailing_slash = raw.endswith("/")
    path = Path(raw).expanduser()
    if path.is_absolute():
        try:
            raw = path.resolve().relative_to(_repo_root(repo)).as_posix()
        except (OSError, ValueError):
            raw = path.as_posix()
    while raw.startswith("./"):
        raw = raw[2:]
    raw = raw.lstrip("/")
    if had_trailing_slash and raw and not raw.endswith("/"):
        raw += "/"
    return raw


def normalize_changed_path(repo: Path, value: str) -> str:
    return _path_from_repo(repo, value).rstrip("/")


def normalize_contract_path(repo: Path, value: str) -> str:
    return _path_from_repo(repo, value)


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"Area-contract config is not an object: {path}"
    return payload, None


def load_area_contracts(repo: Path, config: str = CONFIG_FILE) -> dict[str, Any]:
    path = config_path_for(repo, config)
    payload, error = _read_json(path)
    warnings: list[str] = []
    contracts: list[dict[str, Any]] = []
    if error:
        warnings.append(error)
    if payload is None:
        return {
            "path": str(path),
            "relative_path": _display_path(repo, path),
            "exists": path.exists(),
            "valid": error is None and not path.exists(),
            "repo_goal": "",
            "unknown_policy": "warn",
            "path_contracts": contracts,
            "warnings": warnings,
        }

    raw_contracts = payload.get("path_contracts")
    if raw_contracts is None:
        raw_contracts = payload.get("area_contracts", [])
    if not isinstance(raw_contracts, list):
        warnings.append("area-contract config field `path_contracts` must be a list.")
        raw_contracts = []

    for index, item in enumerate(raw_contracts):
        if not isinstance(item, dict):
            warnings.append(f"path_contracts[{index}] is not an object.")
            continue
        raw_path = str(item.get("path") or item.get("pattern") or "").strip()
        if not raw_path:
            warnings.append(f"path_contracts[{index}] is missing `path`.")
            continue
        status = str(item.get("status") or "aligned").strip().lower()
        if status not in VALID_STATES:
            warnings.append(f"path_contracts[{index}] has invalid status `{status}`; treating it as unknown.")
            status = "unknown"
        validation = item.get("validation", [])
        if isinstance(validation, str):
            validation = [validation]
        if not isinstance(validation, list):
            validation = []
            warnings.append(f"path_contracts[{index}] validation must be a string or list.")
        contracts.append(
            {
                "path": normalize_contract_path(repo, raw_path),
                "raw_path": raw_path,
                "purpose": str(item.get("purpose") or "").strip(),
                "owner": str(item.get("owner") or "").strip(),
                "source": str(item.get("source") or "").strip(),
                "status": status,
                "validation": [str(value) for value in validation if str(value).strip()],
            }
        )

    unknown_policy = str(payload.get("unknown_policy") or "warn").strip().lower() or "warn"
    if unknown_policy not in {"warn", "block"}:
        warnings.append(f"area-contract config has invalid unknown_policy `{unknown_policy}`; using warn.")
        unknown_policy = "warn"

    return {
        "path": str(path),
        "relative_path": _display_path(repo, path),
        "exists": True,
        "valid": not warnings,
        "repo_goal": str(payload.get("repo_goal") or "").strip(),
        "unknown_policy": unknown_policy,
        "path_contracts": contracts,
        "warnings": warnings,
    }


def _display_path(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(_repo_root(repo)).as_posix()
    except (OSError, ValueError):
        return str(path)


def _has_glob(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _match_score(path: str, pattern: str) -> tuple[int, int] | None:
    normalized = path.rstrip("/")
    contract = pattern.strip()
    if not contract:
        return None
    if _has_glob(contract):
        return (1, len(contract)) if fnmatch.fnmatch(normalized, contract) else None
    if contract.endswith("/"):
        prefix = contract.rstrip("/")
        if normalized == prefix or normalized.startswith(contract):
            return (2, len(contract))
        return None
    if normalized == contract:
        return (3, len(contract))
    prefix = f"{contract.rstrip('/')}/"
    if normalized.startswith(prefix):
        return (2, len(contract))
    return None


def match_contract(path: str, contracts: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for contract in contracts:
        score = _match_score(path, contract["path"])
        if score:
            matches.append((score, contract))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def file_goal_record(repo: Path, path_value: str, contracts: list[dict[str, Any]]) -> dict[str, Any]:
    path = normalize_changed_path(repo, path_value)
    contract = match_contract(path, contracts)
    if contract is None:
        return {
            "path": path,
            "state": "unknown",
            "area_contract": None,
            "message": "No area contract matched this path.",
        }
    return {
        "path": path,
        "state": contract["status"],
        "area_contract": {
            "path": contract["path"],
            "purpose": contract.get("purpose", ""),
            "owner": contract.get("owner", ""),
            "source": contract.get("source", ""),
            "status": contract.get("status", "unknown"),
            "validation": contract.get("validation", []),
        },
        "message": f"Matched area contract `{contract['path']}`.",
    }


def summarize_files(files: list[dict[str, Any]], unknown_policy: str = "warn") -> dict[str, Any]:
    counts = {state: 0 for state in sorted(VALID_STATES)}
    for item in files:
        counts[item.get("state", "unknown")] = counts.get(item.get("state", "unknown"), 0) + 1
    total = len(files)
    block_unknown = str(unknown_policy or "warn").lower() == "block"
    result = (
        "conflict"
        if counts.get("conflict")
        else "unknown"
        if counts.get("unknown") and block_unknown
        else "warnings"
        if counts.get("unknown")
        else "passed"
    )
    return {
        "total": total,
        "known": total - counts.get("unknown", 0),
        "aligned": counts.get("aligned", 0),
        "extends": counts.get("extends", 0),
        "conflict": counts.get("conflict", 0),
        "unknown": counts.get("unknown", 0),
        "unknown_paths": [item["path"] for item in files if item.get("state") == "unknown"],
        "conflict_paths": [item["path"] for item in files if item.get("state") == "conflict"],
        "result": result,
    }


def build_goal_check_report(repo: Path, changed_files: list[str] | None, config: str = CONFIG_FILE) -> dict[str, Any]:
    root = _repo_root(repo)
    config_payload = load_area_contracts(root, config)
    normalized_files = sorted(
        {normalize_changed_path(root, path) for path in (changed_files or []) if normalize_changed_path(root, path)}
    )
    files = [file_goal_record(root, path, config_payload["path_contracts"]) for path in normalized_files]
    summary = summarize_files(files, config_payload.get("unknown_policy", "warn"))
    warnings = list(config_payload.get("warnings") or [])
    if not config_payload["exists"]:
        warnings.append(f"Area-contract config not found: {config_payload['relative_path']}")
    if summary["unknown"]:
        warnings.append("Some changed files did not match an area contract.")
    if summary["conflict"]:
        warnings.append("Some changed files matched conflict area contracts.")
    return {
        "schema_version": 1,
        "command": "goal-check",
        "repo": str(root),
        "config": {
            "path": config_payload["path"],
            "relative_path": config_payload["relative_path"],
            "exists": config_payload["exists"],
            "valid": config_payload["valid"],
            "repo_goal": config_payload["repo_goal"],
            "unknown_policy": config_payload["unknown_policy"],
            "path_contract_count": len(config_payload["path_contracts"]),
            "warnings": config_payload["warnings"],
        },
        "changed_files": normalized_files,
        "files": files,
        "summary": summary,
        "result": summary["result"],
        "warnings": warnings,
        "exit_code": 1 if summary["conflict"] or summary["result"] == "unknown" else 0,
    }


def compact_goal_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": report.get("config", {}),
        "repo_goal": (report.get("config") or {}).get("repo_goal", ""),
        "result": report.get("result"),
        "summary": report.get("summary", {}),
        "files": [
            {
                "path": item.get("path"),
                "state": item.get("state"),
                "area_path": (item.get("area_contract") or {}).get("path"),
                "purpose": (item.get("area_contract") or {}).get("purpose", ""),
            }
            for item in report.get("files", [])
        ],
        "warnings": report.get("warnings", []),
    }


def goal_alignment_from_report(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    if summary.get("conflict"):
        decision = "conflict"
    elif summary.get("unknown") or not report.get("files"):
        decision = "unknown"
    elif summary.get("extends"):
        decision = "adaptation-needed"
    else:
        decision = "aligned"

    area_contracts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in report.get("files", []):
        area = item.get("area_contract")
        if area:
            path = area.get("path") or item.get("path") or "(unknown)"
            raw_status = item.get("state") or area.get("status") or "unknown"
            status = "aligned" if raw_status == "extends" else raw_status
            purpose = area.get("purpose") or "No purpose declared for this area contract."
            source = area.get("source") or (report.get("config") or {}).get("relative_path", CONFIG_FILE)
        else:
            path = item.get("path") or "(unknown)"
            raw_status = "unknown"
            status = "unknown"
            purpose = "No area contract matched this path."
            source = (report.get("config") or {}).get("relative_path", CONFIG_FILE)
        key = (path, status)
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "path": path,
            "purpose": purpose,
            "source": source,
            "status": status,
        }
        if raw_status == "extends":
            entry["notes"] = "Goal-check state is extends; task-packet alignment decision is adaptation-needed."
        area_contracts.append(entry)

    if not area_contracts:
        area_contracts.append(
            {
                "path": "(unknown)",
                "purpose": "No changed files or scope paths were available for deterministic goal-check mapping.",
                "source": (report.get("config") or {}).get("relative_path", CONFIG_FILE),
                "status": "unknown",
            }
        )

    repo_goal = (report.get("config") or {}).get("repo_goal") or "Unknown: no repo goal declared in area-contract config."
    stop_conditions = ["Stop if changed files or area contracts change before implementation handoff."]
    if decision == "conflict":
        stop_conditions.append("Stop and reconcile changed paths that match conflict area contracts.")
    if decision == "unknown":
        stop_conditions.append("Treat unmatched paths as explicit unknowns; do not infer ownership from broad docs.")
    if decision == "adaptation-needed":
        stop_conditions.append("Get approval before treating goal-extending work as aligned implementation scope.")
    return {
        "repo_goal": repo_goal,
        "area_contracts": area_contracts,
        "alignment_decision": decision,
        "adaptation_needed": decision in {"adaptation-needed", "conflict", "unknown"},
        "stop_conditions": stop_conditions,
    }


def render_text(report: dict[str, Any]) -> str:
    config = report.get("config") or {}
    summary = report.get("summary") or {}
    repo_goal = config.get("repo_goal") or "(not declared)"
    lines = [
        "Goal check:",
        f" - repo: {report.get('repo')}",
        f" - config: {config.get('relative_path') or config.get('path')} ({'present' if config.get('exists') else 'missing'})",
        f" - repo goal: {repo_goal}",
        f" - result: {report.get('result')}",
        (
            " - summary: "
            f"aligned {summary.get('aligned', 0)}, "
            f"extends {summary.get('extends', 0)}, "
            f"conflict {summary.get('conflict', 0)}, "
            f"unknown {summary.get('unknown', 0)}"
        ),
    ]
    if not report.get("files"):
        lines.append(" - changed files: none")
    else:
        lines.append(" - changed files:")
        for item in report.get("files", []):
            area = item.get("area_contract") or {}
            area_path = area.get("path") or "no matching area contract"
            purpose = area.get("purpose") or item.get("message", "")
            lines.append(f"   - {item['path']}: {item['state']} ({area_path}) {purpose}".rstrip())
    if report.get("warnings"):
        lines.append(" - warnings:")
        for warning in report["warnings"]:
            lines.append(f"   - {warning}")
    return "\n".join(lines)

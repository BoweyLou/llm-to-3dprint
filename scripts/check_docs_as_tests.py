#!/usr/bin/env python3
"""Run explicitly declared high-confidence documentation assertions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = ".agent-workflows/docs-as-tests.json"
SUPPORTED_ASSERTION_KINDS = {
    "json_key_exists",
    "openapi_operation_exists",
    "openapi_response_status_exists",
    "openapi_schema_property_exists",
}
UNSAFE_TOKENS = ("\x00", "\n", "\r", "`", "$(", ";", "&&", "||", "|", "<", ">")
METHOD_RE = re.compile(r"^[A-Za-z]+$")


def repo_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def is_network_ref(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith(("http://", "https://")) or "://" in lowered


def looks_command_like(value: str) -> bool:
    return any(token in value for token in UNSAFE_TOKENS) or value.strip().startswith("-")


def refusal(
    assertion_id: str,
    code: str,
    message: str,
    *,
    field: str | None = None,
    source_doc_path: str | None = None,
    spec_path: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": assertion_id,
        "code": code,
        "message": message,
    }
    if field:
        item["field"] = field
    if source_doc_path:
        item["source_doc_path"] = source_doc_path
    if spec_path:
        item["spec_path"] = spec_path
    return item


def local_path(
    root: Path,
    raw_value: Any,
    field: str,
    assertion_id: str,
    *,
    must_exist: bool,
    missing_code: str,
) -> tuple[Path | None, dict[str, Any] | None]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, refusal(assertion_id, "missing-path", f"{field} must be a non-empty relative path", field=field)
    value = raw_value.strip()
    if is_network_ref(value):
        return None, refusal(assertion_id, "network-url", f"{field} must be a local path", field=field)
    if looks_command_like(value):
        return None, refusal(assertion_id, "unsafe-input", f"{field} contains command-like input", field=field)
    path = Path(value)
    if path.is_absolute():
        return None, refusal(assertion_id, "unsafe-input", f"{field} must be repo-relative", field=field)
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        return None, refusal(assertion_id, "unsafe-input", f"{field} escapes the repository", field=field)
    if must_exist and not resolved.exists():
        return None, refusal(assertion_id, missing_code, f"{field} does not exist", field=field)
    return resolved, None


def load_json(path: Path, assertion_id: str, field: str, invalid_code: str) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, refusal(assertion_id, invalid_code, f"invalid JSON in {field}: {exc}", field=field)
    except UnicodeDecodeError as exc:
        return None, refusal(assertion_id, invalid_code, f"{field} is not UTF-8 JSON: {exc}", field=field)


def assertion_id(value: Any, index: int) -> tuple[str, dict[str, Any] | None]:
    if not isinstance(value, str) or not value.strip():
        fallback = f"assertion-{index}"
        return fallback, refusal(fallback, "missing-id", "assertion id must be a non-empty string", field="id")
    candidate = value.strip()
    if looks_command_like(candidate):
        return candidate, refusal(candidate, "unsafe-input", "assertion id contains command-like input", field="id")
    return candidate, None


def assertion_identifier(assertion: dict[str, Any], index: int) -> tuple[str, dict[str, Any] | None]:
    return assertion_id(assertion.get("claim_id", assertion.get("id")), index)


def selector(assertion: dict[str, Any], assertion_id_value: str) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    value = assertion.get("selector")
    if value is None and ("method" in assertion or "path" in assertion):
        value = {"method": assertion.get("method"), "path": assertion.get("path")}
    if not isinstance(value, dict):
        return None, refusal(assertion_id_value, "missing-selector", "selector must declare method and path", field="selector")

    keys = set(value)
    required = {"method", "path"}
    if not required.issubset(keys):
        return None, refusal(assertion_id_value, "missing-selector", "selector must include method and path", field="selector")
    if keys != required:
        return None, refusal(assertion_id_value, "ambiguous-selector", "selector must contain only method and path", field="selector")

    method = value.get("method")
    path = value.get("path")
    if not isinstance(method, str) or not method.strip() or not METHOD_RE.fullmatch(method.strip()):
        return None, refusal(assertion_id_value, "missing-selector", "selector.method must be an HTTP method", field="selector.method")
    if looks_command_like(method):
        return None, refusal(assertion_id_value, "unsafe-input", "selector.method contains command-like input", field="selector.method")
    if not isinstance(path, str) or not path.strip() or not path.strip().startswith("/"):
        return None, refusal(assertion_id_value, "missing-selector", "selector.path must be an OpenAPI path", field="selector.path")
    if looks_command_like(path):
        return None, refusal(assertion_id_value, "unsafe-input", "selector.path contains command-like input", field="selector.path")
    if is_network_ref(path):
        return None, refusal(assertion_id_value, "network-url", "selector.path must not be a URL", field="selector.path")
    return {"method": method.strip().upper(), "path": path.strip()}, None


def source_doc_value(assertion: dict[str, Any]) -> Any:
    for key in ("source_doc", "source_doc_path", "doc"):
        if key in assertion:
            value = assertion[key]
            if isinstance(value, dict):
                return value.get("path") or value.get("file")
            return value
    return None


def spec_value(assertion: dict[str, Any]) -> Any:
    for key in ("spec", "spec_path", "artifact_path"):
        if key in assertion:
            return assertion[key]
    evidence = assertion.get("evidence")
    if isinstance(evidence, dict):
        for key in ("spec", "spec_path", "artifact_path", "path"):
            if key in evidence:
                return evidence[key]
    return None


def config_value(assertion: dict[str, Any]) -> Any:
    for key in ("config", "config_path", "artifact_path"):
        if key in assertion:
            return assertion[key]
    evidence = assertion.get("evidence")
    if isinstance(evidence, dict):
        for key in ("config", "config_path", "artifact_path", "path"):
            if key in evidence:
                return evidence[key]
    return None


def expected_value(assertion: dict[str, Any]) -> Any:
    if "expected" in assertion:
        return assertion["expected"]
    if "expected_value" in assertion:
        return assertion["expected_value"]
    return None


def pointer_parts(value: Any) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(part, str) and part for part in value):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    pointer = value.strip()
    if looks_command_like(pointer) or is_network_ref(pointer):
        return None
    if pointer.startswith("#/"):
        pointer = pointer[2:]
    elif pointer.startswith("/"):
        pointer = pointer[1:]
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/") if part]


def get_path_value(payload: Any, parts: list[str]) -> tuple[bool, Any]:
    current = payload
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def source_and_artifact_item(
    *,
    assertion_id_value: str,
    kind: str,
    source_doc_raw: Any,
    artifact_raw: Any,
    artifact_key: str,
) -> dict[str, Any]:
    return {
        "id": assertion_id_value,
        "kind": kind,
        "claim_id": assertion_id_value,
        "source_doc_path": source_doc_raw if isinstance(source_doc_raw, str) else None,
        artifact_key: artifact_raw if isinstance(artifact_raw, str) else None,
        "selector": None,
        "safety_tier": None,
        "result": "refused",
        "failures": [],
        "refusals": [],
    }


def apply_metadata(item: dict[str, Any], assertion: dict[str, Any]) -> None:
    for source_key, target_key in (
        ("safety_tier", "safety_tier"),
        ("confidence", "confidence"),
        ("owner", "owner"),
        ("tags", "tags"),
    ):
        if source_key in assertion:
            item[target_key] = assertion[source_key]


def load_local_artifact(
    root: Path,
    *,
    assertion: dict[str, Any],
    assertion_id_value: str,
    item: dict[str, Any],
    artifact_raw: Any,
    artifact_field: str,
    artifact_key: str,
    missing_code: str,
    invalid_code: str,
    cache: dict[Path, tuple[Any | None, dict[str, Any] | None]],
) -> tuple[Path | None, Any | None, bool]:
    source_doc_raw = source_doc_value(assertion)
    source_doc, source_refusal = local_path(
        root,
        source_doc_raw,
        "source_doc",
        assertion_id_value,
        must_exist=True,
        missing_code="missing-source-doc",
    )
    if source_refusal:
        item["refusals"].append(source_refusal)
        return None, None, False
    item["source_doc_path"] = rel(root, source_doc)

    artifact_path, artifact_refusal = local_path(
        root,
        artifact_raw,
        artifact_field,
        assertion_id_value,
        must_exist=True,
        missing_code=missing_code,
    )
    if artifact_refusal:
        artifact_refusal["source_doc_path"] = item["source_doc_path"]
        item["refusals"].append(artifact_refusal)
        return None, None, False
    item[artifact_key] = rel(root, artifact_path)

    if artifact_path not in cache:
        cache[artifact_path] = load_json(artifact_path, assertion_id_value, artifact_field, invalid_code)
    payload, load_refusal = cache[artifact_path]
    if load_refusal:
        load_refusal["source_doc_path"] = item["source_doc_path"]
        load_refusal[artifact_key] = item[artifact_key]
        item["refusals"].append(load_refusal)
        return artifact_path, None, False
    return artifact_path, payload, True


def evaluate_openapi_operation(
    root: Path,
    assertion: dict[str, Any],
    assertion_id_value: str,
    spec_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]],
) -> dict[str, Any]:
    source_doc_raw = source_doc_value(assertion)
    spec_raw = spec_value(assertion)
    item = source_and_artifact_item(
        assertion_id_value=assertion_id_value,
        kind="openapi_operation_exists",
        source_doc_raw=source_doc_raw,
        artifact_raw=spec_raw,
        artifact_key="spec_path",
    )
    apply_metadata(item, assertion)

    selector_value, selector_refusal = selector(assertion, assertion_id_value)
    if selector_refusal:
        item["refusals"].append(selector_refusal)
        return item
    item["selector"] = selector_value

    _, spec, loaded = load_local_artifact(
        root,
        assertion=assertion,
        assertion_id_value=assertion_id_value,
        item=item,
        artifact_raw=spec_raw,
        artifact_field="spec",
        artifact_key="spec_path",
        missing_code="missing-spec",
        invalid_code="invalid-json",
        cache=spec_cache,
    )
    if not loaded:
        return item
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        item["refusals"].append(
            refusal(
                assertion_id_value,
                "invalid-openapi-spec",
                "spec must be a JSON OpenAPI object with a paths object",
                field="spec",
                source_doc_path=item["source_doc_path"],
                spec_path=item["spec_path"],
            )
        )
        return item

    path_item = spec["paths"].get(selector_value["path"])
    operations = path_item if isinstance(path_item, dict) else {}
    methods = {str(method).lower() for method in operations}
    if selector_value["method"].lower() not in methods:
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "operation-not-found",
                "message": "OpenAPI operation was not found",
                "source_doc_path": item["source_doc_path"],
                "spec_path": item["spec_path"],
                "selector": selector_value,
            }
        )
        return item

    item["result"] = "passed"
    return item


def evaluate_openapi_response_status(
    root: Path,
    assertion: dict[str, Any],
    assertion_id_value: str,
    spec_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]],
) -> dict[str, Any]:
    operation_assertion = dict(assertion)
    if isinstance(assertion.get("selector"), dict):
        operation_assertion["selector"] = {
            "method": assertion["selector"].get("method"),
            "path": assertion["selector"].get("path"),
        }
    item = evaluate_openapi_operation(root, operation_assertion, assertion_id_value, spec_cache)
    item["kind"] = "openapi_response_status_exists"
    if item["result"] != "passed":
        return item
    status = assertion.get("status")
    if status is None and isinstance(assertion.get("selector"), dict):
        status = assertion["selector"].get("status")
    if not isinstance(status, (str, int)) or looks_command_like(str(status)):
        item["result"] = "refused"
        item["refusals"].append(refusal(assertion_id_value, "missing-selector", "status must be declared", field="status"))
        return item
    status_value = str(status).strip()
    spec_path = (root / item["spec_path"]).resolve()
    spec, _ = spec_cache[spec_path]
    selector_value = item["selector"]
    operation = spec["paths"][selector_value["path"]][selector_value["method"].lower()]
    responses = operation.get("responses") if isinstance(operation, dict) else None
    if not isinstance(responses, dict) or status_value not in responses:
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "response-status-not-found",
                "message": "OpenAPI response status was not found",
                "source_doc_path": item["source_doc_path"],
                "spec_path": item["spec_path"],
                "selector": {**selector_value, "status": status_value},
            }
        )
        return item
    item["selector"] = {**selector_value, "status": status_value}
    return item


def evaluate_openapi_schema_property(
    root: Path,
    assertion: dict[str, Any],
    assertion_id_value: str,
    spec_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]],
) -> dict[str, Any]:
    source_doc_raw = source_doc_value(assertion)
    spec_raw = spec_value(assertion)
    item = source_and_artifact_item(
        assertion_id_value=assertion_id_value,
        kind="openapi_schema_property_exists",
        source_doc_raw=source_doc_raw,
        artifact_raw=spec_raw,
        artifact_key="spec_path",
    )
    apply_metadata(item, assertion)
    _, spec, loaded = load_local_artifact(
        root,
        assertion=assertion,
        assertion_id_value=assertion_id_value,
        item=item,
        artifact_raw=spec_raw,
        artifact_field="spec",
        artifact_key="spec_path",
        missing_code="missing-spec",
        invalid_code="invalid-json",
        cache=spec_cache,
    )
    if not loaded:
        return item
    if not isinstance(spec, dict):
        item["refusals"].append(refusal(assertion_id_value, "invalid-openapi-spec", "spec must be a JSON object", field="spec"))
        return item
    raw_selector = assertion.get("selector") if isinstance(assertion.get("selector"), dict) else {}
    schema_ref = assertion.get("schema") or assertion.get("schema_path") or raw_selector.get("schema") or raw_selector.get("schema_path")
    property_name = assertion.get("property") or raw_selector.get("property")
    parts = pointer_parts(schema_ref)
    if parts is None:
        item["refusals"].append(refusal(assertion_id_value, "missing-selector", "schema must be a JSON pointer", field="schema"))
        return item
    if not isinstance(property_name, str) or not property_name.strip() or looks_command_like(property_name):
        item["refusals"].append(refusal(assertion_id_value, "missing-selector", "property must be declared", field="property"))
        return item
    found, schema = get_path_value(spec, parts)
    item["selector"] = {"schema": "#/" + "/".join(parts), "property": property_name.strip()}
    if not found or not isinstance(schema, dict):
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "schema-not-found",
                "message": "OpenAPI schema was not found",
                "source_doc_path": item["source_doc_path"],
                "spec_path": item["spec_path"],
                "selector": item["selector"],
            }
        )
        return item
    properties = schema.get("properties")
    if not isinstance(properties, dict) or property_name.strip() not in properties:
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "schema-property-not-found",
                "message": "OpenAPI schema property was not found",
                "source_doc_path": item["source_doc_path"],
                "spec_path": item["spec_path"],
                "selector": item["selector"],
            }
        )
        return item
    item["result"] = "passed"
    return item


def evaluate_json_key(
    root: Path,
    assertion: dict[str, Any],
    assertion_id_value: str,
    json_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]],
) -> dict[str, Any]:
    source_doc_raw = source_doc_value(assertion)
    config_raw = config_value(assertion)
    item = source_and_artifact_item(
        assertion_id_value=assertion_id_value,
        kind="json_key_exists",
        source_doc_raw=source_doc_raw,
        artifact_raw=config_raw,
        artifact_key="config_path",
    )
    apply_metadata(item, assertion)
    _, payload, loaded = load_local_artifact(
        root,
        assertion=assertion,
        assertion_id_value=assertion_id_value,
        item=item,
        artifact_raw=config_raw,
        artifact_field="config",
        artifact_key="config_path",
        missing_code="missing-config-artifact",
        invalid_code="invalid-json",
        cache=json_cache,
    )
    if not loaded:
        return item
    raw_selector = assertion.get("selector") if isinstance(assertion.get("selector"), dict) else {}
    key_path = assertion.get("key") or assertion.get("path") or raw_selector.get("key") or raw_selector.get("path")
    parts = pointer_parts(key_path)
    if parts is None:
        item["refusals"].append(refusal(assertion_id_value, "missing-selector", "key path must be declared", field="key"))
        return item
    item["selector"] = {"key": "/".join(parts)}
    found, value = get_path_value(payload, parts)
    if not found:
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "json-key-not-found",
                "message": "JSON key was not found",
                "source_doc_path": item["source_doc_path"],
                "config_path": item["config_path"],
                "selector": item["selector"],
            }
        )
        return item
    expected = expected_value(assertion)
    if expected is not None and value != expected:
        item["result"] = "failed"
        item["failures"].append(
            {
                "id": assertion_id_value,
                "code": "json-value-mismatch",
                "message": "JSON key value did not match expected value",
                "source_doc_path": item["source_doc_path"],
                "config_path": item["config_path"],
                "selector": item["selector"],
            }
        )
        return item
    item["result"] = "passed"
    return item


def build_report(args: argparse.Namespace, repo: Path | None = None) -> tuple[dict[str, Any], int]:
    root = repo.resolve() if repo else (Path(args.repo).expanduser().resolve() if args.repo else repo_root())
    config_arg = getattr(args, "config", None) or DEFAULT_CONFIG
    payload: dict[str, Any] = {
        "schema_version": 1,
        "command": "docs-as-tests",
        "repo_root": str(root),
        "config_path": config_arg,
        "target_repo_writes": False,
        "network_used": False,
        "network": {"used": False},
        "assertion_count": 0,
        "assertions": [],
        "failures": [],
        "refusals": [],
        "omissions": [],
        "result": "refused",
    }

    config_path, config_refusal = local_path(
        root,
        config_arg,
        "config",
        "config",
        must_exist=True,
        missing_code="missing-config",
    )
    if config_refusal:
        payload["refusals"].append(config_refusal)
        payload["omissions"].append({"id": "config", "code": config_refusal["code"], "reason": config_refusal["message"]})
        return payload, 2
    payload["config_path"] = rel(root, config_path)

    config, config_load_refusal = load_json(config_path, "config", "config", "invalid-json")
    if config_load_refusal:
        payload["refusals"].append(config_load_refusal)
        payload["omissions"].append({"id": "config", "code": config_load_refusal["code"], "reason": config_load_refusal["message"]})
        return payload, 2
    if not isinstance(config, dict):
        item = refusal("config", "invalid-config", "config must be a JSON object", field="config")
        payload["refusals"].append(item)
        payload["omissions"].append({"id": "config", "code": item["code"], "reason": item["message"]})
        return payload, 2

    assertions = config.get("assertions", [])
    if not isinstance(assertions, list):
        item = refusal("config", "invalid-config", "config assertions must be a list", field="assertions")
        payload["refusals"].append(item)
        payload["omissions"].append({"id": "config", "code": item["code"], "reason": item["message"]})
        return payload, 2

    spec_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]] = {}
    json_cache: dict[Path, tuple[Any | None, dict[str, Any] | None]] = {}
    for index, raw_assertion in enumerate(assertions, start=1):
        if not isinstance(raw_assertion, dict):
            item = {
                "id": f"assertion-{index}",
                "kind": None,
                "source_doc_path": None,
                "spec_path": None,
                "selector": None,
                "result": "refused",
                "failures": [],
                "refusals": [refusal(f"assertion-{index}", "invalid-assertion", "assertion must be a JSON object")],
            }
            payload["assertions"].append(item)
            continue

        assertion_id_value, id_refusal = assertion_identifier(raw_assertion, index)
        if id_refusal:
            item = {
                "id": assertion_id_value,
                "claim_id": assertion_id_value,
                "kind": raw_assertion.get("kind"),
                "source_doc_path": source_doc_value(raw_assertion),
                "spec_path": spec_value(raw_assertion),
                "selector": raw_assertion.get("selector"),
                "result": "refused",
                "failures": [],
                "refusals": [id_refusal],
            }
            payload["assertions"].append(item)
            continue

        if raw_assertion.get("skip") is True or raw_assertion.get("enabled") is False:
            payload["assertions"].append(
                {
                    "id": assertion_id_value,
                    "claim_id": assertion_id_value,
                    "kind": raw_assertion.get("kind"),
                    "source_doc_path": source_doc_value(raw_assertion),
                    "spec_path": spec_value(raw_assertion),
                    "config_path": config_value(raw_assertion),
                    "selector": raw_assertion.get("selector"),
                    "result": "skipped",
                    "skip_reason": raw_assertion.get("skip_reason") or "assertion disabled",
                    "failures": [],
                    "refusals": [],
                }
            )
            continue

        kind = raw_assertion.get("kind")
        if kind not in SUPPORTED_ASSERTION_KINDS:
            item = {
                "id": assertion_id_value,
                "claim_id": assertion_id_value,
                "kind": kind,
                "source_doc_path": source_doc_value(raw_assertion),
                "spec_path": spec_value(raw_assertion),
                "selector": raw_assertion.get("selector"),
                "result": "unsupported",
                "failures": [],
                "refusals": [
                    refusal(
                        assertion_id_value,
                        "unsupported-assertion-kind",
                        f"unsupported assertion kind: {kind}",
                        field="kind",
                    )
                ],
            }
            payload["assertions"].append(item)
            continue

        if kind == "openapi_operation_exists":
            payload["assertions"].append(evaluate_openapi_operation(root, raw_assertion, assertion_id_value, spec_cache))
        elif kind == "openapi_response_status_exists":
            payload["assertions"].append(evaluate_openapi_response_status(root, raw_assertion, assertion_id_value, spec_cache))
        elif kind == "openapi_schema_property_exists":
            payload["assertions"].append(evaluate_openapi_schema_property(root, raw_assertion, assertion_id_value, spec_cache))
        elif kind == "json_key_exists":
            payload["assertions"].append(evaluate_json_key(root, raw_assertion, assertion_id_value, json_cache))

    payload["assertion_count"] = len(payload["assertions"])
    for item in payload["assertions"]:
        payload["failures"].extend(item["failures"])
        payload["refusals"].extend(item["refusals"])
        if item["result"] in {"refused", "unsupported"}:
            for refused in item["refusals"]:
                payload["omissions"].append(
                    {
                        "id": item["id"],
                        "code": refused["code"],
                        "reason": refused["message"],
                        "source_doc_path": item.get("source_doc_path"),
                        "spec_path": item.get("spec_path"),
                        "config_path": item.get("config_path"),
                    }
                )

    if payload["refusals"]:
        payload["result"] = "refused"
        return payload, 2
    if payload["failures"]:
        payload["result"] = "failed"
        return payload, 1
    payload["result"] = "passed"
    return payload, 0


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "Docs as tests:",
        f" - repo: {report['repo_root']}",
        f" - config: {report['config_path']}",
        f" - result: {report['result']}",
        f" - assertions: {report['assertion_count']}",
        f" - target repo writes: {str(report['target_repo_writes']).lower()}",
        f" - network used: {str(report['network_used']).lower()}",
    ]
    for item in report["assertions"]:
        selector_value = item.get("selector") or {}
        selector_text = ""
        if selector_value:
            selector_text = f" {selector_value.get('method')} {selector_value.get('path')}"
        lines.append(
            " - "
            f"{item['id']}: {item['result']} "
            f"{item.get('source_doc_path') or '(no doc)'} -> {item.get('spec_path') or '(no spec)'}"
            f"{selector_text}"
        )
    for failure in report["failures"]:
        selector_value = failure.get("selector") or {}
        lines.append(
            " - failure: "
            f"{failure['id']} {failure['code']} "
            f"{selector_value.get('method', '')} {selector_value.get('path', '')}".rstrip()
        )
    for refused in report["refusals"]:
        lines.append(f" - refusal: {refused['id']} {refused['code']}: {refused['message']}")
    if report["omissions"]:
        lines.append(f" - omissions: {len(report['omissions'])}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run explicit high-confidence docs-as-tests assertions")
    parser.add_argument("--repo", default="", help="Repository root. Defaults to current git root.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Config path relative to repo root. Default: {DEFAULT_CONFIG}")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report, exit_code = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

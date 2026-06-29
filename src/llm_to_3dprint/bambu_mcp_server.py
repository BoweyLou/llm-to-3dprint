from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

from llm_to_3dprint import __version__
from llm_to_3dprint.bambu import (
    DEFAULT_BAMBU_GUI_APP_PATH,
    DEFAULT_BAMBU_GUI_CLICK_BACKEND,
    DEFAULT_BAMBU_GUI_MERGE_CLICK,
    BambuProjectSpec,
    apply_seed_template_3mf,
    build_bambu_handoff,
    build_cli_assemble_payload,
    capture_seed_template_3mf,
    check_seed_template_3mf,
    export_3mf_with_bambu_cli,
    export_3mf_with_bambu_gui,
    format_bambu_cli_export_result,
    format_bambu_gui_export_result,
    format_bambu_hammerspoon_setup_result,
    format_bambu_patch_result,
    format_bambu_probe,
    format_bambu_template_capture_result,
    format_bambu_template_check_result,
    patch_studio_3mf_multicolor,
    probe_bambu_studio,
    setup_hammerspoon_for_bambu,
    write_cli_assemble_list,
)

MCP_PROTOCOL_VERSION = "2025-06-18"
JSONRPC_VERSION = "2.0"
SERVER_NAME = "llm-to-3dprint-bambu"

TOOL_ALIASES = {
    "build_bambu_handoff": "render_bambu_handoff",
    "write_bambu_cli_assemble_list": "build_bambu_cli_assemble_list",
    "patch_bambu_3mf": "patch_bambu_studio_3mf",
}


def _project_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Path to a BambuProjectSpec JSON file.",
            },
            "project": {
                "oneOf": [
                    {"type": "object"},
                    {"type": "string"},
                ],
                "description": "Inline BambuProjectSpec JSON payload, or a string path to a BambuProjectSpec JSON file.",
            },
        },
        "additionalProperties": False,
    }


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "probe_bambu_studio",
            "description": "Inspect the local Bambu Studio install and automation prerequisites.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "app_path": {
                        "type": "string",
                        "description": "Optional override for the Bambu Studio app bundle path.",
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "setup_bambu_hammerspoon",
            "description": "Install the minimal hs.ipc bootstrap block for Hammerspoon, optionally restart Hammerspoon, and verify the repo-managed Bambu actions can be used.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "app_path": {
                        "type": "string",
                        "description": "Optional override for the Bambu Studio app bundle path used during verification.",
                    },
                    "restart": {
                        "type": "boolean",
                        "description": "Whether to restart Hammerspoon after writing the bootstrap block. Defaults to true.",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "validate_bambu_project",
            "description": "Validate a Bambu project spec from an inline payload or a JSON file path.",
            "inputSchema": _project_input_schema(),
        },
        {
            "name": "render_bambu_handoff",
            "description": "Render the human-readable Bambu handoff plan from a validated project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "output": {
                        "type": "string",
                        "description": "Optional output path to also write the rendered handoff text.",
                    },
                },
            },
        },
        {
            "name": "build_bambu_cli_assemble_list",
            "description": "Write the Bambu Studio CLI assemble-list JSON for a validated project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "output": {
                        "type": "string",
                        "description": "Path where the assemble-list JSON should be written.",
                    },
                },
                "required": ["output"],
            },
        },
        {
            "name": "export_bambu_3mf_cli",
            "description": "Attempt a Bambu Studio CLI export to a printer-facing 3MF and report the actual result.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "output_3mf": {
                        "type": "string",
                        "description": "Optional override for the target 3MF output path.",
                    },
                    "assemble_list_output": {
                        "type": "string",
                        "description": "Optional path for the intermediate assemble-list JSON file.",
                    },
                },
            },
        },
        {
            "name": "export_bambu_3mf_gui",
            "description": "Drive the local Bambu Studio GUI to save a grouped in-place multicolor 3MF project.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "output_3mf": {
                        "type": "string",
                        "description": "Optional override for the target 3MF output path.",
                    },
                    "app_path": {
                        "type": "string",
                        "description": "Optional override for the Bambu Studio app bundle path.",
                    },
                    "merge_click_x": {
                        "type": "integer",
                        "description": "Screen X coordinate for the multipart merge confirmation click.",
                    },
                    "merge_click_y": {
                        "type": "integer",
                        "description": "Screen Y coordinate for the multipart merge confirmation click.",
                    },
                    "import_timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the import flow to settle.",
                    },
                    "save_timeout": {
                        "type": "number",
                        "description": "Seconds to wait for the save flow to complete.",
                    },
                    "click_backend": {
                        "type": "string",
                        "description": "Optional click backend for merge confirmation: auto, swift, or hammerspoon.",
                    },
                },
            },
        },
        {
            "name": "patch_bambu_studio_3mf",
            "description": "Patch a Studio-authored 3MF with the multicolor metadata defined by a Bambu project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "input_3mf": {
                        "type": "string",
                        "description": "Path to the Studio-authored 3MF file to patch.",
                    },
                    "output_3mf": {
                        "type": "string",
                        "description": "Path where the patched 3MF should be written.",
                    },
                },
                "required": ["input_3mf", "output_3mf"],
            },
        },
        {
            "name": "apply_bambu_seed_template",
            "description": "Patch a known-good seed Bambu Studio 3MF template into a fresh output using a Bambu project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "seed_template_3mf": {
                        "type": "string",
                        "description": "Optional override path for the seed Bambu Studio 3MF template.",
                    },
                    "output_3mf": {
                        "type": "string",
                        "description": "Optional override path for the final patched 3MF output.",
                    },
                },
            },
        },
        {
            "name": "check_bambu_seed_template",
            "description": "Validate that a Studio-authored seed 3MF contains the expected in-place multicolor objects for a Bambu project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "seed_template_3mf": {
                        "type": "string",
                        "description": "Optional override path for the seed Bambu Studio 3MF template.",
                    },
                },
            },
        },
        {
            "name": "capture_bambu_seed_template",
            "description": "Validate and copy a Studio-authored 3MF into the seed-template path for a Bambu project spec.",
            "inputSchema": {
                **_project_input_schema(),
                "properties": {
                    **_project_input_schema()["properties"],
                    "input_3mf": {
                        "type": "string",
                        "description": "Path to the Studio-authored 3MF file to capture.",
                    },
                    "output_3mf": {
                        "type": "string",
                        "description": "Optional override path for the captured seed template.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Allow overwriting an existing captured seed template.",
                    },
                },
                "required": ["input_3mf"],
            },
        },
    ]


def _server_info() -> dict[str, Any]:
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False},
            "prompts": {"listChanged": False},
        },
        "serverInfo": {"name": SERVER_NAME, "version": __version__},
        "instructions": (
            "Use this server to validate BambuProjectSpec files, write assemble-list JSON, "
            "drive Bambu Studio CLI or GUI exports, patch Studio-authored multicolor 3MF projects, "
            "validate or capture seed templates, populate a fresh output from a seed Bambu Studio template, "
            "or retrieve local workflow resources and prompts for design validation and review."
        ),
    }


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}


def _tool_success(text: str, structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured,
        "isError": False,
    }


def _tool_error(message: str, *, structured: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "structuredContent": structured or {"error": message},
        "isError": True,
    }


def _load_project_spec(arguments: dict[str, Any]) -> BambuProjectSpec:
    project_payload = arguments.get("project")
    project_path = arguments.get("project_path")
    if project_payload is not None:
        if isinstance(project_payload, str):
            return BambuProjectSpec.load(project_payload)
        if not isinstance(project_payload, dict):
            raise ValueError("project must be a JSON object or string path when provided")
        return BambuProjectSpec.from_dict(project_payload)
    if project_path is not None:
        if not isinstance(project_path, str) or not project_path:
            raise ValueError("project_path must be a non-empty string when provided")
        return BambuProjectSpec.load(project_path)
    raise ValueError("Provide either project or project_path")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resource_definitions() -> list[dict[str, Any]]:
    return [
        {
            "uri": "llm-to-3dprint://docs/backlog",
            "name": "CAD and printer workflow backlog",
            "mimeType": "text/markdown",
            "description": "Repo-local backlog mirror for CAD, Blender, MCP, and governance work.",
        },
        {
            "uri": "llm-to-3dprint://docs/geometry-recipes",
            "name": "Geometry recipes and shape contracts",
            "mimeType": "text/markdown",
            "description": "Local printable-shape recipes and validation expectations.",
        },
        {
            "uri": "llm-to-3dprint://examples/rectangular-brief",
            "name": "Starter rectangular enclosure brief",
            "mimeType": "application/json",
            "description": "Example DesignBrief payload for the local starter renderer.",
        },
        {
            "uri": "llm-to-3dprint://examples/bambu-a1-handoff",
            "name": "Bambu A1 handoff example",
            "mimeType": "application/json",
            "description": "Example BambuProjectSpec payload for printer-facing handoff work.",
        },
    ]


def _resource_paths() -> dict[str, Path]:
    root = _repo_root()
    return {
        "llm-to-3dprint://docs/backlog": root / "docs" / "backlog.md",
        "llm-to-3dprint://docs/geometry-recipes": root / "docs" / "geometry-recipes.md",
        "llm-to-3dprint://examples/rectangular-brief": root / "examples" / "rectangular_enclosure.json",
        "llm-to-3dprint://examples/bambu-a1-handoff": root / "examples" / "bambu_a1_hybrid_project.json",
    }


def _read_resource(uri: str) -> dict[str, Any]:
    path = _resource_paths().get(uri)
    if path is None:
        raise ValueError(f"Unknown resource URI: {uri}")
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": next(
                    resource["mimeType"]
                    for resource in _resource_definitions()
                    if resource["uri"] == uri
                ),
                "text": path.read_text(),
            }
        ]
    }


def _prompt_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "review_generated_part",
            "description": "Review a generated CAD, STL, STEP, 3MF, or Blender artifact set before printing.",
            "arguments": [
                {"name": "artifact_path", "description": "Path to the generated artifact or review report.", "required": True},
                {"name": "brief_path", "description": "Optional DesignBrief path for intent checks.", "required": False},
            ],
        },
        {
            "name": "prepare_bambu_handoff",
            "description": "Prepare a Bambu Studio handoff review from a project spec and generated artifacts.",
            "arguments": [
                {"name": "project_path", "description": "Path to a BambuProjectSpec JSON file.", "required": True},
            ],
        },
        {
            "name": "validate_design_contract",
            "description": "Validate a DesignBrief before CAD generation and summarize missing contract fields.",
            "arguments": [
                {"name": "brief_path", "description": "Path to a DesignBrief JSON file.", "required": True},
            ],
        },
    ]


def _prompt_messages(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "review_generated_part":
        artifact_path = arguments.get("artifact_path", "<artifact-path>")
        brief_path = arguments.get("brief_path")
        brief_line = f"\n- Brief: `{brief_path}`" if brief_path else ""
        return {
            "description": "Generated part review prompt",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Review the generated part before printing.\n"
                            f"- Artifact or report: `{artifact_path}`{brief_line}\n"
                            "- Check design intent, dimensions, bed fit, geometry health, preview artifacts, and Bambu handoff risks.\n"
                            "- Return blockers first, then concrete next commands."
                        ),
                    },
                }
            ],
        }
    if name == "prepare_bambu_handoff":
        project_path = arguments.get("project_path", "<project-path>")
        return {
            "description": "Bambu handoff preparation prompt",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Prepare the Bambu handoff for printing.\n"
                            f"- Project spec: `{project_path}`\n"
                            "- Validate the spec, validate referenced artifacts, render the handoff, and note whether final 3MF creation needs Studio GUI, CLI, template patching, or manual review."
                        ),
                    },
                }
            ],
        }
    if name == "validate_design_contract":
        brief_path = arguments.get("brief_path", "<brief-path>")
        return {
            "description": "Design-contract validation prompt",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Validate this DesignBrief before CAD generation.\n"
                            f"- Brief: `{brief_path}`\n"
                            "- Run validate-design, inspect missing silhouette/symmetry/cross-section/forbidden-feature fields, and recommend only contract-level fixes before code generation."
                        ),
                    },
                }
            ],
        }
    raise ValueError(f"Unknown prompt: {name}")


def call_mcp_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    name = TOOL_ALIASES.get(name, name)
    payload = arguments or {}
    try:
        if name == "probe_bambu_studio":
            app_path = payload.get("app_path", DEFAULT_BAMBU_GUI_APP_PATH)
            if not isinstance(app_path, str):
                raise ValueError("app_path must be a string when provided")
            probe = probe_bambu_studio(app_path)
            return _tool_success(format_bambu_probe(probe).strip(), asdict(probe))

        if name == "setup_bambu_hammerspoon":
            app_path = payload.get("app_path", DEFAULT_BAMBU_GUI_APP_PATH)
            restart = payload.get("restart", True)
            if not isinstance(app_path, str):
                raise ValueError("app_path must be a string when provided")
            if not isinstance(restart, bool):
                raise ValueError("restart must be a boolean when provided")
            result = setup_hammerspoon_for_bambu(app_path=app_path, restart=restart)
            return _tool_success(format_bambu_hammerspoon_setup_result(result).strip(), asdict(result))

        if name == "validate_bambu_project":
            spec = _load_project_spec(payload)
            grouped_objects = sorted(spec.grouped_objects())
            return _tool_success(
                (
                    f"Validated {spec.name}: printer={spec.target_printer}, "
                    f"filaments={spec.filament_count}, parts={len(spec.parts)}, "
                    f"grouped_objects={','.join(grouped_objects) or 'none'}"
                ),
                {
                    "valid": True,
                    "name": spec.name,
                    "target_printer": spec.target_printer,
                    "nozzle_diameter": spec.nozzle_diameter,
                    "filament_count": spec.filament_count,
                    "part_count": len(spec.parts),
                    "export_backend": spec.export_backend,
                    "grouped_objects": grouped_objects,
                    "project": spec.to_dict(),
                },
            )

        if name == "render_bambu_handoff":
            spec = _load_project_spec(payload)
            handoff = build_bambu_handoff(spec)
            output = payload.get("output")
            if output is not None:
                if not isinstance(output, str) or not output:
                    raise ValueError("output must be a non-empty string when provided")
                destination = Path(output)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(handoff)
            return _tool_success(
                handoff,
                {"handoff": handoff, "project_name": spec.name, "output": output},
            )

        if name == "build_bambu_cli_assemble_list":
            spec = _load_project_spec(payload)
            output = payload.get("output")
            if not isinstance(output, str) or not output:
                raise ValueError("output is required and must be a non-empty string")
            destination = write_cli_assemble_list(spec, output)
            return _tool_success(
                f"Wrote Bambu CLI assemble list to {destination}",
                {
                    "output": str(destination),
                    "payload": build_cli_assemble_payload(spec),
                },
            )

        if name == "export_bambu_3mf_cli":
            spec = _load_project_spec(payload)
            result = export_3mf_with_bambu_cli(
                spec,
                output_3mf=payload.get("output_3mf"),
                assemble_list_path=payload.get("assemble_list_output"),
            )
            return _tool_success(format_bambu_cli_export_result(result).strip(), asdict(result))

        if name == "export_bambu_3mf_gui":
            spec = _load_project_spec(payload)
            merge_x = payload.get("merge_click_x", DEFAULT_BAMBU_GUI_MERGE_CLICK[0])
            merge_y = payload.get("merge_click_y", DEFAULT_BAMBU_GUI_MERGE_CLICK[1])
            if not isinstance(merge_x, int) or not isinstance(merge_y, int):
                raise ValueError("merge_click_x and merge_click_y must be integers")
            click_backend = payload.get("click_backend", DEFAULT_BAMBU_GUI_CLICK_BACKEND)
            if not isinstance(click_backend, str) or not click_backend:
                raise ValueError("click_backend must be a non-empty string when provided")
            result = export_3mf_with_bambu_gui(
                spec,
                output_3mf=payload.get("output_3mf"),
                app_path=payload.get("app_path", DEFAULT_BAMBU_GUI_APP_PATH),
                merge_click=(merge_x, merge_y),
                click_backend=click_backend,
                import_timeout=float(payload.get("import_timeout", 30.0)),
                save_timeout=float(payload.get("save_timeout", 30.0)),
            )
            return _tool_success(format_bambu_gui_export_result(result).strip(), asdict(result))

        if name == "patch_bambu_studio_3mf":
            spec = _load_project_spec(payload)
            input_3mf = payload.get("input_3mf")
            output_3mf = payload.get("output_3mf")
            if not isinstance(input_3mf, str) or not input_3mf:
                raise ValueError("input_3mf is required and must be a non-empty string")
            if not isinstance(output_3mf, str) or not output_3mf:
                raise ValueError("output_3mf is required and must be a non-empty string")
            result = patch_studio_3mf_multicolor(spec, input_3mf, output_3mf=output_3mf)
            return _tool_success(format_bambu_patch_result(result).strip(), asdict(result))

        if name == "apply_bambu_seed_template":
            spec = _load_project_spec(payload)
            seed_template_3mf = payload.get("seed_template_3mf")
            output_3mf = payload.get("output_3mf")
            if seed_template_3mf is not None and (
                not isinstance(seed_template_3mf, str) or not seed_template_3mf
            ):
                raise ValueError("seed_template_3mf must be a non-empty string when provided")
            if output_3mf is not None and (not isinstance(output_3mf, str) or not output_3mf):
                raise ValueError("output_3mf must be a non-empty string when provided")
            result = apply_seed_template_3mf(
                spec,
                output_3mf=output_3mf,
                seed_template_3mf=seed_template_3mf,
            )
            return _tool_success(format_bambu_patch_result(result).strip(), asdict(result))

        if name == "check_bambu_seed_template":
            spec = _load_project_spec(payload)
            seed_template_3mf = payload.get("seed_template_3mf")
            if seed_template_3mf is not None and (
                not isinstance(seed_template_3mf, str) or not seed_template_3mf
            ):
                raise ValueError("seed_template_3mf must be a non-empty string when provided")
            result = check_seed_template_3mf(spec, seed_template_3mf=seed_template_3mf)
            return _tool_success(format_bambu_template_check_result(result).strip(), asdict(result))

        if name == "capture_bambu_seed_template":
            spec = _load_project_spec(payload)
            input_3mf = payload.get("input_3mf")
            output_3mf = payload.get("output_3mf")
            overwrite = payload.get("overwrite", False)
            if not isinstance(input_3mf, str) or not input_3mf:
                raise ValueError("input_3mf is required and must be a non-empty string")
            if output_3mf is not None and (not isinstance(output_3mf, str) or not output_3mf):
                raise ValueError("output_3mf must be a non-empty string when provided")
            if not isinstance(overwrite, bool):
                raise ValueError("overwrite must be a boolean when provided")
            result = capture_seed_template_3mf(
                spec,
                input_3mf,
                output_3mf=output_3mf,
                overwrite=overwrite,
            )
            return _tool_success(format_bambu_template_capture_result(result).strip(), asdict(result))
    except Exception as exc:
        return _tool_error(str(exc), structured={"tool": name, "error": str(exc)})

    return _tool_error(f"Unknown tool: {name}", structured={"tool": name, "error": "unknown_tool"})


def handle_mcp_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if method in {"notifications/initialized", "initialized", "$/cancelRequest"}:
        return None

    if method == "initialize":
        result = _server_info()
        client_protocol = params.get("protocolVersion")
        if isinstance(client_protocol, str) and client_protocol:
            result = {**result, "protocolVersion": client_protocol}
        return _jsonrpc_result(request_id, result)

    if method == "ping":
        return _jsonrpc_result(request_id, {})

    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": _tool_definitions()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(request_id, -32602, "tools/call requires a tool name")
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "tools/call arguments must be an object")
        return _jsonrpc_result(request_id, call_mcp_tool(name, arguments))

    if method == "resources/list":
        return _jsonrpc_result(request_id, {"resources": _resource_definitions()})

    if method == "resources/read":
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            return _jsonrpc_error(request_id, -32602, "resources/read requires a resource URI")
        try:
            return _jsonrpc_result(request_id, _read_resource(uri))
        except Exception as exc:
            return _jsonrpc_error(request_id, -32602, str(exc))

    if method == "prompts/list":
        return _jsonrpc_result(request_id, {"prompts": _prompt_definitions()})

    if method == "prompts/get":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(request_id, -32602, "prompts/get requires a prompt name")
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "prompts/get arguments must be an object")
        try:
            return _jsonrpc_result(request_id, _prompt_messages(name, arguments))
        except Exception as exc:
            return _jsonrpc_error(request_id, -32602, str(exc))

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def serve_stdio() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _jsonrpc_error(None, -32700, f"Invalid JSON: {exc.msg}")
        else:
            response = handle_mcp_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


def main() -> None:
    raise SystemExit(serve_stdio())


if __name__ == "__main__":
    main()

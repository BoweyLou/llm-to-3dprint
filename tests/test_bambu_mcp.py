from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

from llm_to_3dprint.bambu import BambuHammerspoonSetupResult, BambuStudioProbe
from llm_to_3dprint.bambu_mcp import run_messages
import llm_to_3dprint.bambu_mcp_server as bambu_mcp_server


def make_project_payload(root: Path) -> dict:
    return {
        "name": "retro_a1_project",
        "description": "Hybrid two-color A1 handoff.",
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "ams_lite",
        "filament_count": 2,
        "export_backend": "bambu_studio_gui",
        "output_3mf": str(root / "generated" / "output" / "retro_a1.3mf"),
        "parts": [
            {
                "name": "lid_shell",
                "path": str(root / "generated" / "output" / "lid_shell.step"),
                "object_name": "retro_lid",
                "part_name": "lid_shell",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 1,
            },
            {
                "name": "lid_inserts",
                "path": str(root / "generated" / "output" / "lid_inserts.step"),
                "object_name": "retro_lid",
                "part_name": "lid_inserts",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 2,
            },
        ],
    }


def make_patch_project_payload(root: Path) -> dict:
    return {
        "name": "retro_a1_patch_project",
        "description": "Studio-authored 3MF patch workflow for a two-filament lid.",
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "ams_lite",
        "filament_count": 2,
        "export_backend": "bambu_studio_gui",
        "output_3mf": str(root / "generated" / "output" / "retro_a1_patch.3mf"),
        "seed_template_3mf": str(root / "seed-template.3mf"),
        "parts": [
            {
                "name": "lid_shell",
                "path": str(root / "lid_shell.stl"),
                "object_name": "retro_lid",
                "part_name": "lid_shell",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 1,
            },
            {
                "name": "lid_inserts",
                "path": str(root / "lid_inserts.stl"),
                "object_name": "retro_lid",
                "part_name": "lid_inserts",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 2,
            },
        ],
    }


def write_studio_3mf_fixture(path: Path) -> Path:
    project_settings = {
        "nozzle_diameter": [0.4],
        "filament_colour": ["#FFFF00"],
        "filament_multi_colour": ["#FFFF00"],
        "filament_colour_type": ["1"],
        "filament_ids": ["GFL99"],
        "filament_type": ["PLA"],
        "filament_vendor": ["Generic"],
        "filament_settings_id": ["Generic PLA @BBL A1"],
        "filament_extruder_variant": ["Direct Drive Standard"],
        "filament_self_index": ["1"],
        "filament_map": ["1"],
        "filament_nozzle_map": ["0"],
        "filament_volume_map": ["0"],
        "filament_adhesiveness_category": ["100"],
        "filament_prime_volume": ["45"],
        "flush_volumes_vector": ["140"],
        "flush_volumes_matrix": ["0"],
        "flush_multiplier": [1],
        "extruder_colour": ["#FFFF00"],
        "extruder_offset": [0],
        "default_filament_profile": ["Generic PLA @BBL A1"],
        "filament_map_mode": "Auto For Flush",
    }
    model_root = ET.fromstring(
        """
        <model>
          <object id="1">
            <metadata key="name" value="lid_shell" />
            <part id="1">
              <metadata key="source_file" value="generated/output/lid_shell.stl" />
            </part>
          </object>
          <object id="2">
            <metadata key="name" value="lid_inserts" />
            <part id="2">
              <metadata key="source_file" value="generated/output/lid_inserts.stl" />
            </part>
          </object>
        </model>
        """
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Metadata/project_settings.config", json.dumps(project_settings, indent=4) + "\n")
        archive.writestr(
            "Metadata/model_settings.config",
            ET.tostring(model_root, encoding="unicode"),
        )
        archive.writestr("3D/dummy.txt", "placeholder\n")
    return path


def test_mcp_initialize_and_tools_list() -> None:
    responses = run_messages(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
    )

    assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
    assert responses[0]["result"]["capabilities"] == {"tools": {"listChanged": False}}
    tool_names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert "validate_bambu_project" in tool_names
    assert "export_bambu_3mf_gui" in tool_names
    assert "patch_bambu_studio_3mf" in tool_names
    assert "apply_bambu_seed_template" in tool_names
    assert "check_bambu_seed_template" in tool_names
    assert "capture_bambu_seed_template" in tool_names
    assert "setup_bambu_hammerspoon" in tool_names


def test_mcp_validate_and_build_assemble_list(tmp_path: Path) -> None:
    output_root = tmp_path / "generated" / "output"
    output_root.mkdir(parents=True)
    for name in ("lid_shell.step", "lid_shell.stl", "lid_inserts.step", "lid_inserts.stl"):
        (output_root / name).write_text("solid test\nendsolid test\n")

    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps(make_project_payload(tmp_path), indent=2) + "\n")
    assemble_path = tmp_path / "assemble.json"

    responses = run_messages(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "validate_bambu_project", "arguments": {"project": str(project_path)}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "build_bambu_cli_assemble_list", "arguments": {"project": str(project_path), "output": str(assemble_path)}}},
        ]
    )

    validate_result = responses[1]["result"]
    assert validate_result["structuredContent"]["target_printer"] == "A1"
    assert validate_result["structuredContent"]["grouped_objects"] == ["retro_lid"]

    build_result = responses[2]["result"]
    assert assemble_path.exists()
    assert build_result["structuredContent"]["output"] == str(assemble_path)
    payload = build_result["structuredContent"]["payload"]
    assert payload["plates"][0]["objects"][0]["path"].endswith("lid_shell.stl")
    assert payload["plates"][0]["objects"][1]["path"].endswith("lid_inserts.stl")


def test_mcp_tool_errors_return_is_error(tmp_path: Path) -> None:
    responses = run_messages(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "patch_bambu_studio_3mf", "arguments": {"project": str(tmp_path / "missing.json"), "input_3mf": "in.3mf", "output_3mf": "out.3mf"}}},
        ]
    )

    result = responses[1]["result"]
    assert result["isError"] is True
    assert "missing.json" in result["content"][0]["text"]


def test_mcp_apply_seed_template_tool(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    write_studio_3mf_fixture(tmp_path / "seed-template.3mf")
    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps(make_patch_project_payload(tmp_path), indent=2) + "\n")
    output_3mf = tmp_path / "patched-template.3mf"

    responses = run_messages(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "apply_bambu_seed_template",
                    "arguments": {"project_path": str(project_path), "output_3mf": str(output_3mf)},
                },
            },
        ]
    )

    result = responses[1]["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["output_3mf"] == str(output_3mf.resolve())
    assert output_3mf.exists()


def test_mcp_check_and_capture_seed_template_tools(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    input_3mf = write_studio_3mf_fixture(tmp_path / "input-template.3mf")
    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps(make_patch_project_payload(tmp_path), indent=2) + "\n")
    captured_3mf = tmp_path / "captured-template.3mf"

    responses = run_messages(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "check_bambu_seed_template",
                    "arguments": {"project_path": str(project_path), "seed_template_3mf": str(input_3mf)},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "capture_bambu_seed_template",
                    "arguments": {
                        "project_path": str(project_path),
                        "input_3mf": str(input_3mf),
                        "output_3mf": str(captured_3mf),
                    },
                },
            },
        ]
    )

    check_result = responses[1]["result"]
    capture_result = responses[2]["result"]
    assert check_result["isError"] is False
    assert check_result["structuredContent"]["matched_patchable_objects"] == [
        "lid_shell.stl",
        "lid_inserts.stl",
    ]
    assert capture_result["isError"] is False
    assert capture_result["structuredContent"]["output_3mf"] == str(captured_3mf.resolve())
    assert captured_3mf.exists()


def test_mcp_setup_hammerspoon_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        bambu_mcp_server,
        "setup_hammerspoon_for_bambu",
        lambda app_path, restart: BambuHammerspoonSetupResult(
            init_path="/Users/test/.hammerspoon/init.lua",
            actions_path="/tmp/bambu_hammerspoon.lua",
            init_existed=False,
            init_written=True,
            restart_requested=restart,
            restart_succeeded=True,
            probe=BambuStudioProbe(
                installed=True,
                app_path=app_path,
                executable_path="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
                support_dir="/tmp/bambu",
                version="02.05.00.66",
                cli_available=True,
                assistive_access=True,
                assistive_access_error=None,
                hammerspoon_cli_path="/opt/homebrew/bin/hs",
                hammerspoon_cli_available=True,
                hammerspoon_ipc_ready=True,
                hammerspoon_error=None,
            ),
            error_text=None,
            notes=["ok"],
        ),
    )

    responses = run_messages(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1"}}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "setup_bambu_hammerspoon", "arguments": {"restart": False}},
            },
        ]
    )

    result = responses[1]["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["init_written"] is True


def test_mcp_module_stdio_smoke() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    process = subprocess.Popen(
        [sys.executable, "-m", "llm_to_3dprint.bambu_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "1"},
                    },
                }
            )
            + "\n"
        )
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["serverInfo"]["name"] == "llm-to-3dprint-bambu"

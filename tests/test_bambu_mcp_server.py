from __future__ import annotations

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from llm_to_3dprint.bambu import BambuGuiExportResult
from llm_to_3dprint.bambu_mcp_server import call_mcp_tool, handle_mcp_request


def make_project_payload(root: Path | None = None) -> dict:
    prefix = root or Path("generated/output")
    return {
        "name": "retro_a1_project",
        "description": "Hybrid two-color A1 handoff.",
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "ams_lite",
        "filament_count": 2,
        "export_backend": "bambu_studio_mcp",
        "output_3mf": str(prefix / "retro_a1.3mf"),
        "parts": [
            {
                "name": "lid_shell",
                "path": str(prefix / "lid_shell.stl"),
                "object_name": "retro_lid",
                "part_name": "lid_shell",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 1,
            },
            {
                "name": "lid_inserts",
                "path": str(prefix / "lid_inserts.stl"),
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


def test_initialize_reports_tools_capability() -> None:
    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26"},
        }
    )

    assert response is not None
    assert response["result"]["protocolVersion"] == "2025-03-26"
    assert response["result"]["capabilities"]["tools"]["listChanged"] is False


def test_tools_list_contains_expected_names() -> None:
    response = handle_mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert response is not None
    names = [tool["name"] for tool in response["result"]["tools"]]
    assert names == [
        "probe_bambu_studio",
        "setup_bambu_hammerspoon",
        "validate_bambu_project",
        "render_bambu_handoff",
        "build_bambu_cli_assemble_list",
        "export_bambu_3mf_cli",
        "export_bambu_3mf_gui",
        "patch_bambu_studio_3mf",
        "apply_bambu_seed_template",
        "check_bambu_seed_template",
        "capture_bambu_seed_template",
    ]


def test_validate_tool_accepts_inline_project(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    result = call_mcp_tool("validate_bambu_project", {"project": make_project_payload(tmp_path)})

    assert result["isError"] is False
    assert result["structuredContent"]["valid"] is True
    assert result["structuredContent"]["grouped_objects"] == ["retro_lid"]


def test_patch_tool_accepts_project_path(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps(make_project_payload(tmp_path), indent=2) + "\n")
    input_3mf = write_studio_3mf_fixture(tmp_path / "input.3mf")
    output_3mf = tmp_path / "patched.3mf"

    result = call_mcp_tool(
        "patch_bambu_studio_3mf",
        {
            "project_path": str(project_path),
            "input_3mf": str(input_3mf),
            "output_3mf": str(output_3mf),
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["output_exists"] is True
    assert output_3mf.exists()


def test_legacy_patch_tool_alias_still_works(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps(make_project_payload(tmp_path), indent=2) + "\n")
    input_3mf = write_studio_3mf_fixture(tmp_path / "input.3mf")
    output_3mf = tmp_path / "patched.3mf"

    result = call_mcp_tool(
        "patch_bambu_3mf",
        {
            "project_path": str(project_path),
            "input_3mf": str(input_3mf),
            "output_3mf": str(output_3mf),
        },
    )

    assert result["isError"] is False
    assert output_3mf.exists()


def test_export_gui_tool_passes_merge_click_overrides(tmp_path: Path, monkeypatch) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    captured: dict[str, object] = {}

    def fake_export(spec, **kwargs):
        captured["spec_name"] = spec.name
        captured.update(kwargs)
        return BambuGuiExportResult(
            command=["open"],
            output_3mf=str(tmp_path / "out.3mf"),
            import_paths=[str(tmp_path / "lid_shell.stl"), str(tmp_path / "lid_inserts.stl")],
            launch_returncode=0,
            stdout="",
            stderr="",
            output_exists=True,
            merge_dialog_clicked=True,
            save_panel_handled=True,
            error_text=None,
            notes=["ok"],
        )

    monkeypatch.setattr("llm_to_3dprint.bambu_mcp_server.export_3mf_with_bambu_gui", fake_export)

    result = call_mcp_tool(
        "export_bambu_3mf_gui",
        {
            "project": make_project_payload(tmp_path),
            "output_3mf": str(tmp_path / "out.3mf"),
            "merge_click_x": 100,
            "merge_click_y": 200,
            "import_timeout": 12,
            "save_timeout": 34,
        },
    )

    assert result["isError"] is False
    assert captured["spec_name"] == "retro_a1_project"
    assert captured["merge_click"] == (100, 200)
    assert captured["import_timeout"] == 12.0
    assert captured["save_timeout"] == 34.0


def test_mcp_resources_and_prompts_are_exposed() -> None:
    resources = handle_mcp_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
    prompts = handle_mcp_request({"jsonrpc": "2.0", "id": 4, "method": "prompts/list"})

    assert resources is not None
    assert "llm-to-3dprint://docs/backlog" in [
        resource["uri"] for resource in resources["result"]["resources"]
    ]
    assert prompts is not None
    assert "review_generated_part" in [prompt["name"] for prompt in prompts["result"]["prompts"]]


def test_mcp_resource_read_returns_backlog_text() -> None:
    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {"uri": "llm-to-3dprint://docs/backlog"},
        }
    )

    assert response is not None
    assert "Backlog" in response["result"]["contents"][0]["text"]


def test_mcp_prompt_get_returns_review_prompt() -> None:
    response = handle_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "prompts/get",
            "params": {
                "name": "review_generated_part",
                "arguments": {"artifact_path": "generated/output/part.stl"},
            },
        }
    )

    assert response is not None
    text = response["result"]["messages"][0]["content"]["text"]
    assert "generated/output/part.stl" in text
    assert "bed fit" in text

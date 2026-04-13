from __future__ import annotations

import json
import plistlib
from subprocess import CompletedProcess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from llm_to_3dprint.cli import main as cli_main
from llm_to_3dprint.bambu import (
    BambuCliExportResult,
    BambuGuiExportResult,
    BambuPresetBundle,
    BambuProjectSpec,
    BambuStudio3mfPatchResult,
    BambuStudioProbe,
    apply_seed_template_3mf,
    build_bambu_handoff,
    build_cli_assemble_payload,
    build_gui_import_paths,
    build_gui_launch_command,
    capture_seed_template_3mf,
    check_seed_template_3mf,
    export_3mf_with_bambu_gui,
    format_bambu_cli_export_result,
    format_bambu_gui_export_result,
    format_bambu_hammerspoon_setup_result,
    format_bambu_patch_result,
    format_bambu_template_capture_result,
    format_bambu_template_check_result,
    _dismiss_bambu_unsaved_changes_dialog,
    _resolve_gui_click_backend,
    _bambu_import_ready,
    probe_bambu_studio,
    preset_a1_hybrid_two_color,
    patch_studio_3mf_multicolor,
    repo_hammerspoon_actions_path,
    resolve_cli_mesh_path,
    resolve_gui_import_path,
    setup_hammerspoon_for_bambu,
    write_cli_assemble_list,
)


def make_project_payload() -> dict:
    return {
        "name": "retro_a1_project",
        "description": "Hybrid two-color A1 handoff.",
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "ams_lite",
        "filament_count": 2,
        "export_backend": "bambu_studio_gui",
        "output_3mf": "generated/output/retro_a1.3mf",
        "parts": [
            {
                "name": "lid_shell",
                "path": "generated/output/lid_shell.step",
                "object_name": "retro_lid",
                "part_name": "lid_shell",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 1,
            },
            {
                "name": "lid_inserts",
                "path": "generated/output/lid_inserts.step",
                "object_name": "retro_lid",
                "part_name": "lid_inserts",
                "load_strategy": "merge_as_parts",
                "print_mode": "in_place_multicolor",
                "plate": 1,
                "filament": 2,
            },
            {
                "name": "lid_accent",
                "path": "generated/output/lid_accent.stl",
                "load_strategy": "separate_object",
                "print_mode": "side_by_side_accent",
                "plate": 1,
                "filament": 2,
            },
            {
                "name": "base",
                "path": "generated/output/base.stl",
                "load_strategy": "separate_object",
                "print_mode": "standalone",
                "plate": 2,
                "filament": 1,
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
        "output_3mf": "generated/output/retro_a1_patch.3mf",
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


def write_grouped_studio_3mf_fixture(path: Path) -> Path:
    project_settings = {
        "nozzle_diameter": [0.4],
        "filament_colour": ["#FFFF00", "#FF6A00"],
        "filament_multi_colour": ["#FFFF00", "#FF6A00"],
        "filament_colour_type": ["1", "1"],
        "filament_ids": ["GFL99", "GFL99"],
        "filament_type": ["PLA", "PLA"],
        "filament_vendor": ["Generic", "Generic"],
        "filament_settings_id": ["Generic PLA @BBL A1", "Generic PLA @BBL A1"],
        "filament_extruder_variant": ["Direct Drive Standard", "Direct Drive Standard"],
        "filament_self_index": ["1", "2"],
        "filament_map": ["1", "1"],
        "filament_nozzle_map": ["0", "0"],
        "filament_volume_map": ["0", "0"],
        "filament_adhesiveness_category": ["100", "100"],
        "filament_prime_volume": ["45", "45"],
        "flush_volumes_vector": ["140", "140"],
        "flush_volumes_matrix": ["0", "140", "140", "0"],
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
            <metadata key="name" value="esp32_dev_board_enclosure_retro_futurist_lid_inserts" />
            <metadata key="extruder" value="1" />
            <part id="1">
              <metadata key="name" value="lid_inserts.stl" />
              <metadata key="source_file" value="lid_inserts.stl" />
              <metadata key="extruder" value="1" />
            </part>
            <part id="2">
              <metadata key="name" value="lid_shell.stl" />
              <metadata key="source_file" value="lid_shell.stl" />
              <metadata key="extruder" value="1" />
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


def write_retro_seed_template_3mf_fixture(path: Path) -> Path:
    project_settings = {
        "nozzle_diameter": [0.4],
        "filament_colour": ["#FFFF00", "#FF6A00"],
        "filament_multi_colour": ["#FFFF00", "#FF6A00"],
        "filament_colour_type": ["1", "1"],
        "filament_ids": ["GFL99", "GFL99"],
        "filament_type": ["PLA", "PLA"],
        "filament_vendor": ["Generic", "Generic"],
        "filament_settings_id": ["Generic PLA @BBL A1", "Generic PLA @BBL A1"],
        "filament_extruder_variant": ["Direct Drive Standard", "Direct Drive Standard"],
        "filament_self_index": ["1", "2"],
        "filament_map": ["1", "1"],
        "filament_nozzle_map": ["0", "0"],
        "filament_volume_map": ["0", "0"],
        "filament_adhesiveness_category": ["100", "100"],
        "filament_prime_volume": ["45", "45"],
        "flush_volumes_vector": ["140", "140"],
        "flush_volumes_matrix": ["0", "140", "140", "0"],
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
            <metadata key="extruder" value="1" />
            <part id="1">
              <metadata key="source_file" value="generated/output/lid_shell.stl" />
            </part>
          </object>
          <object id="2">
            <metadata key="name" value="lid_inserts" />
            <metadata key="extruder" value="2" />
            <part id="2">
              <metadata key="source_file" value="generated/output/lid_inserts.stl" />
            </part>
          </object>
          <object id="3">
            <metadata key="name" value="lid_accent" />
            <metadata key="extruder" value="2" />
            <part id="3">
              <metadata key="source_file" value="generated/output/lid_accent.stl" />
            </part>
          </object>
          <object id="4">
            <metadata key="name" value="base" />
            <metadata key="extruder" value="1" />
            <part id="4">
              <metadata key="source_file" value="generated/output/base.stl" />
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


def test_preset_a1_hybrid_two_color_is_valid() -> None:
    spec = preset_a1_hybrid_two_color()

    assert spec.target_printer == "A1"
    assert spec.export_backend == "bambu_studio_cli"
    assert spec.filament_count == 2
    assert set(spec.grouped_objects()) == {"retro_lid"}


def test_resolve_cli_and_gui_import_paths_use_mesh_fallback(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_shell.step", "lid_inserts.stl", "lid_inserts.step", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )

    assert resolve_cli_mesh_path(spec.parts[0]).suffix == ".stl"
    assert resolve_gui_import_path(spec.parts[0]).suffix == ".stl"
    assert resolve_gui_import_path(spec.parts[2]).suffix == ".stl"
    assert resolve_gui_import_path(spec.parts[3]).suffix == ".stl"


def test_build_cli_assemble_payload_orders_plate_and_grouping(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_shell.step", "lid_inserts.stl", "lid_inserts.step", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )

    payload = build_cli_assemble_payload(spec)

    assert len(payload["plates"]) == 2
    assert payload["plates"][0]["need_arrange"] is True
    assert payload["plates"][0]["objects"][0]["assemble_index"] == [1]
    assert payload["plates"][0]["objects"][0]["path"].endswith("lid_shell.stl")
    assert payload["plates"][0]["objects"][1]["path"].endswith("lid_inserts.stl")


def test_build_gui_import_paths_and_launch_command_use_open(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_shell.step", "lid_inserts.stl", "lid_inserts.step", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )

    import_paths = build_gui_import_paths(spec)
    command = build_gui_launch_command(spec, app_path="/Applications/BambuStudio.app")

    assert len(import_paths) == 2
    assert import_paths[0].name == "lid_shell.stl"
    assert import_paths[1].name == "lid_inserts.stl"
    assert command[:3] == ["open", "-a", "/Applications/BambuStudio.app"]
    assert command[3:] == [str(path) for path in import_paths]


def test_build_bambu_handoff_mentions_grouped_and_separate_parts() -> None:
    spec = BambuProjectSpec.from_dict(make_project_payload())

    handoff = build_bambu_handoff(spec)

    assert "retro_lid" in handoff
    assert "lid_shell.step" in handoff
    assert "lid_accent.stl" in handoff
    assert "generated/output/retro_a1.3mf" in handoff


def test_patch_studio_3mf_multicolor_rewrites_project_metadata(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    input_3mf = write_studio_3mf_fixture(tmp_path / "input.3mf")
    output_3mf = tmp_path / "patched.3mf"

    result = patch_studio_3mf_multicolor(spec, input_3mf, output_3mf=output_3mf)
    formatted = format_bambu_patch_result(result)

    assert result.success
    assert result.patched_objects == ["lid_shell", "lid_inserts"]
    assert "success=True" in formatted
    assert "patched_objects=lid_shell;lid_inserts" in formatted
    assert output_3mf.exists()

    with zipfile.ZipFile(output_3mf, "r") as archive:
        project_settings = json.loads(archive.read("Metadata/project_settings.config"))
        model_root = ET.fromstring(archive.read("Metadata/model_settings.config"))

    assert project_settings["filament_colour"] == ["#FFFF00", "#FF6A00"]
    assert project_settings["filament_multi_colour"] == ["#FFFF00", "#FF6A00"]
    assert project_settings["filament_extruder_variant"] == [
        "Direct Drive Standard",
        "Direct Drive Standard",
    ]
    assert project_settings["filament_self_index"] == ["1", "2"]
    assert project_settings["filament_map"] == ["1", "1"]
    assert project_settings["filament_nozzle_map"] == ["0", "0"]
    assert project_settings["filament_volume_map"] == ["0", "0"]
    assert project_settings["flush_volumes_vector"] == ["140", "140"]
    assert project_settings["flush_volumes_matrix"] == ["0", "140", "140", "0"]

    object_extruders = {}
    for obj in model_root.findall("object"):
        name = obj.find("metadata[@key='name']").attrib["value"]
        extruder = obj.find("metadata[@key='extruder']").attrib["value"]
        object_extruders[name] = extruder
    assert object_extruders == {"lid_shell": "1", "lid_inserts": "2"}


def test_patch_studio_3mf_multicolor_ignores_unimported_separate_objects(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.stl"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.stl"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )

    result = patch_studio_3mf_multicolor(
        spec,
        write_studio_3mf_fixture(tmp_path / "input.3mf"),
        output_3mf=tmp_path / "patched-full-spec.3mf",
    )

    assert result.success
    assert sorted(result.patched_objects) == ["lid_inserts", "lid_shell"]


def test_patch_studio_3mf_multicolor_updates_grouped_parts_in_one_object(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    input_3mf = write_grouped_studio_3mf_fixture(tmp_path / "grouped-input.3mf")
    output_3mf = tmp_path / "grouped-patched.3mf"

    result = patch_studio_3mf_multicolor(spec, input_3mf, output_3mf=output_3mf)

    assert result.success
    with zipfile.ZipFile(output_3mf, "r") as archive:
        model_root = ET.fromstring(archive.read("Metadata/model_settings.config"))

    parts = model_root.findall("object")[0].findall("part")
    part_extruders = {}
    for part in parts:
        name = ""
        extruder = None
        for meta in part.findall("metadata"):
            if meta.get("key") == "name":
                name = meta.get("value") or ""
            if meta.get("key") == "extruder":
                extruder = meta.get("value")
        part_extruders[name] = extruder

    assert part_extruders == {"lid_inserts.stl": "2", "lid_shell.stl": "1"}


def test_apply_seed_template_3mf_uses_spec_template_and_preserves_seed(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    template_3mf = write_studio_3mf_fixture(tmp_path / "seed-template.3mf")
    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    output_3mf = tmp_path / "patched-from-template.3mf"

    result = apply_seed_template_3mf(spec, output_3mf=output_3mf)

    assert result.success
    assert result.input_3mf == str(template_3mf.resolve())
    assert result.output_3mf == str(output_3mf.resolve())
    assert output_3mf.exists()
    assert template_3mf.exists()
    assert any("Patched from seed template" in note for note in result.notes)


def test_export_3mf_with_bambu_gui_prefers_seed_template_structure(
    tmp_path: Path, monkeypatch
) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "seed_template_3mf": str(tmp_path / "retro-seed-template.3mf"),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.stl"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.stl"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )
    write_retro_seed_template_3mf_fixture(Path(spec.seed_template_3mf))
    output_3mf = tmp_path / "retro-export.3mf"

    monkeypatch.setattr(
        "llm_to_3dprint.bambu.probe_bambu_studio",
        lambda app_path=object(): (_ for _ in ()).throw(AssertionError("GUI probe should not run")),
    )
    monkeypatch.setattr(
        "llm_to_3dprint.bambu.build_gui_import_paths",
        lambda spec: (_ for _ in ()).throw(AssertionError("Grouped GUI import should not run")),
    )

    result = export_3mf_with_bambu_gui(spec, output_3mf=output_3mf)

    assert result.success
    assert result.command == []
    assert result.import_paths == []
    assert result.click_backend_used == "seed_template"
    assert any("seed template takes precedence" in note for note in result.notes)
    assert output_3mf.exists()

    with zipfile.ZipFile(output_3mf, "r") as archive:
        model_root = ET.fromstring(archive.read("Metadata/model_settings.config"))

    object_names = [obj.find("metadata[@key='name']").attrib["value"] for obj in model_root.findall("object")]
    part_counts = [len(obj.findall("part")) for obj in model_root.findall("object")]
    assert object_names == ["lid_shell", "lid_inserts", "lid_accent", "base"]
    assert part_counts == [1, 1, 1, 1]


def test_export_3mf_with_bambu_gui_does_not_fallback_when_seed_template_is_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    output_3mf = tmp_path / "missing-template-export.3mf"

    monkeypatch.setattr(
        "llm_to_3dprint.bambu.probe_bambu_studio",
        lambda app_path=object(): (_ for _ in ()).throw(AssertionError("GUI probe should not run")),
    )
    monkeypatch.setattr(
        "llm_to_3dprint.bambu.build_gui_import_paths",
        lambda spec: (_ for _ in ()).throw(AssertionError("Grouped GUI import should not run")),
    )

    result = export_3mf_with_bambu_gui(spec, output_3mf=output_3mf)

    assert result.success is False
    assert "Missing seed template 3MF" in (result.error_text or "")
    assert result.command == []
    assert result.import_paths == []


def test_check_seed_template_3mf_reports_expected_objects(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    template_3mf = write_studio_3mf_fixture(tmp_path / "seed-template.3mf")

    result = check_seed_template_3mf(spec, seed_template_3mf=template_3mf)
    formatted = format_bambu_template_check_result(result)

    assert result.success
    assert result.matched_patchable_objects == ["lid_shell.stl", "lid_inserts.stl"]
    assert result.missing_patchable_objects == []
    assert "success=True" in formatted
    assert "matched_patchable_objects=lid_shell.stl;lid_inserts.stl" in formatted


def test_capture_seed_template_3mf_copies_validated_template(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    input_3mf = write_studio_3mf_fixture(tmp_path / "input-template.3mf")
    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    output_3mf = tmp_path / "captured-template.3mf"

    result = capture_seed_template_3mf(spec, input_3mf, output_3mf=output_3mf)
    formatted = format_bambu_template_capture_result(result)

    assert result.success
    assert result.template_check.success
    assert result.output_3mf == str(output_3mf.resolve())
    assert output_3mf.exists()
    assert "success=True" in formatted
    assert "copied=True" in formatted


def test_bambu_patch_3mf_cli_command_writes_output(tmp_path: Path, monkeypatch, capsys) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    spec_path = tmp_path / "project.json"
    input_3mf = write_studio_3mf_fixture(tmp_path / "input.3mf")
    output_3mf = tmp_path / "patched-cli.3mf"
    spec.dump(spec_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm-to-3dprint",
            "bambu-patch-3mf",
            str(spec_path),
            str(input_3mf),
            "--output",
            str(output_3mf),
        ],
    )

    cli_main()
    captured = capsys.readouterr()

    assert "success=True" in captured.out
    assert output_3mf.exists()


def test_bambu_apply_template_cli_command_writes_output(tmp_path: Path, monkeypatch, capsys) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    write_studio_3mf_fixture(tmp_path / "seed-template.3mf")
    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    spec_path = tmp_path / "project.json"
    output_3mf = tmp_path / "patched-template-cli.3mf"
    spec.dump(spec_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm-to-3dprint",
            "bambu-apply-template",
            str(spec_path),
            "--output",
            str(output_3mf),
        ],
    )

    cli_main()
    captured = capsys.readouterr()

    assert "success=True" in captured.out
    assert output_3mf.exists()


def test_bambu_check_template_cli_command_reports_success(tmp_path: Path, monkeypatch, capsys) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    write_studio_3mf_fixture(tmp_path / "seed-template.3mf")
    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    spec_path = tmp_path / "project.json"
    spec.dump(spec_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm-to-3dprint",
            "bambu-check-template",
            str(spec_path),
        ],
    )

    cli_main()
    captured = capsys.readouterr()

    assert "success=True" in captured.out
    assert "matched_patchable_objects=lid_shell.stl;lid_inserts.stl" in captured.out


def test_bambu_capture_template_cli_command_writes_output(tmp_path: Path, monkeypatch, capsys) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    input_3mf = write_studio_3mf_fixture(tmp_path / "input-template.3mf")
    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    spec_path = tmp_path / "project.json"
    output_3mf = tmp_path / "captured-template-cli.3mf"
    spec.dump(spec_path)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm-to-3dprint",
            "bambu-capture-template",
            str(spec_path),
            str(input_3mf),
            "--output",
            str(output_3mf),
        ],
    )

    cli_main()
    captured = capsys.readouterr()

    assert "success=True" in captured.out
    assert output_3mf.exists()


def test_write_cli_assemble_list_emits_json(tmp_path: Path) -> None:
    for name in ("lid_shell.stl", "lid_shell.step", "lid_inserts.stl", "lid_inserts.step", "lid_accent.stl", "base.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(
        {
            **make_project_payload(),
            "parts": [
                {
                    "name": "lid_shell",
                    "path": str(tmp_path / "lid_shell.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_shell",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "lid_inserts",
                    "path": str(tmp_path / "lid_inserts.step"),
                    "object_name": "retro_lid",
                    "part_name": "lid_inserts",
                    "load_strategy": "merge_as_parts",
                    "print_mode": "in_place_multicolor",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "lid_accent",
                    "path": str(tmp_path / "lid_accent.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "side_by_side_accent",
                    "plate": 1,
                    "filament": 2,
                },
                {
                    "name": "base",
                    "path": str(tmp_path / "base.stl"),
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 2,
                    "filament": 1,
                },
            ],
        }
    )

    destination = write_cli_assemble_list(spec, tmp_path / "assemble.json")

    assert destination.exists()
    assert destination.read_text().startswith("{\n  \"plates\"")


def test_format_bambu_cli_export_result_reports_status() -> None:
    result = BambuCliExportResult(
        command=["BambuStudio", "--export-3mf", "out.3mf"],
        output_3mf="out.3mf",
        assemble_list_path="assemble.json",
        presets=BambuPresetBundle(
            machine_path="/tmp/machine.json",
            process_path="/tmp/process.json",
            filament_paths=["/tmp/filament.json", "/tmp/filament.json"],
        ),
        returncode=1,
        stdout="hello",
        stderr="Segmentation fault",
        output_exists=False,
        crash_report="/tmp/BambuStudio-123.ips",
    )

    formatted = format_bambu_cli_export_result(result)

    assert "success=False" in formatted
    assert "crash_report=/tmp/BambuStudio-123.ips" in formatted


def test_format_bambu_gui_export_result_reports_status() -> None:
    result = BambuGuiExportResult(
        command=["open", "-a", "/Applications/BambuStudio.app", "one.stl"],
        output_3mf="generated/output/out.3mf",
        import_paths=["one.stl"],
        launch_returncode=0,
        stdout="imported",
        stderr="",
        output_exists=True,
        merge_dialog_clicked=True,
        save_panel_handled=True,
        error_text=None,
        notes=["calibrated click"],
    )

    formatted = format_bambu_gui_export_result(result)

    assert "success=True" in formatted
    assert "merge_dialog_clicked=True" in formatted
    assert "click_backend_used=None" in formatted
    assert "calibrated click" in formatted


def test_probe_bambu_studio_reports_hammerspoon_when_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = tmp_path / "BambuStudio.app"
    executable = app / "Contents" / "MacOS" / "BambuStudio"
    executable.parent.mkdir(parents=True)
    executable.write_text("")
    info_plist = app / "Contents" / "Info.plist"
    info_plist.parent.mkdir(parents=True, exist_ok=True)
    with info_plist.open("wb") as handle:
        plistlib.dump({"CFBundleShortVersionString": "02.05.00.66"}, handle)

    monkeypatch.setattr("llm_to_3dprint.bambu.shutil.which", lambda name: "/opt/homebrew/bin/hs" if name == "hs" else None)

    def fake_run(command, capture_output=True, text=True, timeout=None):
        if command[0] == "osascript":
            return CompletedProcess(command, 0, "true\n", "")
        if command[0] == "/opt/homebrew/bin/hs":
            return CompletedProcess(command, 0, "1\n", "")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("llm_to_3dprint.bambu.subprocess.run", fake_run)

    probe = probe_bambu_studio(app)

    assert probe.installed is True
    assert probe.cli_available is True
    assert probe.hammerspoon_cli_available is True
    assert probe.hammerspoon_ipc_ready is True
    assert probe.hammerspoon_cli_path == "/opt/homebrew/bin/hs"


def test_resolve_gui_click_backend_prefers_hammerspoon_when_ready() -> None:
    probe = BambuStudioProbe(
        installed=True,
        app_path="/Applications/BambuStudio.app",
        executable_path="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        support_dir="/tmp/bambu",
        version="02.05.00.66",
        cli_available=True,
        assistive_access=True,
        hammerspoon_cli_path="/opt/homebrew/bin/hs",
        hammerspoon_cli_available=True,
        hammerspoon_ipc_ready=True,
    )

    assert _resolve_gui_click_backend("auto", probe) == "hammerspoon"
    assert _resolve_gui_click_backend("swift", probe) == "swift"


def test_bambu_import_ready_accepts_real_project_window_without_untitled() -> None:
    names = ["hammerspoon_gui_test"]

    assert _bambu_import_ready(
        names,
        needs_merge_confirmation=True,
        merge_dialog_clicked=True,
    ) is True


def test_dismiss_bambu_unsaved_changes_dialog_uses_escape(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run(script: str):
        captured["script"] = script
        return CompletedProcess(["osascript"], 0, "", "")

    monkeypatch.setattr("llm_to_3dprint.bambu._run_osascript", fake_run)

    result = _dismiss_bambu_unsaved_changes_dialog()

    assert result.returncode == 0
    assert 'set frontmost to true' in captured["script"]
    assert "key code 53" in captured["script"]


def test_export_3mf_with_bambu_gui_prefers_seed_template_for_multicolor_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in ("lid_shell.stl", "lid_inserts.stl"):
        (tmp_path / name).write_text("solid test\nendsolid test\n")

    spec = BambuProjectSpec.from_dict(make_patch_project_payload(tmp_path))
    probe = BambuStudioProbe(
        installed=True,
        app_path="/Applications/BambuStudio.app",
        executable_path="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        support_dir="/tmp/bambu",
        version="02.05.00.66",
        cli_available=True,
        assistive_access=True,
        hammerspoon_cli_path="/opt/homebrew/bin/hs",
        hammerspoon_cli_available=True,
        hammerspoon_ipc_ready=True,
    )
    output_3mf = tmp_path / "gui-normalized.3mf"
    import_paths = [tmp_path / "lid_shell.stl", tmp_path / "lid_inserts.stl"]
    window_names = iter(
        [
            ["Object with multiple parts was detected"],
            ["normalized_project"],
            ["normalized_project"],
        ]
    )
    template_calls: list[Path] = []

    monkeypatch.setattr("llm_to_3dprint.bambu.probe_bambu_studio", lambda app_path=...: probe)
    monkeypatch.setattr("llm_to_3dprint.bambu.build_gui_import_paths", lambda _spec: import_paths)
    monkeypatch.setattr(
        "llm_to_3dprint.bambu.build_gui_launch_command",
        lambda _spec, app_path=...: ["open", "-a", probe.app_path, *[str(path) for path in import_paths]],
    )
    monkeypatch.setattr("llm_to_3dprint.bambu._recover_bambu_gui_state", lambda timeout=5.0: [])
    monkeypatch.setattr("llm_to_3dprint.bambu._bambu_process_exists", lambda: False)
    monkeypatch.setattr("llm_to_3dprint.bambu._resolve_gui_click_backend", lambda backend, _probe: "hammerspoon")
    monkeypatch.setattr("llm_to_3dprint.bambu._bring_bambu_to_front", lambda: CompletedProcess(["osascript"], 0, "", ""))
    monkeypatch.setattr(
        "llm_to_3dprint.bambu._confirm_bambu_merge_prompt",
        lambda *args, **kwargs: (True, '{"ok":true}', None, "hammerspoon"),
    )
    monkeypatch.setattr("llm_to_3dprint.bambu._bambu_window_names", lambda: next(window_names, ["normalized_project"]))

    def fake_save(path, save_timeout=30.0):
        path.write_text("grouped-save")
        return True, ""

    monkeypatch.setattr("llm_to_3dprint.bambu._save_bambu_project_to_path", fake_save)

    def fake_apply(_spec, *, output_3mf=None, seed_template_3mf=None):
        output_path = Path(output_3mf or _spec.output_3mf).resolve()
        template_calls.append(output_path)
        output_path.write_text("normalized-template-save")
        return BambuStudio3mfPatchResult(
            input_3mf=str(Path(_spec.seed_template_3mf or "").resolve()),
            output_3mf=str(output_path),
            filament_count=_spec.filament_count,
            nozzle_count=1,
            patched_objects=["lid_shell.stl", "lid_inserts.stl"],
            output_exists=True,
            patched=True,
            notes=["Patched from seed template: seed-template.3mf"],
        )

    monkeypatch.setattr("llm_to_3dprint.bambu.apply_seed_template_3mf", fake_apply)
    monkeypatch.setattr(
        "llm_to_3dprint.bambu.patch_studio_3mf_multicolor",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("grouped patch path should not run")),
    )

    def fake_run(command, capture_output=True, text=True, timeout=None):
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("llm_to_3dprint.bambu.subprocess.run", fake_run)

    result = export_3mf_with_bambu_gui(spec, output_3mf=output_3mf, click_backend="hammerspoon")

    assert result.success
    assert output_3mf.exists()
    assert output_3mf.read_text() == "normalized-template-save"
    assert template_calls == [output_3mf.resolve()]
    assert any("seed template takes precedence" in note for note in result.notes)
    assert any("Patched from seed template" in note for note in result.notes)


def test_setup_hammerspoon_for_bambu_writes_init_block(tmp_path: Path, monkeypatch) -> None:
    init_path = tmp_path / "init.lua"
    probe = BambuStudioProbe(
        installed=True,
        app_path="/Applications/BambuStudio.app",
        executable_path="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        support_dir="/tmp/bambu",
        version="02.05.00.66",
        cli_available=True,
        assistive_access=True,
        hammerspoon_cli_path="/opt/homebrew/bin/hs",
        hammerspoon_cli_available=True,
        hammerspoon_ipc_ready=True,
    )
    monkeypatch.setattr("llm_to_3dprint.bambu.probe_bambu_studio", lambda app_path: probe)

    result = setup_hammerspoon_for_bambu(init_path=init_path, restart=False)
    formatted = format_bambu_hammerspoon_setup_result(result)

    assert result.success
    assert result.init_written is True
    assert init_path.exists()
    assert 'require("hs.ipc")' in init_path.read_text()
    assert repo_hammerspoon_actions_path().exists()
    assert "success=True" in formatted
    assert f"actions_path={repo_hammerspoon_actions_path()}" in formatted


def test_bambu_setup_hammerspoon_cli_command_writes_init(tmp_path: Path, monkeypatch, capsys) -> None:
    init_path = tmp_path / "hammerspoon" / "init.lua"
    probe = BambuStudioProbe(
        installed=True,
        app_path="/Applications/BambuStudio.app",
        executable_path="/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        support_dir="/tmp/bambu",
        version="02.05.00.66",
        cli_available=True,
        assistive_access=True,
        hammerspoon_cli_path="/opt/homebrew/bin/hs",
        hammerspoon_cli_available=True,
        hammerspoon_ipc_ready=True,
    )

    def fake_setup(*, app_path, restart, init_path=None):
        return setup_hammerspoon_for_bambu(init_path=init_path or init_path_local, restart=restart)

    init_path_local = init_path
    monkeypatch.setattr("llm_to_3dprint.bambu.probe_bambu_studio", lambda app_path: probe)
    monkeypatch.setattr("llm_to_3dprint.cli.setup_hammerspoon_for_bambu", fake_setup)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llm-to-3dprint",
            "bambu-setup-hammerspoon",
            "--no-restart",
        ],
    )

    cli_main()
    captured = capsys.readouterr()

    assert "success=True" in captured.out
    assert init_path.exists()

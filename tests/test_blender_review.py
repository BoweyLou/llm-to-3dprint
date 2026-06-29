from __future__ import annotations

import json
from pathlib import Path

from llm_to_3dprint.bambu import BambuProjectSpec
from llm_to_3dprint.blender_review import write_blender_review_plan


def test_write_blender_review_plan_creates_report_and_script(tmp_path: Path) -> None:
    spec = BambuProjectSpec.from_dict(
        {
            "name": "review_project",
            "description": "Project with reviewable STL and manual STEP.",
            "target_printer": "A1",
            "nozzle_diameter": 0.4,
            "ams": "none",
            "filament_count": 1,
            "export_backend": "clean_room_3mf",
            "output_3mf": "generated/output/review_project.3mf",
            "parts": [
                {
                    "name": "body",
                    "path": "body.stl",
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 1,
                    "filament": 1,
                },
                {
                    "name": "solid_review",
                    "path": "solid.step",
                    "load_strategy": "separate_object",
                    "print_mode": "standalone",
                    "plate": 1,
                    "filament": 1,
                },
            ],
        }
    )

    plan = write_blender_review_plan(spec, tmp_path / "review", base_dir=tmp_path)

    assert Path(plan.plan_path).exists()
    assert Path(plan.report_path).exists()
    script = Path(plan.script_path).read_text()
    assert "bpy.ops.wm.stl_import" in script
    payload = json.loads(Path(plan.plan_path).read_text())
    assert payload["artifacts"][0]["import_supported"] is True
    assert payload["artifacts"][1]["import_supported"] is False
    assert [view["name"] for view in payload["views"]] == ["front", "right", "top", "isometric"]

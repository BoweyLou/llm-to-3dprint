from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from llm_to_3dprint.brief import DesignBrief
from llm_to_3dprint.cli import main as cli_main
from llm_to_3dprint.design_validation import (
    format_design_validation_report,
    validate_design_contract,
)


def ramp_payload(**overrides):
    payload = {
        "name": "smooth_threshold_ramp",
        "description": "Ramp with explicit shape constraints.",
        "object_type": "ramp",
        "library": "cadquery",
        "units": "mm",
        "base_shape": "rectangular",
        "internal_dimensions": {"length": 120.0, "width": 80.0, "height": 12.0},
        "wall_thickness": 2.0,
        "design_intent": {
            "silhouette": "single smooth wedge with rounded side transitions",
            "visual_style": "quiet functional utility part",
            "symmetry": "y",
            "surface_continuity": "no abrupt lumps along the ramp surface",
            "must_be_smooth": True,
            "max_slope_degrees": 12.0,
            "min_wall_thickness": 1.6,
            "forbidden_features": ["spikes", "isolated bumps", "non-manifold ribs"],
            "cross_sections": [
                "centerline should rise monotonically from front lip to rear edge",
                "left and right side profiles should mirror each other",
            ],
        },
    }
    payload.update(overrides)
    return payload


def mesh_drawer_payload(**overrides):
    payload = {
        "name": "desk_organiser_mesh_preserved_drawers",
        "description": "Mesh-preserved desk organiser with functional drawers.",
        "object_type": "mesh_preserved_drawer_organiser",
        "library": "mesh",
        "units": "mm",
        "base_shape": "rectangular",
        "internal_dimensions": {"length": 100.0, "width": 50.0, "height": 93.0},
        "wall_thickness": 2.2,
        "design_intent": {
            "silhouette": "preserve the original drawing-derived organiser mesh",
            "visual_style": "child-designed desk organiser with original mesh surface retained",
            "symmetry": "none",
            "surface_continuity": "source triangles are partitioned without remeshing",
            "must_be_smooth": False,
            "min_wall_thickness": 1.2,
            "forbidden_features": ["dropped source triangles", "duplicated source triangles"],
            "cross_sections": ["front drawer stack with four removable drawers"],
        },
        "mesh_preservation": {
            "source_3mf": "/Users/yannickbowe/Downloads/reduced_color-2.3mf",
            "mesh_reuse_policy": "partition_visible_mesh",
            "require_triangle_accounting": True,
        },
        "drawer_stack": {
            "drawer_count": 1,
            "clearance": 0.5,
            "min_clearance": 0.4,
            "max_clearance": 0.6,
            "patch_masks": [
                {
                    "name": "drawer_1_front",
                    "x_min": 2.0,
                    "x_max": 50.0,
                    "y_min": 10.0,
                    "y_max": 26.0,
                    "z_min": 4.0,
                    "z_max": 23.0,
                }
            ],
        },
    }
    payload.update(overrides)
    return payload


class DesignValidationTests(unittest.TestCase):
    def test_valid_design_contract_passes_with_slope_check(self) -> None:
        brief = DesignBrief.from_dict(ramp_payload())

        report = validate_design_contract(brief)

        self.assertTrue(report.passes, report.issues)
        self.assertEqual(report.computed["ramp_slope_degrees"], 5.71)
        text = format_design_validation_report(report)
        self.assertIn("PASS smooth_threshold_ramp", text)
        self.assertIn("ramp_slope_degrees=5.71", text)

    def test_missing_design_intent_fails_before_generation(self) -> None:
        payload = ramp_payload()
        payload.pop("design_intent")
        brief = DesignBrief.from_dict(payload)

        report = validate_design_contract(brief)

        self.assertFalse(report.passes)
        self.assertIn("missing_design_intent", [issue.code for issue in report.issues])

    def test_ramp_slope_must_not_exceed_design_contract(self) -> None:
        payload = ramp_payload(
            internal_dimensions={"length": 80.0, "width": 80.0, "height": 30.0}
        )
        payload["design_intent"]["max_slope_degrees"] = 10.0
        brief = DesignBrief.from_dict(payload)

        report = validate_design_contract(brief)

        self.assertFalse(report.passes)
        self.assertIn("max_slope_exceeded", [issue.code for issue in report.issues])
        self.assertEqual(report.computed["ramp_slope_degrees"], 20.56)

    def test_cli_validate_design_exits_nonzero_for_bad_brief(self) -> None:
        payload = ramp_payload(
            internal_dimensions={"length": 80.0, "width": 80.0, "height": 30.0}
        )
        payload["design_intent"]["max_slope_degrees"] = 10.0
        with tempfile.TemporaryDirectory() as tmpdir:
            brief_path = Path(tmpdir) / "brief.json"
            brief_path.write_text(json.dumps(payload) + "\n")

            output = io.StringIO()
            with patch.object(sys, "argv", ["llm-to-3dprint", "validate-design", str(brief_path)]):
                with redirect_stdout(output):
                    with self.assertRaises(SystemExit) as raised:
                        cli_main()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("FAIL smooth_threshold_ramp", output.getvalue())
        self.assertIn("max_slope_exceeded", output.getvalue())

    def test_mesh_preserved_drawer_contract_passes(self) -> None:
        brief = DesignBrief.from_dict(mesh_drawer_payload())

        report = validate_design_contract(brief)

        self.assertTrue(report.passes, report.issues)
        self.assertEqual(report.computed["drawer_count"], 1)
        self.assertEqual(report.computed["mesh_reuse_policy"], "partition_visible_mesh")
        self.assertEqual(report.computed["source_skin_shell_thickness"], 0.8)

    def test_mesh_preserved_drawer_contract_requires_triangle_accounting(self) -> None:
        payload = mesh_drawer_payload()
        payload["mesh_preservation"]["require_triangle_accounting"] = False
        brief = DesignBrief.from_dict(payload)

        report = validate_design_contract(brief)

        self.assertFalse(report.passes)
        self.assertIn("triangle_accounting_not_required", [issue.code for issue in report.issues])


if __name__ == "__main__":
    unittest.main()

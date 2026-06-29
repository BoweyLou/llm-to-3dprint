from pathlib import Path

import pytest

from llm_to_3dprint.brief import DesignBrief, preset_rectangular_enclosure


def test_preset_has_expected_outer_dimensions() -> None:
    brief = preset_rectangular_enclosure()

    assert brief.outer_length == 84.0
    assert brief.outer_width == 54.0
    assert brief.outer_height == 27.5


def test_load_example_brief() -> None:
    root = Path(__file__).resolve().parents[1]
    brief = DesignBrief.load(root / "examples" / "rectangular_enclosure.json")

    assert brief.name == "rectangular_enclosure_demo"
    assert len(brief.cutouts) == 2
    assert len(brief.mounting_holes) == 4


def test_load_friction_lid_example_brief() -> None:
    root = Path(__file__).resolve().parents[1]
    brief = DesignBrief.load(root / "examples" / "friction_lid_enclosure.json")

    assert brief.name == "friction_lid_enclosure_demo"
    assert brief.closure is not None
    assert brief.closure.type == "friction_lid"
    assert brief.resolved_lid_seat_z == pytest.approx(17.6)


def test_brief_with_closure_metadata_loads_and_derives_seat_z() -> None:
    brief = DesignBrief.from_dict(
        {
            "name": "friction_lid_enclosure",
            "description": "Electronics enclosure with explicit closure metadata.",
            "object_type": "enclosure",
            "library": "cadquery",
            "units": "mm",
            "base_shape": "rectangular",
            "internal_dimensions": {"length": 60.0, "width": 40.0, "height": 20.0},
            "wall_thickness": 2.0,
            "base_thickness": 3.0,
            "fillet_radius": 1.0,
            "lid_style": "friction_lid",
            "closure": {
                "type": "friction_lid",
                "insert_depth": 4.0,
                "target_clearance": 0.35,
                "assembled_orientation": "lip_down",
                "print_orientation": "styled_face_up",
                "supports_allowed": True,
                "decorate_exterior_only": True,
            },
        }
    )

    assert brief.closure is not None
    assert brief.closure.type == "friction_lid"
    assert brief.resolved_lid_seat_z == pytest.approx(19.0)


def test_brief_accepts_design_intent_contract() -> None:
    brief = DesignBrief.from_dict(
        {
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
    )

    assert brief.design_intent is not None
    assert brief.design_intent.symmetry == "y"
    assert brief.design_intent.must_be_smooth is True
    assert "isolated bumps" in brief.design_intent.forbidden_features


def test_design_intent_rejects_invalid_constraints() -> None:
    with pytest.raises(ValueError, match="max_slope_degrees"):
        DesignBrief.from_dict(
            {
                "name": "bad_design_intent",
                "description": "Invalid design intent.",
                "object_type": "ramp",
                "library": "cadquery",
                "units": "mm",
                "base_shape": "rectangular",
                "internal_dimensions": {"length": 120.0, "width": 80.0, "height": 12.0},
                "wall_thickness": 2.0,
                "design_intent": {"max_slope_degrees": 120.0},
            }
        )


def test_design_intent_min_wall_must_not_exceed_wall_thickness() -> None:
    with pytest.raises(ValueError, match="min_wall_thickness"):
        DesignBrief.from_dict(
            {
                "name": "bad_min_wall",
                "description": "Invalid design intent.",
                "object_type": "ramp",
                "library": "cadquery",
                "units": "mm",
                "base_shape": "rectangular",
                "internal_dimensions": {"length": 120.0, "width": 80.0, "height": 12.0},
                "wall_thickness": 2.0,
                "design_intent": {"min_wall_thickness": 2.5},
            }
        )


def test_brief_accepts_mesh_preserved_drawer_metadata() -> None:
    brief = DesignBrief.from_dict(
        {
            "name": "desk_organiser_mesh_preserved_drawers",
            "description": "Mesh-preserved desk organiser with functional drawers.",
            "object_type": "mesh_preserved_drawer_organiser",
            "library": "mesh",
            "units": "mm",
            "base_shape": "rectangular",
            "internal_dimensions": {"length": 100.0, "width": 50.0, "height": 93.0},
            "wall_thickness": 2.2,
            "mesh_preservation": {
                "source_3mf": "/Users/yannickbowe/Downloads/reduced_color-2.3mf",
                "mesh_reuse_policy": "partition_visible_mesh",
                "canonical_orientation": "front_rotated_180",
                "canonical_rotate_z_degrees": 180.0,
                "require_triangle_accounting": True,
            },
            "drawer_stack": {
                "drawer_count": 4,
                "face": "front",
                "mode": "separate_removable_trays",
                "clearance": 0.5,
                "min_clearance": 0.4,
                "max_clearance": 0.6,
                "front_patch_includes": ["drawer faces", "handles"],
                "skin_selection_strategy": "front_visible_raycast",
                "patch_masks": [
                    {"name": "drawer_1_front", "x_min": 2.0, "x_max": 50.0, "y_min": 10.0, "y_max": 26.0, "z_min": 4.0, "z_max": 23.0},
                    {"name": "drawer_2_front", "x_min": 2.0, "x_max": 50.0, "y_min": 10.0, "y_max": 26.0, "z_min": -8.0, "z_max": 4.0},
                    {"name": "drawer_3_front", "x_min": 2.0, "x_max": 50.0, "y_min": 10.0, "y_max": 26.0, "z_min": -23.0, "z_max": -8.0},
                    {"name": "drawer_4_front", "x_min": 2.0, "x_max": 50.0, "y_min": 10.0, "y_max": 26.0, "z_min": -46.0, "z_max": -23.0},
                ],
            },
        }
    )

    assert brief.library == "mesh"
    assert brief.mesh_preservation is not None
    assert brief.mesh_preservation.mesh_reuse_policy == "partition_visible_mesh"
    assert brief.drawer_stack is not None
    assert brief.drawer_stack.drawer_count == 4
    assert brief.drawer_stack.skin_selection_strategy == "front_visible_raycast"
    assert brief.drawer_stack.source_skin_shell_thickness == pytest.approx(0.8)
    assert len(brief.drawer_stack.patch_masks) == 4


def test_mesh_preserved_drawer_clearance_must_stay_in_range() -> None:
    with pytest.raises(ValueError, match="clearance"):
        DesignBrief.from_dict(
            {
                "name": "bad_mesh_drawers",
                "description": "Invalid drawer clearance.",
                "object_type": "mesh_preserved_drawer_organiser",
                "library": "mesh",
                "units": "mm",
                "base_shape": "rectangular",
                "internal_dimensions": {"length": 100.0, "width": 50.0, "height": 93.0},
                "wall_thickness": 2.2,
                "mesh_preservation": {
                    "source_3mf": "/tmp/source.3mf",
                    "mesh_reuse_policy": "partition_visible_mesh",
                },
                "drawer_stack": {
                    "drawer_count": 1,
                    "clearance": 0.2,
                    "min_clearance": 0.4,
                    "max_clearance": 0.6,
                    "patch_masks": [
                        {"name": "drawer_1", "x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0, "z_min": 0.0, "z_max": 1.0}
                    ],
                },
            }
        )


def test_non_open_top_closure_requires_insert_depth_or_seat_z() -> None:
    with pytest.raises(ValueError, match="insert_depth or seat_z"):
        DesignBrief.from_dict(
            {
                "name": "bad_closure_enclosure",
                "description": "Invalid closure metadata.",
                "object_type": "enclosure",
                "library": "cadquery",
                "units": "mm",
                "base_shape": "rectangular",
                "internal_dimensions": {"length": 60.0, "width": 40.0, "height": 20.0},
                "wall_thickness": 2.0,
                "base_thickness": 3.0,
                "lid_style": "friction_lid",
                "closure": {"type": "friction_lid"},
            }
        )

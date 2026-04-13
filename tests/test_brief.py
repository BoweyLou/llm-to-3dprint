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

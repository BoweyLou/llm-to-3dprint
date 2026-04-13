from llm_to_3dprint.brief import Closure, preset_rectangular_enclosure
from llm_to_3dprint.prompting import build_generation_prompt


def test_prompt_contains_key_sections() -> None:
    prompt = build_generation_prompt(preset_rectangular_enclosure())

    assert "Target library: cadquery" in prompt
    assert "Generate a complete Python script" in prompt
    assert "Mounting holes:" in prompt
    assert "Coordinate conventions:" in prompt


def test_prompt_includes_explicit_closure_metadata_and_fit_guidance() -> None:
    brief = preset_rectangular_enclosure()
    brief.lid_style = "friction_lid"
    brief.closure = Closure(
        type="friction_lid",
        insert_depth=4.2,
        seat_z=17.8,
        target_clearance=0.35,
        assembled_orientation="lip_down",
        print_orientation="styled_face_up",
        supports_allowed=True,
        decorate_exterior_only=True,
    )
    brief.validate()

    prompt = build_generation_prompt(brief)

    assert "Closure:" in prompt
    assert "- type: friction_lid" in prompt
    assert "- seat z: 17.8" in prompt
    assert "- supports allowed: True" in prompt
    assert "Exposes get_lid_seat_height(), LID_SEAT_Z, or BASE_OUTER_HEIGHT and LID_LIP_DEPTH" in prompt

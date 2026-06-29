from llm_to_3dprint.brief import (
    Closure,
    DesignIntent,
    DrawerPatchMask,
    DrawerStack,
    MeshPreservation,
    preset_rectangular_enclosure,
)
from llm_to_3dprint.prompting import build_generation_prompt


def test_prompt_contains_key_sections() -> None:
    prompt = build_generation_prompt(preset_rectangular_enclosure())

    assert "Target library: cadquery" in prompt
    assert "Generate a complete Python script" in prompt
    assert "Mounting holes:" in prompt
    assert "Coordinate conventions:" in prompt


def test_prompt_includes_design_intent_contract() -> None:
    brief = preset_rectangular_enclosure()
    brief.design_intent = DesignIntent(
        silhouette="smooth utility wedge",
        visual_style="restrained functional part",
        symmetry="y",
        surface_continuity="continuous top face without isolated bumps",
        must_be_smooth=True,
        max_slope_degrees=12.0,
        min_wall_thickness=1.8,
        forbidden_features=["spikes", "random decorative blobs"],
        cross_sections=["centerline should be monotonic"],
    )
    brief.validate()

    prompt = build_generation_prompt(brief)

    assert "Design intent:" in prompt
    assert "- silhouette: smooth utility wedge" in prompt
    assert "- symmetry: y" in prompt
    assert "- forbidden features: spikes; random decorative blobs" in prompt
    assert "Treats the design intent as a contract" in prompt


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


def test_prompt_includes_mesh_preservation_and_drawer_stack() -> None:
    brief = preset_rectangular_enclosure()
    brief.library = "mesh"
    brief.object_type = "mesh_preserved_drawer_organiser"
    brief.mesh_preservation = MeshPreservation(
        source_3mf="/Users/yannickbowe/Downloads/reduced_color-2.3mf",
        mesh_reuse_policy="partition_visible_mesh",
    )
    brief.drawer_stack = DrawerStack(
        drawer_count=1,
        patch_masks=[
            DrawerPatchMask(
                name="drawer_1_front",
                x_min=2.0,
                x_max=50.0,
                y_min=10.0,
                y_max=26.0,
                z_min=4.0,
                z_max=23.0,
            )
        ],
    )
    brief.validate()

    prompt = build_generation_prompt(brief)

    assert "Mesh preservation:" in prompt
    assert "- reuse policy: partition_visible_mesh" in prompt
    assert "Drawer stack:" in prompt
    assert "- skin selection strategy: front_visible_raycast" in prompt
    assert "- source skin shell thickness: 0.8" in prompt
    assert "- drawer_1_front: x=2.0..50.0" in prompt
    assert "Preserves every source triangle exactly once" in prompt

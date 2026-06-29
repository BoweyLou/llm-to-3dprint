from __future__ import annotations

from llm_to_3dprint.brief import DesignBrief


def build_generation_prompt(brief: DesignBrief) -> str:
    """Return a reusable prompt for LLM-assisted CAD code generation."""

    cutout_lines: list[str] = []
    for cutout in brief.cutouts:
        size_bits: list[str] = []
        if cutout.width is not None:
            size_bits.append(f"width={cutout.width}")
        if cutout.height is not None:
            size_bits.append(f"height={cutout.height}")
        if cutout.diameter is not None:
            size_bits.append(f"diameter={cutout.diameter}")
        if cutout.depth is not None:
            size_bits.append(f"depth={cutout.depth}")
        cutout_lines.append(
            f"- {cutout.name}: face={cutout.face}, shape={cutout.shape}, "
            f"x={cutout.x}, y={cutout.y}, z={cutout.z}, " + ", ".join(size_bits)
        )

    hole_lines = [
        f"- {hole.name}: x={hole.x}, y={hole.y}, diameter={hole.diameter}, depth={hole.depth or brief.resolved_base_thickness}"
        for hole in brief.mounting_holes
    ]

    requirement_lines = [f"- {item}" for item in brief.requirements] or ["- No extra requirements provided."]
    note_lines = [f"- {item}" for item in brief.notes] or ["- No extra notes provided."]
    cutout_block = "\n".join(cutout_lines) if cutout_lines else "- No cutouts requested."
    hole_block = "\n".join(hole_lines) if hole_lines else "- No mounting holes requested."
    design_intent_block = "- No explicit design intent contract provided."
    if brief.design_intent is not None:
        design_lines: list[str] = []
        if brief.design_intent.silhouette is not None:
            design_lines.append(f"- silhouette: {brief.design_intent.silhouette}")
        if brief.design_intent.visual_style is not None:
            design_lines.append(f"- visual style: {brief.design_intent.visual_style}")
        if brief.design_intent.symmetry is not None:
            design_lines.append(f"- symmetry: {brief.design_intent.symmetry}")
        if brief.design_intent.surface_continuity is not None:
            design_lines.append(
                f"- surface continuity: {brief.design_intent.surface_continuity}"
            )
        if brief.design_intent.must_be_smooth is not None:
            design_lines.append(f"- must be smooth: {brief.design_intent.must_be_smooth}")
        if brief.design_intent.max_slope_degrees is not None:
            design_lines.append(f"- max slope degrees: {brief.design_intent.max_slope_degrees}")
        if brief.design_intent.min_wall_thickness is not None:
            design_lines.append(f"- min wall thickness: {brief.design_intent.min_wall_thickness}")
        if brief.design_intent.cross_sections:
            design_lines.append(
                "- cross sections: " + "; ".join(brief.design_intent.cross_sections)
            )
        if brief.design_intent.forbidden_features:
            design_lines.append(
                "- forbidden features: " + "; ".join(brief.design_intent.forbidden_features)
            )
        if brief.design_intent.notes:
            design_lines.append(f"- design notes: {brief.design_intent.notes}")
        design_intent_block = "\n".join(design_lines)
    closure_block = "- No explicit closure metadata provided."
    if brief.closure is not None:
        closure_lines = [f"- type: {brief.closure.type}"]
        if brief.closure.insert_depth is not None:
            closure_lines.append(f"- insert depth: {brief.closure.insert_depth}")
        if brief.closure.seat_z is not None:
            closure_lines.append(f"- seat z: {brief.closure.seat_z}")
        elif brief.resolved_lid_seat_z is not None:
            closure_lines.append(f"- derived seat z: {brief.resolved_lid_seat_z}")
        if brief.closure.target_clearance is not None:
            closure_lines.append(f"- target clearance: {brief.closure.target_clearance}")
        if brief.closure.assembled_orientation is not None:
            closure_lines.append(
                f"- assembled orientation: {brief.closure.assembled_orientation}"
            )
        if brief.closure.print_orientation is not None:
            closure_lines.append(f"- print orientation: {brief.closure.print_orientation}")
        if brief.closure.supports_allowed is not None:
            closure_lines.append(f"- supports allowed: {brief.closure.supports_allowed}")
        if brief.closure.decorate_exterior_only is not None:
            closure_lines.append(
                f"- decorate exterior only: {brief.closure.decorate_exterior_only}"
            )
        if brief.closure.notes:
            closure_lines.append(f"- closure notes: {brief.closure.notes}")
        closure_block = "\n".join(closure_lines)
    mesh_block = "- No mesh-preservation metadata provided."
    if brief.mesh_preservation is not None:
        mesh_block = "\n".join(
            [
                f"- source 3MF: {brief.mesh_preservation.source_3mf}",
                f"- reuse policy: {brief.mesh_preservation.mesh_reuse_policy}",
                f"- canonical orientation: {brief.mesh_preservation.canonical_orientation}",
                f"- canonical Z rotation: {brief.mesh_preservation.canonical_rotate_z_degrees}",
                (
                    "- triangle accounting required: "
                    f"{brief.mesh_preservation.require_triangle_accounting}"
                ),
            ]
        )
    drawer_block = "- No drawer-stack metadata provided."
    if brief.drawer_stack is not None:
        mask_lines = [
            (
                f"  - {mask.name}: x={mask.x_min}..{mask.x_max}, "
                f"y={mask.y_min}..{mask.y_max}, z={mask.z_min}..{mask.z_max}"
            )
            for mask in brief.drawer_stack.patch_masks
        ]
        drawer_lines = [
            f"- count: {brief.drawer_stack.drawer_count}",
            f"- face: {brief.drawer_stack.face}",
            f"- mode: {brief.drawer_stack.mode}",
            f"- clearance: {brief.drawer_stack.clearance}",
            f"- drawer wall thickness: {brief.drawer_stack.drawer_wall_thickness}",
            f"- body wall thickness: {brief.drawer_stack.body_wall_thickness}",
            f"- drawer depth: {brief.drawer_stack.drawer_depth}",
            f"- skin selection strategy: {brief.drawer_stack.skin_selection_strategy}",
            f"- source skin shell thickness: {brief.drawer_stack.source_skin_shell_thickness}",
            "- patch masks:",
            *mask_lines,
        ]
        drawer_block = "\n".join(drawer_lines)

    extra_generation_rules: list[str] = []
    if brief.closure is not None and brief.closure.type != "open_top":
        extra_generation_rules.extend(
            [
                "8. Makes print orientation and assembled orientation explicit for the lid/base interface.",
                "9. Exposes get_lid_seat_height(), LID_SEAT_Z, or BASE_OUTER_HEIGHT and LID_LIP_DEPTH for fit checks.",
                "10. Avoids putting mating geometry and exterior styling on the wrong side of the lid.",
            ]
        )

    return f"""You are generating a Python CAD script.

Target library: {brief.library}
Object name: {brief.name}
Object type: {brief.object_type}
Units: {brief.units}
Base shape: {brief.base_shape}

Description:
{brief.description}

Core dimensions:
- internal length: {brief.internal_dimensions.length}
- internal width: {brief.internal_dimensions.width}
- internal height: {brief.internal_dimensions.height}
- wall thickness: {brief.wall_thickness}
- base thickness: {brief.resolved_base_thickness}
- fillet radius: {brief.fillet_radius}
- lid style: {brief.lid_style}

Closure:
{closure_block}

Design intent:
{design_intent_block}

Mesh preservation:
{mesh_block}

Drawer stack:
{drawer_block}

Cutouts:
{cutout_block}

Mounting holes:
{hole_block}

Requirements:
{chr(10).join(requirement_lines)}

Notes:
{chr(10).join(note_lines)}

Coordinate conventions:
- origin is centered in X and Y
- Z=0 is the bottom face
- X spans the enclosure length
- Y spans the enclosure width
- cutout coordinates describe the center of the feature

Generate a complete Python script that:
1. Defines every critical dimension as a named parameter near the top of the file.
2. Uses relative references and reusable helper functions where practical.
3. Builds the final solid in {brief.library}.
4. Exports both STL and STEP files.
5. Includes brief comments explaining parameter groups and coordinate assumptions.
6. Avoids brittle absolute magic numbers.
7. Treats the design intent as a contract: preserve silhouette, symmetry, smoothness, and forbidden-shape constraints before adding decorative details.
8. Preserves every source triangle exactly once across output parts when mesh-preservation metadata is present.
{chr(10).join(extra_generation_rules) if extra_generation_rules else ""}

If geometry is ambiguous, choose conservative printable defaults and state them in code comments.
"""

from __future__ import annotations

from dataclasses import asdict
from pprint import pformat

from llm_to_3dprint.brief import DesignBrief


def render_script(brief: DesignBrief) -> str:
    """Dispatch to a concrete script renderer."""

    if brief.library != "cadquery":
        raise ValueError(
            f"Only cadquery rendering is implemented today, got {brief.library!r}. "
            "Use the prompt generator for build123d briefs."
        )

    if brief.base_shape != "rectangular":
        raise ValueError(
            f"Only rectangular base shapes are implemented today, got {brief.base_shape!r}."
        )

    return render_cadquery_enclosure(brief)


def render_cadquery_enclosure(brief: DesignBrief) -> str:
    """Render a starter CadQuery script for an open-top rectangular enclosure."""

    cutouts_literal = pformat([asdict(cutout) for cutout in brief.cutouts], sort_dicts=False, width=100)
    holes_literal = pformat(
        [asdict(hole) for hole in brief.mounting_holes],
        sort_dicts=False,
        width=100,
    )

    return f'''"""Generated from a structured design brief.

Part: {brief.name}
Description: {brief.description}
Units: {brief.units}

Coordinate conventions:
- X is centered across the part length.
- Y is centered across the part width.
- Z=0 is the bottom face.
- Face cutouts use X/Y/Z values in world coordinates.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq


PART_NAME = "{brief.name}"
INNER_LENGTH = {brief.internal_dimensions.length}
INNER_WIDTH = {brief.internal_dimensions.width}
INNER_HEIGHT = {brief.internal_dimensions.height}
WALL_THICKNESS = {brief.wall_thickness}
BASE_THICKNESS = {brief.resolved_base_thickness}
FILLET_RADIUS = {brief.fillet_radius}
DEFAULT_CUT_DEPTH = max(WALL_THICKNESS, BASE_THICKNESS) + 1.0
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

CUTOUTS = {cutouts_literal}
MOUNTING_HOLES = {holes_literal}


def build_enclosure() -> cq.Workplane:
    outer_length = INNER_LENGTH + (2 * WALL_THICKNESS)
    outer_width = INNER_WIDTH + (2 * WALL_THICKNESS)
    outer_height = INNER_HEIGHT + BASE_THICKNESS

    shell = cq.Workplane("XY").box(
        outer_length,
        outer_width,
        outer_height,
        centered=(True, True, False),
    )
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=BASE_THICKNESS)
        .box(
            INNER_LENGTH,
            INNER_WIDTH,
            INNER_HEIGHT,
            centered=(True, True, False),
        )
    )
    model = shell.cut(cavity)

    if FILLET_RADIUS > 0:
        model = model.edges("|Z").fillet(FILLET_RADIUS)

    for hole in MOUNTING_HOLES:
        depth = hole.get("depth") or BASE_THICKNESS
        cutter = (
            cq.Workplane("XY")
            .center(hole["x"], hole["y"])
            .circle(hole["diameter"] / 2.0)
            .extrude(depth)
        )
        model = model.cut(cutter)

    for cutout in CUTOUTS:
        model = model.cut(_make_cutout(cutout, outer_length, outer_width, outer_height))

    return model


def _make_cutout(
    cutout: dict[str, float | str | None],
    outer_length: float,
    outer_width: float,
    outer_height: float,
) -> cq.Workplane:
    face = cutout["face"]
    shape = cutout["shape"]
    depth = float(cutout.get("depth") or DEFAULT_CUT_DEPTH)

    if face == "front":
        workplane = cq.Workplane("XZ").workplane(offset=outer_width / 2.0)
        center = (float(cutout["x"]), float(cutout["z"]))
        direction = -depth
    elif face == "back":
        workplane = cq.Workplane("XZ").workplane(offset=-outer_width / 2.0)
        center = (float(cutout["x"]), float(cutout["z"]))
        direction = depth
    elif face == "right":
        workplane = cq.Workplane("YZ").workplane(offset=outer_length / 2.0)
        center = (float(cutout["y"]), float(cutout["z"]))
        direction = -depth
    elif face == "left":
        workplane = cq.Workplane("YZ").workplane(offset=-outer_length / 2.0)
        center = (float(cutout["y"]), float(cutout["z"]))
        direction = depth
    elif face == "top":
        workplane = cq.Workplane("XY").workplane(offset=outer_height)
        center = (float(cutout["x"]), float(cutout["y"]))
        direction = -depth
    elif face == "bottom":
        workplane = cq.Workplane("XY")
        center = (float(cutout["x"]), float(cutout["y"]))
        direction = depth
    else:
        raise ValueError(f"Unsupported face: {{face!r}}")

    if shape == "rectangular":
        return (
            workplane
            .center(*center)
            .rect(float(cutout["width"]), float(cutout["height"]))
            .extrude(direction)
        )

    if shape == "circular":
        return workplane.center(*center).circle(float(cutout["diameter"]) / 2.0).extrude(direction)

    raise ValueError(f"Unsupported cutout shape: {{shape!r}}")


def export_model(model: cq.Workplane) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(model, str(OUTPUT_DIR / f"{{PART_NAME}}.stl"))
    cq.exporters.export(model, str(OUTPUT_DIR / f"{{PART_NAME}}.step"))


result = build_enclosure()

if __name__ == "__main__":
    export_model(result)
'''

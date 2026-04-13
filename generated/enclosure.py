"""Generated from a structured design brief.

Part: rectangular_enclosure_demo
Description: Open-top electronics enclosure with a front display cutout and four base mounting holes.
Units: mm

Coordinate conventions:
- X is centered across the part length.
- Y is centered across the part width.
- Z=0 is the bottom face.
- Face cutouts use X/Y/Z values in world coordinates.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq


PART_NAME = "rectangular_enclosure_demo"
INNER_LENGTH = 80.0
INNER_WIDTH = 50.0
INNER_HEIGHT = 25.0
WALL_THICKNESS = 2.0
BASE_THICKNESS = 2.5
FILLET_RADIUS = 2.0
DEFAULT_CUT_DEPTH = max(WALL_THICKNESS, BASE_THICKNESS) + 1.0
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

CUTOUTS = [
    {
        "name": "front_display",
        "face": "front",
        "shape": "rectangular",
        "x": 0.0,
        "y": 0.0,
        "z": 14.0,
        "width": 40.0,
        "height": 20.0,
        "diameter": null,
        "depth": 4.0,
        "notes": "Centered display or label window."
    },
    {
        "name": "side_cable",
        "face": "right",
        "shape": "circular",
        "x": 0.0,
        "y": 0.0,
        "z": 9.0,
        "width": null,
        "height": null,
        "diameter": 8.0,
        "depth": 4.0,
        "notes": "Cable pass-through on the right wall."
    }
]
MOUNTING_HOLES = [
    {
        "name": "front_left",
        "x": -28.0,
        "y": 16.0,
        "diameter": 3.2,
        "depth": 3.0
    },
    {
        "name": "front_right",
        "x": 28.0,
        "y": 16.0,
        "diameter": 3.2,
        "depth": 3.0
    },
    {
        "name": "rear_left",
        "x": -28.0,
        "y": -16.0,
        "diameter": 3.2,
        "depth": 3.0
    },
    {
        "name": "rear_right",
        "x": 28.0,
        "y": -16.0,
        "diameter": 3.2,
        "depth": 3.0
    }
]


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
        raise ValueError(f"Unsupported face: {face!r}")

    if shape == "rectangular":
        return (
            workplane
            .center(*center)
            .rect(float(cutout["width"]), float(cutout["height"]))
            .extrude(direction)
        )

    if shape == "circular":
        return workplane.center(*center).circle(float(cutout["diameter"]) / 2.0).extrude(direction)

    raise ValueError(f"Unsupported cutout shape: {shape!r}")


def export_model(model: cq.Workplane) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(model, str(OUTPUT_DIR / f"{PART_NAME}.stl"))
    cq.exporters.export(model, str(OUTPUT_DIR / f"{PART_NAME}.step"))


result = build_enclosure()

if __name__ == "__main__":
    export_model(result)

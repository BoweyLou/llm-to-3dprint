"""Modular robot-vac threshold ramp for a 680 mm wide, 30 mm high threshold.

The design is split into three Bambu A1-printable segments with hidden underside
connector keys. Units are millimeters.

Coordinate conventions:
- X runs across the doorway width.
- Y runs in the robot travel direction, from floor approach (-Y) to threshold (+Y).
- Z=0 is the floor-contact face.
"""

from __future__ import annotations

from math import ceil
from pathlib import Path

import cadquery as cq
from cadquery import exporters


PART_NAME = "robot_vac_threshold_ramp"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# User-provided doorway dimensions.
TOTAL_WIDTH = 680.0
THRESHOLD_HEIGHT = 30.0

# Bambu A1 build volume is 256 x 256 x 256 mm. Keep practical margins for brim
# and placement rather than filling the bed edge to edge.
MAX_SEGMENT_WIDTH = 230.0

# Keep the total front-to-back footprint to 90 mm for tighter door clearances.
OVERALL_DEPTH_TARGET = 90.0
TOP_LANDING_DEPTH = 17.5
RAMP_RUN_DEPTH = OVERALL_DEPTH_TARGET - TOP_LANDING_DEPTH
OVERALL_DEPTH = RAMP_RUN_DEPTH + TOP_LANDING_DEPTH

# Segment layout.
SEAM_GAP = 0.4
SEGMENT_COUNT = ceil(TOTAL_WIDTH / MAX_SEGMENT_WIDTH)
SEGMENT_BODY_WIDTH = (TOTAL_WIDTH - ((SEGMENT_COUNT - 1) * SEAM_GAP)) / SEGMENT_COUNT

# Connector keys: inserted into shallow underside pockets spanning each seam.
CONNECTOR_KEY_SPAN_X = 38.0
CONNECTOR_KEY_DEPTH_Y = 24.0
CONNECTOR_KEY_THICKNESS = 2.6
CONNECTOR_CLEARANCE = 0.35
CONNECTOR_HALF_POCKET_X = (CONNECTOR_KEY_SPAN_X + SEAM_GAP + CONNECTOR_CLEARANCE) / 2.0
CONNECTOR_POCKET_DEPTH_Y = CONNECTOR_KEY_DEPTH_Y + CONNECTOR_CLEARANCE
CONNECTOR_POCKET_Z = CONNECTOR_KEY_THICKNESS + CONNECTOR_CLEARANCE
CONNECTOR_Y_POSITIONS = (-50.0, -20.0, 5.0)

# Low ribs give the wheels a tactile transition without making a sharp obstacle.
TRACTION_RIB_COUNT = 5
TRACTION_RIB_DEPTH_Y = 2.2
TRACTION_RIB_HEIGHT = 0.55
TRACTION_RIB_OVERLAP = 0.25
TRACTION_RIB_EDGE_MARGIN_X = 8.0
TRACTION_RIB_FIRST_Y = -58.0
TRACTION_RIB_SPACING_Y = 14.0


def build_segment(segment_index: int) -> cq.Workplane:
    """Build one printable ramp segment.

    segment_index is zero-based. Segment 0 is the left end, the final segment is
    the right end, and middle segments receive connector pockets on both sides.
    """

    _validate_segment_index(segment_index)
    _validate_dimensions()

    body = _build_wedge(SEGMENT_BODY_WIDTH)
    body = body.union(_build_traction_ribs(SEGMENT_BODY_WIDTH))

    if segment_index > 0:
        body = _cut_connector_pockets(body, side="left")
    if segment_index < SEGMENT_COUNT - 1:
        body = _cut_connector_pockets(body, side="right")

    return body


def build_connector_key() -> cq.Workplane:
    """Build the reusable underside key that bridges two neighboring segments."""

    key = cq.Workplane("XY").box(
        CONNECTOR_KEY_SPAN_X,
        CONNECTOR_KEY_DEPTH_Y,
        CONNECTOR_KEY_THICKNESS,
        centered=(True, True, False),
    )
    key = key.edges("|Z").chamfer(0.35)
    key = key.faces(">Z").edges().chamfer(0.25)
    return key


def build_assembly() -> cq.Assembly:
    """Build a visual assembly with all segments and connector keys seated."""

    assembly = cq.Assembly(name=PART_NAME)

    for index in range(SEGMENT_COUNT):
        segment = build_segment(index)
        assembly.add(
            segment,
            name=f"segment_{index + 1}",
            loc=cq.Location(cq.Vector(_segment_x_offset(index), 0, 0)),
        )

    for seam_index in range(SEGMENT_COUNT - 1):
        seam_x = _seam_x_position(seam_index)
        for key_index, y_pos in enumerate(CONNECTOR_Y_POSITIONS, start=1):
            assembly.add(
                build_connector_key(),
                name=f"connector_s{seam_index + 1}_{key_index}",
                loc=cq.Location(cq.Vector(seam_x, y_pos, 0.0)),
            )

    return assembly


def export_all() -> None:
    """Export STL and STEP files for printing and CAD review."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for index in range(SEGMENT_COUNT):
        segment = build_segment(index)
        stem = f"{PART_NAME}_segment_{index + 1}_of_{SEGMENT_COUNT}"
        exporters.export(segment, str(OUTPUT_DIR / f"{stem}.stl"))
        exporters.export(segment, str(OUTPUT_DIR / f"{stem}.step"))

    key = build_connector_key()
    exporters.export(key, str(OUTPUT_DIR / f"{PART_NAME}_connector_key.stl"))
    exporters.export(key, str(OUTPUT_DIR / f"{PART_NAME}_connector_key.step"))

    build_assembly().save(str(OUTPUT_DIR / f"{PART_NAME}_assembly.step"))


def _build_wedge(width: float) -> cq.Workplane:
    front_y = -RAMP_RUN_DEPTH
    threshold_y = 0.0
    back_y = TOP_LANDING_DEPTH

    profile_yz = [
        (front_y, 0.0),
        (threshold_y, THRESHOLD_HEIGHT),
        (back_y, THRESHOLD_HEIGHT),
        (back_y, 0.0),
    ]

    return (
        cq.Workplane("YZ")
        .polyline(profile_yz)
        .close()
        .extrude(width)
        .translate((-width / 2.0, 0.0, 0.0))
    )


def _build_traction_ribs(width: float) -> cq.Workplane:
    rib_length_x = width - (2.0 * TRACTION_RIB_EDGE_MARGIN_X)
    ribs: cq.Workplane | None = None

    for i in range(TRACTION_RIB_COUNT):
        y_pos = TRACTION_RIB_FIRST_Y + (i * TRACTION_RIB_SPACING_Y)
        z_surface = _top_surface_z_at_y(y_pos)
        rib = (
            cq.Workplane("XY")
            .box(
                rib_length_x,
                TRACTION_RIB_DEPTH_Y,
                TRACTION_RIB_HEIGHT,
                centered=(True, True, True),
            )
            .translate(
                (
                    0.0,
                    y_pos,
                    z_surface + (TRACTION_RIB_HEIGHT / 2.0) - TRACTION_RIB_OVERLAP,
                )
            )
        )
        ribs = rib if ribs is None else ribs.union(rib)

    assert ribs is not None
    return ribs


def _cut_connector_pockets(model: cq.Workplane, side: str) -> cq.Workplane:
    if side not in {"left", "right"}:
        raise ValueError("side must be 'left' or 'right'")

    sign = -1.0 if side == "left" else 1.0
    x_center = sign * ((SEGMENT_BODY_WIDTH / 2.0) - (CONNECTOR_HALF_POCKET_X / 2.0))
    cutter_z = CONNECTOR_POCKET_Z + 0.2

    for y_pos in CONNECTOR_Y_POSITIONS:
        pocket = (
            cq.Workplane("XY")
            .box(
                CONNECTOR_HALF_POCKET_X,
                CONNECTOR_POCKET_DEPTH_Y,
                cutter_z,
                centered=(True, True, True),
            )
            .translate((x_center, y_pos, (cutter_z / 2.0) - 0.1))
        )
        model = model.cut(pocket)

    return model


def _top_surface_z_at_y(y_pos: float) -> float:
    if y_pos <= -RAMP_RUN_DEPTH:
        return 0.0
    if y_pos >= 0.0:
        return THRESHOLD_HEIGHT
    return ((y_pos + RAMP_RUN_DEPTH) / RAMP_RUN_DEPTH) * THRESHOLD_HEIGHT


def _segment_x_offset(index: int) -> float:
    return (
        -(TOTAL_WIDTH / 2.0)
        + (SEGMENT_BODY_WIDTH / 2.0)
        + (index * (SEGMENT_BODY_WIDTH + SEAM_GAP))
    )


def _seam_x_position(seam_index: int) -> float:
    return (
        -(TOTAL_WIDTH / 2.0)
        + ((seam_index + 1) * SEGMENT_BODY_WIDTH)
        + (seam_index * SEAM_GAP)
        + (SEAM_GAP / 2.0)
    )


def _validate_segment_index(segment_index: int) -> None:
    if not 0 <= segment_index < SEGMENT_COUNT:
        raise ValueError(f"segment_index must be between 0 and {SEGMENT_COUNT - 1}")


def _validate_dimensions() -> None:
    if TOTAL_WIDTH <= 0 or THRESHOLD_HEIGHT <= 0:
        raise ValueError("TOTAL_WIDTH and THRESHOLD_HEIGHT must be positive")
    if SEGMENT_BODY_WIDTH > MAX_SEGMENT_WIDTH:
        raise ValueError("segment width exceeds configured print-bed limit")
    if OVERALL_DEPTH > 245.0:
        raise ValueError("ramp depth is too close to the Bambu A1 bed limit")
    for y_pos in CONNECTOR_Y_POSITIONS:
        if _top_surface_z_at_y(y_pos) < CONNECTOR_POCKET_Z + 2.0:
            raise ValueError("connector pocket is too close to the thin front edge")


if __name__ == "__main__":
    export_all()

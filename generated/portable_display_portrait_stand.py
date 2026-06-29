"""Generate a portrait stand for a bare portable display.

All dimensions are millimeters.

Coordinate conventions:
- X runs across the portrait display width, negative left to positive right.
- Y runs front to rear on the bench, positive toward the wall/cable exit.
- Z=0 is the bench-contact face for each printable part.

The separate print parts are exported in print orientation. The assembly preview
places them in their real assembled positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isclose, radians, sin, tan
from pathlib import Path

import cadquery as cq


PART_NAME = "portable_display_portrait_stand"
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / PART_NAME

# Display and viewing assumptions.
MONITOR_WIDTH = 250.0
MONITOR_HEIGHT = 355.0
MONITOR_THICKNESS = 11.0
SCREEN_TILT_DEG = 15.0
SLOT_WIDTH = 12.5
FELT_PAD_ALLOWANCE = SLOT_WIDTH - MONITOR_THICKNESS

# Printer and manufacturing assumptions.
TARGET_BED = 220.0
MATERIAL = "PETG"
NOZZLE_DIAMETER = 0.4
MIN_WALL_THICKNESS = 3.0

# Cable/port assumptions. The plinth may sit below the port zone, but the
# raised shelf/backrest support is kept out of the right-half bottom port area.
CABLE_TURN_DEPTH = 75.0
MIN_CABLE_TURN_DEPTH = 70.0
PORT_KEEP_OUT = "right_half_bottom"
PORT_KEEPOUT_X_START = 0.0
PORT_KEEPOUT_X_END = 88.0
RIGHT_SUPPORT_LOCAL_MIN_X = 22.0
RIGHT_SUPPORT_LOCAL_MAX_X = 46.0

# Assembly layout.
LEFT_FOOT_CENTER_X = -80.0
RIGHT_FOOT_CENTER_X = 82.0
BRIDGE_CENTER_Y = 112.0
RIGHT_SUPPORT_WORLD_MIN_X = RIGHT_FOOT_CENTER_X + RIGHT_SUPPORT_LOCAL_MIN_X

# Flared plinth styling and structural dimensions.
PLINTH_THICKNESS = 8.0
FOOT_FRONT_Y = -8.0
FOOT_REAR_Y = 126.0
FOOT_FRONT_HALF_WIDTH = 42.0
FOOT_REAR_HALF_WIDTH = 54.0

# Lift the display bottom high enough for real plug bodies and cable bend
# radius. The earlier 12.5 mm value fitted the screen edge but not the cables.
MONITOR_BOTTOM_Z = 32.0
PLUG_BODY_CLEARANCE_HEIGHT = 28.0
SIDE_CAPTURE_THICKNESS = 4.0
SIDE_CAPTURE_HEIGHT = 28.0

BACKREST_HEIGHT = 118.0
BACKREST_THICKNESS = 9.0
BACKREST_BASE_HEEL = 20.0

# Single continuous low front skirt. It is modeled in assembled orientation and
# exported diagonally for the K1 bed. The front visible edge stays low, while
# the rear/top edge leans at the screen angle and meets the display bottom.
FASCIA_ASSEMBLED_WIDTH = 262.0
FASCIA_TOP_WIDTH = MONITOR_WIDTH + 4.0
FASCIA_FRONT_Y = -42.0
FASCIA_FRONT_HEIGHT = 7.0
FASCIA_REAR_BOTTOM_Y = -10.0
FASCIA_REAR_HEIGHT = MONITOR_BOTTOM_Z
FASCIA_FRONT_TOP_Y = FASCIA_FRONT_Y + tan(radians(SCREEN_TILT_DEG)) * FASCIA_FRONT_HEIGHT
FASCIA_REAR_TOP_Y = FASCIA_REAR_BOTTOM_Y + tan(radians(SCREEN_TILT_DEG)) * FASCIA_REAR_HEIGHT
FASCIA_REAR_Y = FASCIA_REAR_TOP_Y
FASCIA_DEPTH = FASCIA_REAR_Y - FASCIA_FRONT_Y
FASCIA_HEIGHT = FASCIA_REAR_HEIGHT
MONITOR_CENTER_Y_AT_BOTTOM = FASCIA_REAR_TOP_Y + (SLOT_WIDTH / 2.0)
BACKREST_TARGET_Y_AT_MONITOR_BOTTOM = FASCIA_REAR_TOP_Y + SLOT_WIDTH
BACKREST_FRONT_BASE_Y = BACKREST_TARGET_Y_AT_MONITOR_BOTTOM - (
    tan(radians(SCREEN_TILT_DEG)) * (MONITOR_BOTTOM_Z - PLINTH_THICKNESS)
)
FASCIA_PRINT_ROTATION_DEG = 45.0
FASCIA_REAR_CABLE_POCKET_WIDTH = 142.0
FASCIA_REAR_CABLE_POCKET_X = 48.0
FASCIA_REAR_CABLE_POCKET_DEPTH = 32.0
FASCIA_REAR_CABLE_POCKET_BOTTOM_Z = 1.5

# Right-foot cable trough and rear exit. The front fascia pocket is wider than
# this through-channel; cables enter the pocket at the ports, then sweep into
# this local right-side channel before turning rearward.
CABLE_CHANNEL_LOCAL_X = -19.0
CABLE_CHANNEL_WIDTH = 78.0
CABLE_EXIT_WIDTH = 86.0
CABLE_CHANNEL_START_Y = FASCIA_REAR_BOTTOM_Y - 1.0
CABLE_CHANNEL_END_Y = CABLE_CHANNEL_START_Y + CABLE_TURN_DEPTH
CABLE_BAY_CUT_HEIGHT = MONITOR_BOTTOM_Z + 2.0
ZIP_TIE_SLOT_WIDTH = 3.0
ZIP_TIE_SLOT_LENGTH = 30.0

# M3 hardware.
M3_CLEARANCE_DIAMETER = 3.4
M3_INSERT_DIAMETER = 4.8
M3_INSERT_DEPTH = 5.5
BRIDGE_LENGTH = 212.0
BRIDGE_DEPTH = 18.0
BRIDGE_HEIGHT = 12.0
BRIDGE_Z = PLINTH_THICKNESS
FOOT_INSERT_LOCAL_X = (-16.0, 16.0)

# Fit coupon dimensions.
COUPON_WIDTH = 110.0
COUPON_DEPTH = 122.0
COUPON_SUPPORT_X_MIN = -48.0
COUPON_SUPPORT_X_MAX = -12.0
COUPON_CABLE_CHANNEL_X = 18.0
COUPON_CABLE_CHANNEL_WIDTH = 68.0

# Retrofit spacer/keeper parts for the already-printed v8 assembly. These sit
# on top of the foot plinths, brace the skirt from behind, and provide the real
# load-bearing ledge for the monitor bottom edge.
SKIRT_SPACER_LEFT_WIDTH = 42.0
SKIRT_SPACER_RIGHT_WIDTH = 28.0
SKIRT_SPACER_LEFT_CENTER_X = LEFT_FOOT_CENTER_X
SKIRT_SPACER_RIGHT_CENTER_X = RIGHT_SUPPORT_WORLD_MIN_X + (SKIRT_SPACER_RIGHT_WIDTH / 2.0) + 2.0
SKIRT_SPACER_HEIGHT = MONITOR_BOTTOM_Z - PLINTH_THICKNESS
SKIRT_SPACER_TAPE_CLEARANCE = 0.6
SKIRT_SPACER_REAR_Y = BACKREST_TARGET_Y_AT_MONITOR_BOTTOM + 2.0
SKIRT_SPACER_FRONT_LOWER_Y = (
    FASCIA_REAR_BOTTOM_Y
    + tan(radians(SCREEN_TILT_DEG)) * PLINTH_THICKNESS
    + SKIRT_SPACER_TAPE_CLEARANCE
)
SKIRT_SPACER_FRONT_UPPER_Y = FASCIA_REAR_TOP_Y + SKIRT_SPACER_TAPE_CLEARANCE
SKIRT_SPACER_TOP_DEPTH = SKIRT_SPACER_REAR_Y - SKIRT_SPACER_FRONT_UPPER_Y


@dataclass(frozen=True)
class Bounds:
    x: float
    y: float
    z: float


def build_left_foot() -> cq.Workplane:
    """Build the left printable cradle foot in print orientation."""

    part = _foot_plinth()
    part = part.union(_backrest(-38.0, 38.0))
    part = part.union(_side_capture(-42.0, side="left"))
    part = part.cut(_heat_set_insert_cuts(FOOT_INSERT_LOCAL_X))
    return _soften_print_part(part)


def build_right_foot() -> cq.Workplane:
    """Build the right printable foot with the cable channel and corner cradle."""

    part = _foot_plinth()
    # The right bottom support starts beyond PORT_KEEPOUT_X_END in the assembled
    # position, leaving the right-half port cluster clear.
    part = part.union(_backrest(RIGHT_SUPPORT_LOCAL_MIN_X, RIGHT_SUPPORT_LOCAL_MAX_X))
    part = part.union(_side_capture(RIGHT_SUPPORT_LOCAL_MAX_X + 2.0, side="right"))
    part = part.cut(_cable_trough_cut())
    part = part.cut(_zip_tie_slot_cuts())
    part = part.cut(_heat_set_insert_cuts(FOOT_INSERT_LOCAL_X))
    return _soften_print_part(part)


def build_front_fascia_skirt() -> cq.Workplane:
    """Build the continuous skirt in print orientation for the K1 bed."""

    return build_front_fascia_skirt_assembled().rotate(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        FASCIA_PRINT_ROTATION_DEG,
    )


def build_front_fascia_skirt_assembled() -> cq.Workplane:
    """Build the continuous low skirt in its assembled orientation."""

    skirt = _front_fascia_skirt_body()
    skirt = skirt.cut(_front_fascia_rear_cable_pocket_cut())
    return _soften_print_part(skirt)


def build_rear_bridge() -> cq.Workplane:
    """Build the screw-down rear bridge rail in print orientation."""

    bridge = _box(0.0, 0.0, 0.0, BRIDGE_LENGTH, BRIDGE_DEPTH, BRIDGE_HEIGHT)
    bridge = bridge.cut(_bridge_clearance_holes())
    return bridge


def build_skirt_spacer_left() -> cq.Workplane:
    """Build the left retrofit spacer/keeper in print orientation."""

    return _soften_print_part(_skirt_spacer(SKIRT_SPACER_LEFT_WIDTH))


def build_skirt_spacer_right() -> cq.Workplane:
    """Build the right retrofit spacer/keeper in print orientation."""

    return _soften_print_part(_skirt_spacer(SKIRT_SPACER_RIGHT_WIDTH))


def build_fit_coupon() -> cq.Workplane:
    """Build a compact section of the real right-side stand interface."""

    base = _coupon_plinth()
    coupon = base.union(_coupon_front_fascia())
    coupon = coupon.union(_backrest(COUPON_SUPPORT_X_MIN, COUPON_SUPPORT_X_MAX, height=58.0))
    coupon = coupon.cut(_coupon_cable_channel_cut())
    coupon = coupon.cut(_coupon_fascia_cable_pocket_cut())
    return _soften_print_part(coupon)


def build_assembly_preview() -> cq.Compound:
    """Return a stand assembly preview with all parts in assembled positions."""

    left = build_left_foot().translate((LEFT_FOOT_CENTER_X, 0.0, 0.0))
    right = build_right_foot().translate((RIGHT_FOOT_CENTER_X, 0.0, 0.0))
    fascia = build_front_fascia_skirt_assembled()
    bridge = build_rear_bridge().translate((0.0, BRIDGE_CENTER_Y, BRIDGE_Z))
    left_spacer = build_skirt_spacer_left().translate(
        (SKIRT_SPACER_LEFT_CENTER_X, 0.0, PLINTH_THICKNESS)
    )
    right_spacer = build_skirt_spacer_right().translate(
        (SKIRT_SPACER_RIGHT_CENTER_X, 0.0, PLINTH_THICKNESS)
    )
    monitor = build_monitor_clearance_preview()
    return cq.Compound.makeCompound(
        [
            left.val(),
            right.val(),
            fascia.val(),
            bridge.val(),
            left_spacer.val(),
            right_spacer.val(),
            monitor.val(),
        ]
    )


def build_fit_coupon_usage_preview() -> cq.Compound:
    """Return a non-printing preview showing how the coupon is meant to be used."""

    coupon = build_fit_coupon()
    monitor = _monitor_slice_preview().translate((COUPON_SUPPORT_X_MIN + 17.0, 0.0, 0.0))
    cable = _cable_route_preview(COUPON_CABLE_CHANNEL_X, CABLE_CHANNEL_START_Y, COUPON_DEPTH - 40.0)
    return cq.Compound.makeCompound([coupon.val(), monitor.val(), cable.val()])


def build_monitor_clearance_preview() -> cq.Workplane:
    """Build a non-print monitor envelope for the assembly STEP preview."""

    screen = _box(
        0.0,
        MONITOR_CENTER_Y_AT_BOTTOM,
        MONITOR_BOTTOM_Z,
        MONITOR_WIDTH,
        MONITOR_THICKNESS,
        MONITOR_HEIGHT,
    )
    return screen.rotate(
        (0.0, MONITOR_CENTER_Y_AT_BOTTOM, MONITOR_BOTTOM_Z),
        (1.0, MONITOR_CENTER_Y_AT_BOTTOM, MONITOR_BOTTOM_Z),
        -SCREEN_TILT_DEG,
    )


def _monitor_slice_preview() -> cq.Workplane:
    """Build a short non-print monitor slice for the coupon usage preview."""

    seat_z = MONITOR_BOTTOM_Z
    screen = _box(
        0.0,
        MONITOR_CENTER_Y_AT_BOTTOM,
        seat_z,
        28.0,
        MONITOR_THICKNESS,
        95.0,
    )
    return screen.rotate(
        (0.0, MONITOR_CENTER_Y_AT_BOTTOM, seat_z),
        (1.0, MONITOR_CENTER_Y_AT_BOTTOM, seat_z),
        -SCREEN_TILT_DEG,
    )


def _cable_route_preview(center_x: float, start_y: float, end_y: float) -> cq.Workplane:
    """Build non-print cable cylinders that show the intended hidden route."""

    length = end_y - start_y
    cables = []
    for dx, diameter, z_pos in ((-12.0, 5.0, 7.0), (0.0, 5.0, 14.0), (12.0, 6.0, 21.0)):
        cables.append(
            cq.Workplane("XZ")
            .center(center_x + dx, z_pos)
            .circle(diameter / 2.0)
            .extrude(length)
            .translate((0.0, start_y, 0.0))
        )
    return _union_solids(cables)


def build_print_parts() -> dict[str, cq.Workplane]:
    """Build only the printable parts, not the monitor preview."""

    return {
        "left_foot": build_left_foot(),
        "right_foot": build_right_foot(),
        "front_fascia_skirt": build_front_fascia_skirt(),
        "rear_bridge": build_rear_bridge(),
        "skirt_spacer_left": build_skirt_spacer_left(),
        "skirt_spacer_right": build_skirt_spacer_right(),
        "fit_coupon": build_fit_coupon(),
    }


def validate_design() -> dict[str, Bounds]:
    """Validate the CAD-level assumptions before export."""
    return validate_parts(build_print_parts())


def validate_parts(parts: dict[str, cq.Workplane]) -> dict[str, Bounds]:
    """Validate already-built printable parts."""

    if not isclose(SCREEN_TILT_DEG, 15.0, abs_tol=0.001):
        raise ValueError(f"SCREEN_TILT_DEG must remain 15.0, got {SCREEN_TILT_DEG:g}")
    if SLOT_WIDTH < MONITOR_THICKNESS + 1.0:
        raise ValueError("SLOT_WIDTH leaves less than 1 mm total allowance for protective pads.")
    if CABLE_TURN_DEPTH < MIN_CABLE_TURN_DEPTH:
        raise ValueError("CABLE_TURN_DEPTH is below the measured cable depth.")
    if MONITOR_BOTTOM_Z < PLUG_BODY_CLEARANCE_HEIGHT + 3.0:
        raise ValueError("MONITOR_BOTTOM_Z leaves less than 3 mm plug body clearance.")
    if RIGHT_SUPPORT_WORLD_MIN_X < PORT_KEEPOUT_X_END:
        raise ValueError("Right cradle support intersects the declared port keepout.")
    if FASCIA_ASSEMBLED_WIDTH < MONITOR_WIDTH + 12.0:
        raise ValueError("Front fascia must visually cover the full monitor width.")
    if FASCIA_HEIGHT > MONITOR_BOTTOM_Z + 0.5:
        raise ValueError("Front fascia is too tall; it should only kiss the bottom edge.")
    if FOOT_FRONT_Y < FASCIA_REAR_BOTTOM_Y:
        raise ValueError("Foot plinths must sit behind the continuous front fascia.")
    if not isclose(SKIRT_SPACER_HEIGHT + PLINTH_THICKNESS, MONITOR_BOTTOM_Z, abs_tol=0.001):
        raise ValueError("Retrofit spacer top must land at the monitor bottom height.")
    if SKIRT_SPACER_TOP_DEPTH < MONITOR_THICKNESS + 1.0:
        raise ValueError("Retrofit spacer top ledge is too shallow to support the monitor edge.")
    right_spacer_min_x = SKIRT_SPACER_RIGHT_CENTER_X - (SKIRT_SPACER_RIGHT_WIDTH / 2.0)
    if right_spacer_min_x <= PORT_KEEPOUT_X_END:
        raise ValueError("Right retrofit spacer must stay outside the port keepout.")
    cable_channel_world_min_x = RIGHT_FOOT_CENTER_X + CABLE_CHANNEL_LOCAL_X - (CABLE_CHANNEL_WIDTH / 2.0)
    cable_channel_world_max_x = RIGHT_FOOT_CENTER_X + CABLE_CHANNEL_LOCAL_X + (CABLE_CHANNEL_WIDTH / 2.0)
    if cable_channel_world_max_x >= RIGHT_SUPPORT_WORLD_MIN_X:
        raise ValueError("Cable channel must not cut into the right rear support.")
    if cable_channel_world_min_x > PORT_KEEPOUT_X_START + 30.0:
        raise ValueError("Cable channel starts too far right to catch the port-side cable bundle.")
    backrest_y_at_monitor_bottom = BACKREST_FRONT_BASE_Y + (
        tan(radians(SCREEN_TILT_DEG)) * (MONITOR_BOTTOM_Z - PLINTH_THICKNESS)
    )
    slot_depth = backrest_y_at_monitor_bottom - FASCIA_REAR_TOP_Y
    if not isclose(slot_depth, SLOT_WIDTH, abs_tol=0.001):
        raise ValueError("Backrest front face must be tied to the front fascia by SLOT_WIDTH at screen bottom height.")

    bounds: dict[str, Bounds] = {}
    for name, part in parts.items():
        part_bounds = _bounds(part)
        bounds[name] = part_bounds
        if part_bounds.x > TARGET_BED or part_bounds.y > TARGET_BED:
            raise ValueError(
                f"{name} footprint {part_bounds.x:.1f} x {part_bounds.y:.1f} exceeds {TARGET_BED:g} mm bed."
            )
    return bounds


def export_parts() -> None:
    """Export printable STL/STEP parts and an assembly preview STEP."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parts = build_print_parts()
    bounds = validate_parts(parts)

    for name, part in parts.items():
        cq.exporters.export(part, str(OUTPUT_DIR / f"{PART_NAME}_{name}.stl"))
        cq.exporters.export(part, str(OUTPUT_DIR / f"{PART_NAME}_{name}.step"))

    assembly = build_assembly_preview()
    cq.exporters.export(assembly, str(OUTPUT_DIR / f"{PART_NAME}_assembly_preview.step"))
    cq.exporters.export(
        assembly,
        str(OUTPUT_DIR / f"{PART_NAME}_assembly_preview_not_for_printing.stl"),
    )
    coupon_preview = build_fit_coupon_usage_preview()
    cq.exporters.export(coupon_preview, str(OUTPUT_DIR / f"{PART_NAME}_fit_coupon_usage_preview.step"))
    cq.exporters.export(
        coupon_preview,
        str(OUTPUT_DIR / f"{PART_NAME}_fit_coupon_usage_preview_not_for_printing.stl"),
    )

    _write_bounds_report(bounds)
    _write_usage_preview_png()


def _foot_plinth() -> cq.Workplane:
    """Subtle rounded plinth that flares wider toward the rear."""

    points = [
        (-FOOT_FRONT_HALF_WIDTH + 10.0, FOOT_FRONT_Y),
        (FOOT_FRONT_HALF_WIDTH - 10.0, FOOT_FRONT_Y),
        (FOOT_FRONT_HALF_WIDTH - 2.0, FOOT_FRONT_Y + 4.0),
        (FOOT_FRONT_HALF_WIDTH + 7.0, 16.0),
        (FOOT_REAR_HALF_WIDTH, FOOT_REAR_Y - 32.0),
        (FOOT_REAR_HALF_WIDTH - 5.0, FOOT_REAR_Y - 14.0),
        (FOOT_REAR_HALF_WIDTH - 18.0, FOOT_REAR_Y),
        (-FOOT_REAR_HALF_WIDTH + 18.0, FOOT_REAR_Y),
        (-FOOT_REAR_HALF_WIDTH + 5.0, FOOT_REAR_Y - 14.0),
        (-FOOT_REAR_HALF_WIDTH, FOOT_REAR_Y - 32.0),
        (-FOOT_FRONT_HALF_WIDTH - 7.0, 16.0),
        (-FOOT_FRONT_HALF_WIDTH + 2.0, FOOT_FRONT_Y + 4.0),
    ]
    return cq.Workplane("XY").polyline(points).close().extrude(PLINTH_THICKNESS)


def _coupon_plinth() -> cq.Workplane:
    half_width = COUPON_WIDTH / 2.0
    points = [
        (-half_width + 8.0, -42.0),
        (half_width - 8.0, -42.0),
        (half_width - 1.0, -34.0),
        (half_width, COUPON_DEPTH - 42.0),
        (half_width - 8.0, COUPON_DEPTH - 22.0),
        (-half_width + 8.0, COUPON_DEPTH - 22.0),
        (-half_width, COUPON_DEPTH - 42.0),
        (-half_width + 1.0, -34.0),
    ]
    return cq.Workplane("XY").polyline(points).close().extrude(PLINTH_THICKNESS)


def _front_fascia_skirt_body() -> cq.Workplane:
    return _front_fascia_skirt_section(FASCIA_ASSEMBLED_WIDTH)


def _front_fascia_rear_cable_pocket_cut() -> cq.Workplane:
    return _box(
        FASCIA_REAR_CABLE_POCKET_X,
        FASCIA_REAR_Y - (FASCIA_REAR_CABLE_POCKET_DEPTH / 2.0) + 1.0,
        FASCIA_REAR_CABLE_POCKET_BOTTOM_Z,
        FASCIA_REAR_CABLE_POCKET_WIDTH,
        FASCIA_REAR_CABLE_POCKET_DEPTH + 1.0,
        FASCIA_HEIGHT + 2.0,
    )


def _coupon_front_fascia() -> cq.Workplane:
    return _front_fascia_skirt_section(COUPON_WIDTH)


def _front_fascia_skirt_section(width: float) -> cq.Workplane:
    """Build the side-profiled fascia as a single low angled skirt."""

    points = [
        (FASCIA_FRONT_Y, 0.0),
        (FASCIA_REAR_BOTTOM_Y, 0.0),
        (FASCIA_REAR_TOP_Y, FASCIA_REAR_HEIGHT),
        (FASCIA_FRONT_TOP_Y, FASCIA_FRONT_HEIGHT),
    ]
    return (
        cq.Workplane("YZ")
        .polyline(points)
        .close()
        .extrude(width)
        .translate((-width / 2.0, 0.0, 0.0))
    )


def _skirt_spacer(width: float) -> cq.Workplane:
    """Build a retrofit wedge that keys the skirt and lifts the screen edge."""

    points = [
        (SKIRT_SPACER_FRONT_LOWER_Y, 0.0),
        (SKIRT_SPACER_REAR_Y, 0.0),
        (SKIRT_SPACER_REAR_Y, SKIRT_SPACER_HEIGHT),
        (SKIRT_SPACER_FRONT_UPPER_Y, SKIRT_SPACER_HEIGHT),
    ]
    return (
        cq.Workplane("YZ")
        .polyline(points)
        .close()
        .extrude(width)
        .translate((-width / 2.0, 0.0, 0.0))
    )


def _backrest(x_min: float, x_max: float, *, height: float = BACKREST_HEIGHT) -> cq.Workplane:
    width = x_max - x_min
    front_base_y = BACKREST_FRONT_BASE_Y
    front_top_y = front_base_y + tan(radians(SCREEN_TILT_DEG)) * height
    heel_y = front_base_y + BACKREST_THICKNESS + BACKREST_BASE_HEEL
    points = [
        (front_base_y, PLINTH_THICKNESS),
        (front_top_y, PLINTH_THICKNESS + height),
        (front_top_y + BACKREST_THICKNESS, PLINTH_THICKNESS + height),
        (heel_y, PLINTH_THICKNESS),
    ]
    return cq.Workplane("YZ").polyline(points).close().extrude(width).translate((x_min, 0.0, 0.0))


def _side_capture(x_outer: float, *, side: str) -> cq.Workplane:
    sign = -1.0 if side == "left" else 1.0
    center_x = x_outer + sign * (SIDE_CAPTURE_THICKNESS / 2.0)
    front_y = FASCIA_REAR_TOP_Y + 1.0
    rear_y = BACKREST_FRONT_BASE_Y + 4.0
    depth = rear_y - front_y
    # The capture can sit just outside the flared plinth at the very front, so
    # it reaches the bench instead of starting as a slicer-visible floating fin.
    return _box(
        center_x,
        (front_y + rear_y) / 2.0,
        0.0,
        SIDE_CAPTURE_THICKNESS,
        depth,
        MONITOR_BOTTOM_Z + SIDE_CAPTURE_HEIGHT,
    )


def _cable_trough_cut() -> cq.Workplane:
    channel = _box(
        CABLE_CHANNEL_LOCAL_X,
        (CABLE_CHANNEL_START_Y + CABLE_CHANNEL_END_Y) / 2.0,
        0.0,
        CABLE_CHANNEL_WIDTH,
        CABLE_TURN_DEPTH,
        CABLE_BAY_CUT_HEIGHT,
    )
    return channel.union(
        _box(
            CABLE_CHANNEL_LOCAL_X,
            CABLE_CHANNEL_END_Y + 14.0,
            0.0,
            CABLE_EXIT_WIDTH,
            28.0,
            CABLE_BAY_CUT_HEIGHT,
        )
    )


def _coupon_cable_channel_cut() -> cq.Workplane:
    channel_end_y = min(CABLE_CHANNEL_END_Y, COUPON_DEPTH - 48.0)
    channel = _box(
        COUPON_CABLE_CHANNEL_X,
        (CABLE_CHANNEL_START_Y + channel_end_y) / 2.0,
        0.0,
        COUPON_CABLE_CHANNEL_WIDTH,
        channel_end_y - CABLE_CHANNEL_START_Y,
        CABLE_BAY_CUT_HEIGHT,
    )
    rear_exit = _box(
        COUPON_CABLE_CHANNEL_X,
        channel_end_y + 11.0,
        0.0,
        COUPON_CABLE_CHANNEL_WIDTH + 8.0,
        22.0,
        CABLE_BAY_CUT_HEIGHT,
    )
    return channel.union(rear_exit)


def _coupon_fascia_cable_pocket_cut() -> cq.Workplane:
    return _box(
        COUPON_CABLE_CHANNEL_X,
        FASCIA_REAR_Y - (FASCIA_REAR_CABLE_POCKET_DEPTH / 2.0) + 1.0,
        FASCIA_REAR_CABLE_POCKET_BOTTOM_Z,
        COUPON_CABLE_CHANNEL_WIDTH + 10.0,
        FASCIA_REAR_CABLE_POCKET_DEPTH + 1.0,
        FASCIA_HEIGHT + 2.0,
    )


def _zip_tie_slot_cuts() -> cq.Workplane:
    slots = []
    for y_pos in (CABLE_CHANNEL_START_Y + 22.0, CABLE_CHANNEL_END_Y - 14.0):
        slots.append(
            _box(
                CABLE_CHANNEL_LOCAL_X,
                y_pos,
                0.0,
                ZIP_TIE_SLOT_LENGTH,
                ZIP_TIE_SLOT_WIDTH,
                PLINTH_THICKNESS + 1.0,
            )
        )
    return _union_solids(slots)


def _heat_set_insert_cuts(x_positions: tuple[float, ...]) -> cq.Workplane:
    cuts = []
    for x_pos in x_positions:
        cuts.append(
            cq.Workplane("XY")
            .workplane(offset=PLINTH_THICKNESS - M3_INSERT_DEPTH)
            .center(x_pos, BRIDGE_CENTER_Y)
            .circle(M3_INSERT_DIAMETER / 2.0)
            .extrude(M3_INSERT_DEPTH + 1.0)
        )
    return _union_solids(cuts)


def _bridge_clearance_holes() -> cq.Workplane:
    x_positions = [
        LEFT_FOOT_CENTER_X + FOOT_INSERT_LOCAL_X[0],
        LEFT_FOOT_CENTER_X + FOOT_INSERT_LOCAL_X[1],
        RIGHT_FOOT_CENTER_X + FOOT_INSERT_LOCAL_X[0],
        RIGHT_FOOT_CENTER_X + FOOT_INSERT_LOCAL_X[1],
    ]
    cuts = []
    for x_pos in x_positions:
        cuts.append(
            cq.Workplane("XY")
            .center(x_pos, 0.0)
            .circle(M3_CLEARANCE_DIAMETER / 2.0)
            .extrude(BRIDGE_HEIGHT + 1.0)
        )
    return _union_solids(cuts)


def _box(
    center_x: float,
    center_y: float,
    bottom_z: float,
    size_x: float,
    size_y: float,
    size_z: float,
) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .box(size_x, size_y, size_z, centered=(True, True, False))
        .translate((center_x, center_y, bottom_z))
    )


def _union_solids(solids: list[cq.Workplane]) -> cq.Workplane:
    if not solids:
        raise ValueError("Cannot union an empty list of solids.")
    result = solids[0]
    for solid in solids[1:]:
        result = result.union(solid)
    return result


def _soften_print_part(part: cq.Workplane) -> cq.Workplane:
    return part


def _bounds(part: cq.Workplane) -> Bounds:
    box = part.val().BoundingBox()
    return Bounds(
        x=round(box.xlen, 3),
        y=round(box.ylen, 3),
        z=round(box.zlen, 3),
    )


def _write_bounds_report(bounds: dict[str, Bounds]) -> None:
    report_path = OUTPUT_DIR / f"{PART_NAME}_bounds.txt"
    lines = [
        f"part_name={PART_NAME}",
        f"material={MATERIAL}",
        f"target_bed_mm={TARGET_BED:g}",
        f"screen_tilt_deg={SCREEN_TILT_DEG:g}",
        f"slot_width_mm={SLOT_WIDTH:g}",
        f"felt_pad_allowance_mm={FELT_PAD_ALLOWANCE:g}",
        f"cable_turn_depth_mm={CABLE_TURN_DEPTH:g}",
        f"port_keepout={PORT_KEEP_OUT}",
        f"monitor_bottom_z_mm={MONITOR_BOTTOM_Z:g}",
        f"plug_body_clearance_height_mm={PLUG_BODY_CLEARANCE_HEIGHT:g}",
        f"cable_channel_width_mm={CABLE_CHANNEL_WIDTH:g}",
        (
            "right_foot_cable_channel_world_x_mm="
            f"{RIGHT_FOOT_CENTER_X + CABLE_CHANNEL_LOCAL_X - (CABLE_CHANNEL_WIDTH / 2.0):g}"
            ".."
            f"{RIGHT_FOOT_CENTER_X + CABLE_CHANNEL_LOCAL_X + (CABLE_CHANNEL_WIDTH / 2.0):g}"
        ),
        (
            "front_fascia_cable_pocket_world_x_mm="
            f"{FASCIA_REAR_CABLE_POCKET_X - (FASCIA_REAR_CABLE_POCKET_WIDTH / 2.0):g}"
            ".."
            f"{FASCIA_REAR_CABLE_POCKET_X + (FASCIA_REAR_CABLE_POCKET_WIDTH / 2.0):g}"
        ),
        (
            "fit_coupon_cable_channel_x_mm="
            f"{COUPON_CABLE_CHANNEL_X - (COUPON_CABLE_CHANNEL_WIDTH / 2.0):g}"
            ".."
            f"{COUPON_CABLE_CHANNEL_X + (COUPON_CABLE_CHANNEL_WIDTH / 2.0):g}"
        ),
        f"backrest_front_base_y_mm={BACKREST_FRONT_BASE_Y:g}",
        f"front_fascia_assembled_width_mm={FASCIA_ASSEMBLED_WIDTH:g}",
        f"front_fascia_height_mm={FASCIA_HEIGHT:g}",
        f"front_fascia_print_rotation_deg={FASCIA_PRINT_ROTATION_DEG:g}",
        f"skirt_spacer_height_mm={SKIRT_SPACER_HEIGHT:g}",
        f"skirt_spacer_assembled_top_z_mm={SKIRT_SPACER_HEIGHT + PLINTH_THICKNESS:g}",
        f"skirt_spacer_top_depth_mm={SKIRT_SPACER_TOP_DEPTH:g}",
        (
            "right_skirt_spacer_world_x_mm="
            f"{SKIRT_SPACER_RIGHT_CENTER_X - (SKIRT_SPACER_RIGHT_WIDTH / 2.0):g}"
            ".."
            f"{SKIRT_SPACER_RIGHT_CENTER_X + (SKIRT_SPACER_RIGHT_WIDTH / 2.0):g}"
        ),
    ]
    for name, item in sorted(bounds.items()):
        lines.append(f"{name}: {item.x:g} x {item.y:g} x {item.z:g} mm")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_usage_preview_png() -> None:
    """Write a quick side-section image of the corrected coupon geometry."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle

    seat_z = MONITOR_BOTTOM_Z
    angle = -radians(SCREEN_TILT_DEG)

    def rotate_screen_point(local_y_pos: float, z_pos: float) -> tuple[float, float]:
        y_pos = MONITOR_CENTER_Y_AT_BOTTOM + local_y_pos
        rel_y = y_pos - MONITOR_CENTER_Y_AT_BOTTOM
        rel_z = z_pos - seat_z
        return (
            MONITOR_CENTER_Y_AT_BOTTOM + rel_y * cos(angle) - rel_z * sin(angle),
            seat_z + rel_y * sin(angle) + rel_z * cos(angle),
        )

    monitor_points = [
        rotate_screen_point(-MONITOR_THICKNESS / 2.0, seat_z),
        rotate_screen_point(MONITOR_THICKNESS / 2.0, seat_z),
        rotate_screen_point(MONITOR_THICKNESS / 2.0, seat_z + 95.0),
        rotate_screen_point(-MONITOR_THICKNESS / 2.0, seat_z + 95.0),
    ]
    backrest_height = 58.0
    backrest_front_base_y = BACKREST_FRONT_BASE_Y
    backrest_front_top_y = backrest_front_base_y + tan(radians(SCREEN_TILT_DEG)) * backrest_height
    backrest_points = [
        (backrest_front_base_y, PLINTH_THICKNESS),
        (backrest_front_top_y, PLINTH_THICKNESS + backrest_height),
        (backrest_front_top_y + BACKREST_THICKNESS, PLINTH_THICKNESS + backrest_height),
        (backrest_front_base_y + BACKREST_THICKNESS + BACKREST_BASE_HEEL, PLINTH_THICKNESS),
    ]
    fascia_points = [
        (FASCIA_FRONT_Y, 0.0),
        (FASCIA_REAR_BOTTOM_Y, 0.0),
        (FASCIA_REAR_TOP_Y, FASCIA_REAR_HEIGHT),
        (FASCIA_FRONT_TOP_Y, FASCIA_FRONT_HEIGHT),
    ]
    channel_end_y = min(CABLE_CHANNEL_END_Y, COUPON_DEPTH - 48.0)

    fig, (ax, ax_plan) = plt.subplots(1, 2, figsize=(13, 4.8), dpi=160)
    ax.add_patch(Rectangle((-42.0, 0.0), COUPON_DEPTH, PLINTH_THICKNESS, color="#242424", alpha=0.9))
    ax.add_patch(Polygon(fascia_points, closed=True, facecolor="#111111", edgecolor="#000000", linewidth=1.2))
    ax.add_patch(Polygon(backrest_points, closed=True, facecolor="#111111", edgecolor="#000000", linewidth=1.2))
    ax.add_patch(
        Rectangle(
            (CABLE_CHANNEL_START_Y, 0.8),
            channel_end_y - CABLE_CHANNEL_START_Y,
            PLUG_BODY_CLEARANCE_HEIGHT,
            facecolor="#f6fafc",
            edgecolor="#0c8fb3",
            linewidth=1.6,
        )
    )
    ax.add_patch(Polygon(monitor_points, closed=True, facecolor="#b9d7ff", edgecolor="#2d5f9a", alpha=0.55, linewidth=1.6))
    ax.add_patch(FancyArrowPatch((channel_end_y - 8.0, 4.0), (channel_end_y + 17.0, 4.0), arrowstyle="->", mutation_scale=14, color="#0c8fb3", linewidth=1.6))

    ax.text(FASCIA_FRONT_Y + 6.0, FASCIA_FRONT_HEIGHT + 4.0, "low angled skirt", fontsize=9)
    ax.text(FASCIA_REAR_TOP_Y + 4.0, seat_z + 5.0, "lifted open slot", fontsize=9, color="#2d5f9a")
    ax.text(CABLE_CHANNEL_START_Y + 5.0, PLUG_BODY_CLEARANCE_HEIGHT + 3.0, "28 mm plug bay", fontsize=9, color="#0c8fb3")
    ax.text(channel_end_y + 10.0, 19.5, "rear exit", fontsize=9, color="#0c8fb3")
    ax.text(-47.0, 2.0, "front", fontsize=9)
    ax.text(77.0, 2.0, "rear", fontsize=9)

    ax.set_title("v8 fit coupon side section: lifted, widened cable/plug bay")
    ax.set_xlabel("Y on bench: front to rear (mm)")
    ax.set_ylabel("Z height (mm)")
    ax.set_xlim(-50.0, 88.0)
    ax.set_ylim(0.0, 78.0)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#dddddd", linewidth=0.5)

    half_width = COUPON_WIDTH / 2.0
    footprint_points = [
        (-half_width + 8.0, -42.0),
        (half_width - 8.0, -42.0),
        (half_width - 1.0, -34.0),
        (half_width, COUPON_DEPTH - 42.0),
        (half_width - 8.0, COUPON_DEPTH - 22.0),
        (-half_width + 8.0, COUPON_DEPTH - 22.0),
        (-half_width, COUPON_DEPTH - 42.0),
        (-half_width + 1.0, -34.0),
    ]
    ax_plan.add_patch(Polygon(footprint_points, closed=True, facecolor="#242424", edgecolor="#000000", alpha=0.9))
    ax_plan.add_patch(
        Rectangle(
            (-half_width, FASCIA_FRONT_Y),
            COUPON_WIDTH,
            FASCIA_REAR_Y - FASCIA_FRONT_Y,
            facecolor="#111111",
            edgecolor="#000000",
            linewidth=1.1,
        )
    )
    ax_plan.add_patch(
        Rectangle(
            (COUPON_SUPPORT_X_MIN, BACKREST_FRONT_BASE_Y),
            COUPON_SUPPORT_X_MAX - COUPON_SUPPORT_X_MIN,
            BACKREST_THICKNESS + BACKREST_BASE_HEEL,
            facecolor="#555555",
            edgecolor="#000000",
            linewidth=1.0,
        )
    )
    ax_plan.add_patch(
        Rectangle(
            (
            COUPON_CABLE_CHANNEL_X - COUPON_CABLE_CHANNEL_WIDTH / 2.0,
                CABLE_CHANNEL_START_Y,
            ),
            COUPON_CABLE_CHANNEL_WIDTH,
            channel_end_y - CABLE_CHANNEL_START_Y,
            facecolor="#f6fafc",
            edgecolor="#0c8fb3",
            linewidth=1.5,
        )
    )
    ax_plan.add_patch(FancyArrowPatch((COUPON_CABLE_CHANNEL_X, channel_end_y - 5.0), (COUPON_CABLE_CHANNEL_X, channel_end_y + 18.0), arrowstyle="->", mutation_scale=14, color="#0c8fb3", linewidth=1.5))
    ax_plan.text(COUPON_SUPPORT_X_MIN - 1.0, 22.0, "backrest support", fontsize=8, rotation=90, color="white")
    ax_plan.text(COUPON_CABLE_CHANNEL_X - 14.0, 15.0, "cable slot", fontsize=8, rotation=90, color="#0c8fb3")
    ax_plan.text(-33.0, FASCIA_FRONT_Y + 8.0, "continuous skirt", fontsize=8, color="white")
    ax_plan.text(-44.0, -45.0, "front", fontsize=8)
    ax_plan.text(28.0, 84.0, "rear exit", fontsize=8, color="#0c8fb3")
    ax_plan.set_title("Coupon top view")
    ax_plan.set_xlabel("X across display (mm)")
    ax_plan.set_ylabel("Y front to rear (mm)")
    ax_plan.set_xlim(-50.0, 50.0)
    ax_plan.set_ylim(-48.0, 90.0)
    ax_plan.set_aspect("equal", adjustable="box")
    ax_plan.grid(True, color="#dddddd", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / f"{PART_NAME}_v8_widened_cable_bay_coupon_usage.png")
    plt.close(fig)


if __name__ == "__main__":
    export_parts()

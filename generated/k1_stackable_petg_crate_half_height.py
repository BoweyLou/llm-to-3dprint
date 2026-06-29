"""Generate a half-height stackable PETG crate for the Creality K1.

All dimensions are millimeters.

Coordinate conventions:
- X and Y are centered on the box footprint.
- Z=0 is the print-bed contact face.
- The box prints upright with the open top facing up.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import struct

import cadquery as cq


PART_NAME = "k1_stackable_petg_crate_half_height"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output" / PART_NAME

TARGET_BUILD_VOLUME = (220.0, 220.0, 250.0)
PETG_DENSITY_G_PER_MM3 = 1.27e-3

# Main envelope. The K1 is 220 x 220 x 250 mm; this keeps the near-full plate
# footprint from the tall box but drops the height to a more crate-like size.
TOP_OUTER = 216.0
BOTTOM_LOCATOR = 204.0
STACK_STOP = 213.5
BOX_HEIGHT = 120.0

LOCATOR_HEIGHT = 6.0
STACK_STOP_HEIGHT = 12.0
BASE_THICKNESS = 2.2
WALL_THICKNESS = 1.2
TOP_RIM_HEIGHT = 10.0
TOP_RIM_WALL = 3.2

# Functional features.
HAND_SLOT_LENGTH = 66.0
HAND_SLOT_HEIGHT = 22.0
HAND_SLOT_CENTER_Z = 72.0
HAND_PAD_LENGTH = 92.0
HAND_PAD_HEIGHT = 38.0
HAND_PAD_THICKNESS = 1.6

LABEL_WIDTH = 112.0
LABEL_HEIGHT = 30.0
LABEL_CENTER_Z = 54.0
LABEL_THICKNESS = 1.4

VERTICAL_RIB_WIDTH = 5.0
VERTICAL_RIB_DEPTH = 4.8
VERTICAL_RIB_Z_MIN = 15.0
VERTICAL_RIB_Z_MAX = BOX_HEIGHT - TOP_RIM_HEIGHT - 3.0
FLOOR_RIB_HEIGHT = 1.2
FLOOR_RIB_WIDTH = 5.0

VISIBILITY_HOLE_WIDTH = 17.0
VISIBILITY_HOLE_HEIGHT = 16.0
VISIBILITY_HOLE_CUT_DEPTH = TOP_OUTER + 18.0
FRONT_BACK_HOLE_XS = (-92.0, -69.0, -46.0, -23.0, 0.0, 23.0, 46.0, 69.0, 92.0)
FRONT_BACK_HOLE_ZS = (25.0, 44.0, 63.0, 82.0, 101.0)
SIDE_HOLE_YS = FRONT_BACK_HOLE_XS
SIDE_HOLE_ZS = FRONT_BACK_HOLE_ZS

LABEL_KEEP_OUT_X = LABEL_WIDTH / 2.0 + 10.0
LABEL_KEEP_OUT_Z_MIN = LABEL_CENTER_Z - (LABEL_HEIGHT / 2.0) - 8.0
LABEL_KEEP_OUT_Z_MAX = LABEL_CENTER_Z + (LABEL_HEIGHT / 2.0) + 8.0
HAND_KEEP_OUT_Y = HAND_PAD_LENGTH / 2.0 + 8.0
HAND_KEEP_OUT_Z_MIN = HAND_SLOT_CENTER_Z - (HAND_PAD_HEIGHT / 2.0) - 8.0
HAND_KEEP_OUT_Z_MAX = HAND_SLOT_CENTER_Z + (HAND_PAD_HEIGHT / 2.0) + 8.0


@dataclass(frozen=True)
class Bounds:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float

    @property
    def size(self) -> tuple[float, float, float]:
        return (
            self.max_x - self.min_x,
            self.max_y - self.min_y,
            self.max_z - self.min_z,
        )


def build_box() -> cq.Workplane:
    """Build the printable storage box as one body."""

    outer = _loft_rect(
        [
            (0.0, BOTTOM_LOCATOR, BOTTOM_LOCATOR),
            (LOCATOR_HEIGHT, BOTTOM_LOCATOR, BOTTOM_LOCATOR),
            (STACK_STOP_HEIGHT, STACK_STOP, STACK_STOP),
            (BOX_HEIGHT, TOP_OUTER, TOP_OUTER),
        ]
    )

    inner = _loft_rect(
        [
            (BASE_THICKNESS, _inner_size(BASE_THICKNESS), _inner_size(BASE_THICKNESS)),
            (
                BOX_HEIGHT - TOP_RIM_HEIGHT,
                _inner_size(BOX_HEIGHT - TOP_RIM_HEIGHT),
                _inner_size(BOX_HEIGHT - TOP_RIM_HEIGHT),
            ),
            (BOX_HEIGHT + 1.0, _top_opening(), _top_opening()),
        ]
    )

    box = outer.cut(inner)
    for feature in [
        _vertical_ribs(),
        _floor_ribs(),
        _hand_pad("left"),
        _hand_pad("right"),
        _label_plaque(),
    ]:
        box = box.union(feature)

    box = box.cut(_visibility_hole_cutter())
    box = box.cut(_hand_slot_cutter())
    return box


def build_stack_interface_coupon() -> cq.Workplane:
    """Build a small two-piece stack-interface coupon for fit testing."""

    receiver = _stack_receiver_coupon().translate((-58.0, 0.0, 0.0))
    locator = _stack_locator_coupon().translate((58.0, 0.0, 0.0))
    return receiver.union(locator)


def export_all() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    box = build_box()
    coupon = build_stack_interface_coupon()

    box_stl = OUTPUT_DIR / f"{PART_NAME}.stl"
    box_step = OUTPUT_DIR / f"{PART_NAME}.step"
    coupon_stl = OUTPUT_DIR / f"{PART_NAME}_stack_interface_coupon.stl"
    coupon_step = OUTPUT_DIR / f"{PART_NAME}_stack_interface_coupon.step"
    manifest_path = OUTPUT_DIR / f"{PART_NAME}_manifest.json"

    cq.exporters.export(box, str(box_stl), tolerance=0.12, angularTolerance=0.18)
    cq.exporters.export(box, str(box_step))
    cq.exporters.export(coupon, str(coupon_stl), tolerance=0.1, angularTolerance=0.18)
    cq.exporters.export(coupon, str(coupon_step))

    box_bounds = _stl_bounds(box_stl)
    coupon_bounds = _stl_bounds(coupon_stl)
    _validate_bounds(box_bounds, TARGET_BUILD_VOLUME)
    _validate_bounds(coupon_bounds, TARGET_BUILD_VOLUME)

    box_volume_mm3 = float(box.val().Volume())
    manifest = {
        "part_name": PART_NAME,
        "target_printer": "Creality K1",
        "target_build_volume_mm": list(TARGET_BUILD_VOLUME),
        "material": "black PETG",
        "design_intent": "near-full-plate, half-height stackable crate with denser diamond cutouts",
        "outputs": {
            "box_stl": str(box_stl),
            "box_step": str(box_step),
            "stack_interface_coupon_stl": str(coupon_stl),
            "stack_interface_coupon_step": str(coupon_step),
        },
        "box_bounds_mm": asdict(box_bounds) | {"size": list(box_bounds.size)},
        "coupon_bounds_mm": asdict(coupon_bounds) | {"size": list(coupon_bounds.size)},
        "stacking": {
            "bottom_locator_mm": BOTTOM_LOCATOR,
            "top_opening_mm": _top_opening(),
            "clearance_per_side_mm": (_top_opening() - BOTTOM_LOCATOR) / 2.0,
            "locator_drop_depth_mm": STACK_STOP_HEIGHT,
        },
        "features": {
            "hand_slot_length_mm": HAND_SLOT_LENGTH,
            "hand_slot_height_mm": HAND_SLOT_HEIGHT,
            "hand_slot_center_z_mm": HAND_SLOT_CENTER_Z,
            "label_plaque_width_mm": LABEL_WIDTH,
            "label_plaque_height_mm": LABEL_HEIGHT,
            "label_center_z_mm": LABEL_CENTER_Z,
            "visibility_hole_shape": "dense support-friendly diamonds",
            "visibility_hole_width_mm": VISIBILITY_HOLE_WIDTH,
            "visibility_hole_height_mm": VISIBILITY_HOLE_HEIGHT,
            "front_back_visibility_hole_count": len(_front_back_hole_centers()),
            "side_visibility_hole_count": len(_side_hole_centers()),
        },
        "estimated_solid_model_volume_cm3": round(box_volume_mm3 / 1000.0, 2),
        "estimated_petg_mass_from_cad_g": round(box_volume_mm3 * PETG_DENSITY_G_PER_MM3, 1),
        "print_notes": [
            "Print upright with the open top up.",
            "Supports should be off; all designed overhangs are shallow or vertical cuts.",
            "Dense diamond visibility holes are kept out of the label plaque, hand pads, rim, and base.",
            "At full size, avoid an outside brim unless your slicer keeps it inside the 220 mm bed.",
            "Suggested starting point: 0.24 mm layers, 3 wall loops, 8-10% gyroid or cubic infill.",
            "The crate keeps the tall box stack interface, so the existing quarter validation print is still a useful stack-clearance reference.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _outer_size(z_pos: float) -> float:
    if z_pos <= LOCATOR_HEIGHT:
        return BOTTOM_LOCATOR
    if z_pos <= STACK_STOP_HEIGHT:
        t = (z_pos - LOCATOR_HEIGHT) / (STACK_STOP_HEIGHT - LOCATOR_HEIGHT)
        return _lerp(BOTTOM_LOCATOR, STACK_STOP, t)
    t = (z_pos - STACK_STOP_HEIGHT) / (BOX_HEIGHT - STACK_STOP_HEIGHT)
    return _lerp(STACK_STOP, TOP_OUTER, t)


def _inner_size(z_pos: float) -> float:
    return _outer_size(z_pos) - (2.0 * WALL_THICKNESS)


def _top_opening() -> float:
    return TOP_OUTER - (2.0 * TOP_RIM_WALL)


def _lerp(start: float, end: float, t: float) -> float:
    return start + ((end - start) * max(0.0, min(1.0, t)))


def _loft_rect(profiles: list[tuple[float, float, float]]) -> cq.Workplane:
    first_z, first_width, first_depth = profiles[0]
    work = cq.Workplane("XY").workplane(offset=first_z).rect(first_width, first_depth)
    previous_z = first_z
    for z_pos, width, depth in profiles[1:]:
        work = work.workplane(offset=z_pos - previous_z).rect(width, depth)
        previous_z = z_pos
    return work.loft(ruled=True, combine=True)


def _loft_polygon(profiles: list[tuple[float, list[tuple[float, float]]]]) -> cq.Workplane:
    first_z, first_points = profiles[0]
    work = cq.Workplane("XY").workplane(offset=first_z).polyline(first_points).close()
    previous_z = first_z
    for z_pos, points in profiles[1:]:
        work = work.workplane(offset=z_pos - previous_z).polyline(points).close()
        previous_z = z_pos
    return work.loft(ruled=True, combine=True)


def _vertical_ribs() -> cq.Workplane:
    ribs: cq.Workplane | None = None
    for x_pos in (-74.0, 74.0):
        ribs = _combine(ribs, _face_rib("front", x_pos))
    for x_pos in (-74.0, 0.0, 74.0):
        ribs = _combine(ribs, _face_rib("back", x_pos))
    for y_pos in (-74.0, 74.0):
        ribs = _combine(ribs, _face_rib("left", y_pos))
        ribs = _combine(ribs, _face_rib("right", y_pos))
    if ribs is None:
        raise RuntimeError("no ribs were created")
    return ribs


def _face_rib(face: str, center: float) -> cq.Workplane:
    z_positions = [VERTICAL_RIB_Z_MIN, VERTICAL_RIB_Z_MAX]
    profiles: list[tuple[float, list[tuple[float, float]]]] = []

    for z_pos in z_positions:
        half = _outer_size(z_pos) / 2.0
        if face == "front":
            x0 = center - (VERTICAL_RIB_WIDTH / 2.0)
            x1 = center + (VERTICAL_RIB_WIDTH / 2.0)
            y0 = -half
            y1 = y0 + VERTICAL_RIB_DEPTH
            points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif face == "back":
            x0 = center - (VERTICAL_RIB_WIDTH / 2.0)
            x1 = center + (VERTICAL_RIB_WIDTH / 2.0)
            y1 = half
            y0 = y1 - VERTICAL_RIB_DEPTH
            points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif face == "left":
            y0 = center - (VERTICAL_RIB_WIDTH / 2.0)
            y1 = center + (VERTICAL_RIB_WIDTH / 2.0)
            x0 = -half
            x1 = x0 + VERTICAL_RIB_DEPTH
            points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        elif face == "right":
            y0 = center - (VERTICAL_RIB_WIDTH / 2.0)
            y1 = center + (VERTICAL_RIB_WIDTH / 2.0)
            x1 = half
            x0 = x1 - VERTICAL_RIB_DEPTH
            points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        else:
            raise ValueError(f"unknown face {face!r}")
        profiles.append((z_pos, points))

    return _loft_polygon(profiles)


def _floor_ribs() -> cq.Workplane:
    rib_z = BASE_THICKNESS
    span = BOTTOM_LOCATOR - 28.0
    ribs: cq.Workplane | None = None
    for y_pos in (-54.0, 0.0, 54.0):
        ribs = _combine(ribs, _box(span, FLOOR_RIB_WIDTH, FLOOR_RIB_HEIGHT, 0.0, y_pos, rib_z))
    for x_pos in (-54.0, 54.0):
        ribs = _combine(ribs, _box(FLOOR_RIB_WIDTH, span, FLOOR_RIB_HEIGHT, x_pos, 0.0, rib_z))
    if ribs is None:
        raise RuntimeError("no floor ribs were created")
    return ribs


def _hand_pad(side: str) -> cq.Workplane:
    sign = -1.0 if side == "left" else 1.0
    center_x = sign * ((TOP_OUTER / 2.0) - (HAND_PAD_THICKNESS / 2.0))
    return _box(
        HAND_PAD_THICKNESS,
        HAND_PAD_LENGTH,
        HAND_PAD_HEIGHT,
        center_x,
        0.0,
        HAND_SLOT_CENTER_Z - (HAND_PAD_HEIGHT / 2.0),
    )


def _label_plaque() -> cq.Workplane:
    center_y = -(TOP_OUTER / 2.0) + (LABEL_THICKNESS / 2.0)
    return _box(
        LABEL_WIDTH,
        LABEL_THICKNESS,
        LABEL_HEIGHT,
        0.0,
        center_y,
        LABEL_CENTER_Z - (LABEL_HEIGHT / 2.0),
    )


def _hand_slot_cutter() -> cq.Workplane:
    return (
        cq.Workplane("YZ")
        .center(0.0, HAND_SLOT_CENTER_Z)
        .slot2D(HAND_SLOT_LENGTH, HAND_SLOT_HEIGHT)
        .extrude(TOP_OUTER + 12.0, both=True)
    )


def _visibility_hole_cutter() -> cq.Workplane:
    cutters: cq.Workplane | None = None
    for x_pos, z_pos in _front_back_hole_centers():
        cutters = _combine(cutters, _front_back_diamond_cutter(x_pos, z_pos))
    for y_pos, z_pos in _side_hole_centers():
        cutters = _combine(cutters, _side_diamond_cutter(y_pos, z_pos))
    if cutters is None:
        raise RuntimeError("no visibility holes were created")
    return cutters


def _front_back_hole_centers() -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for z_pos in FRONT_BACK_HOLE_ZS:
        for x_pos in FRONT_BACK_HOLE_XS:
            if _inside_label_keepout(x_pos, z_pos):
                continue
            centers.append((x_pos, z_pos))
    return centers


def _side_hole_centers() -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for z_pos in SIDE_HOLE_ZS:
        for y_pos in SIDE_HOLE_YS:
            if _inside_hand_keepout(y_pos, z_pos):
                continue
            centers.append((y_pos, z_pos))
    return centers


def _inside_label_keepout(x_pos: float, z_pos: float) -> bool:
    return (
        abs(x_pos) <= LABEL_KEEP_OUT_X
        and LABEL_KEEP_OUT_Z_MIN <= z_pos <= LABEL_KEEP_OUT_Z_MAX
    )


def _inside_hand_keepout(y_pos: float, z_pos: float) -> bool:
    return (
        abs(y_pos) <= HAND_KEEP_OUT_Y
        and HAND_KEEP_OUT_Z_MIN <= z_pos <= HAND_KEEP_OUT_Z_MAX
    )


def _front_back_diamond_cutter(x_pos: float, z_pos: float) -> cq.Workplane:
    return (
        cq.Workplane("XZ")
        .center(x_pos, z_pos)
        .polyline(_diamond_points())
        .close()
        .extrude(VISIBILITY_HOLE_CUT_DEPTH, both=True)
    )


def _side_diamond_cutter(y_pos: float, z_pos: float) -> cq.Workplane:
    return (
        cq.Workplane("YZ")
        .center(y_pos, z_pos)
        .polyline(_diamond_points())
        .close()
        .extrude(VISIBILITY_HOLE_CUT_DEPTH, both=True)
    )


def _diamond_points() -> list[tuple[float, float]]:
    return [
        (0.0, VISIBILITY_HOLE_HEIGHT / 2.0),
        (VISIBILITY_HOLE_WIDTH / 2.0, 0.0),
        (0.0, -VISIBILITY_HOLE_HEIGHT / 2.0),
        (-VISIBILITY_HOLE_WIDTH / 2.0, 0.0),
    ]


def _stack_receiver_coupon() -> cq.Workplane:
    outer = _loft_rect([(0.0, 84.0, 84.0), (22.0, 84.0, 84.0)])
    inner = _loft_rect([(BASE_THICKNESS, 70.0, 70.0), (23.0, 70.0, 70.0)])
    rim = outer.cut(inner)
    top_lip = _box(84.0, 4.0, 8.0, 0.0, -42.0 + 2.0, 14.0).union(
        _box(4.0, 84.0, 8.0, -42.0 + 2.0, 0.0, 14.0)
    )
    return rim.union(top_lip)


def _stack_locator_coupon() -> cq.Workplane:
    locator = _loft_rect(
        [
            (0.0, 58.0, 58.0),
            (LOCATOR_HEIGHT, 58.0, 58.0),
            (STACK_STOP_HEIGHT, 70.0, 70.0),
            (18.0, 72.0, 72.0),
        ]
    )
    return locator.cut(_loft_rect([(BASE_THICKNESS, 50.0, 50.0), (19.0, 50.0, 50.0)]))


def _box(
    width: float,
    depth: float,
    height: float,
    center_x: float,
    center_y: float,
    z_min: float,
) -> cq.Workplane:
    return (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .translate((center_x, center_y, z_min))
    )


def _combine(current: cq.Workplane | None, addition: cq.Workplane) -> cq.Workplane:
    return addition if current is None else current.union(addition)


def _bounds(part: cq.Workplane) -> Bounds:
    bb = part.val().BoundingBox()
    return Bounds(
        min_x=round(bb.xmin, 3),
        max_x=round(bb.xmax, 3),
        min_y=round(bb.ymin, 3),
        max_y=round(bb.ymax, 3),
        min_z=round(bb.zmin, 3),
        max_z=round(bb.zmax, 3),
    )


def _stl_bounds(path: Path) -> Bounds:
    data = path.read_bytes()
    triangle_count = struct.unpack("<I", data[80:84])[0]
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    offset = 84
    for _ in range(triangle_count):
        offset += 12
        for _vertex in range(3):
            x_pos, y_pos, z_pos = struct.unpack("<fff", data[offset : offset + 12])
            offset += 12
            xs.append(x_pos)
            ys.append(y_pos)
            zs.append(z_pos)
        offset += 2
    return Bounds(
        min_x=round(min(xs), 3),
        max_x=round(max(xs), 3),
        min_y=round(min(ys), 3),
        max_y=round(max(ys), 3),
        min_z=round(min(zs), 3),
        max_z=round(max(zs), 3),
    )


def _validate_bounds(bounds: Bounds, build_volume: tuple[float, float, float]) -> None:
    for axis, size, limit in zip(("X", "Y", "Z"), bounds.size, build_volume):
        if size > limit:
            raise ValueError(f"{axis} size {size:.3f} exceeds build limit {limit:.3f}")


def main() -> None:
    manifest = export_all()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

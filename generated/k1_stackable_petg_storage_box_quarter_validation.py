"""Generate four quarter-size validation boxes for the K1 storage box.

The validation boxes preserve the storage-box proportions and features, but
minimum wall, rim, base, and clearance dimensions are kept printable instead of
being scaled down literally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import struct

import cadquery as cq


PART_NAME = "k1_stackable_petg_storage_box_quarter_validation"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output" / "k1_stackable_petg_storage_box"
TARGET_BUILD_VOLUME = (220.0, 220.0, 250.0)
PETG_DENSITY_G_PER_MM3 = 1.27e-3

TOP_OUTER = 54.0
BOTTOM_LOCATOR = 50.5
STACK_STOP = 53.3
BOX_HEIGHT = 59.5

LOCATOR_HEIGHT = 2.4
STACK_STOP_HEIGHT = 4.0
BASE_THICKNESS = 1.6
WALL_THICKNESS = 1.2
TOP_RIM_HEIGHT = 4.0
TOP_RIM_WALL = 1.0

HAND_SLOT_LENGTH = 16.0
HAND_SLOT_HEIGHT = 7.0
HAND_SLOT_CENTER_Z = 39.0
HAND_PAD_LENGTH = 24.0
HAND_PAD_HEIGHT = 16.0
HAND_PAD_THICKNESS = 1.2

LABEL_WIDTH = 28.0
LABEL_HEIGHT = 12.0
LABEL_CENTER_Z = 24.0
LABEL_THICKNESS = 0.8

RIB_WIDTH = 1.2
RIB_DEPTH = 1.6
RIB_Z_MIN = 5.0
RIB_Z_MAX = BOX_HEIGHT - TOP_RIM_HEIGHT - 1.5
FLOOR_RIB_HEIGHT = 0.8
FLOOR_RIB_WIDTH = 1.4

VISIBILITY_HOLE_WIDTH = 6.0
VISIBILITY_HOLE_HEIGHT = 8.0
VISIBILITY_HOLE_CUT_DEPTH = TOP_OUTER + 8.0
FRONT_BACK_HOLE_XS = (-18.0, 0.0, 18.0)
FRONT_BACK_HOLE_ZS = (14.0, 36.0, 49.0)
SIDE_HOLE_YS = (-18.0, 0.0, 18.0)
SIDE_HOLE_ZS = (16.0, 51.0)

LABEL_KEEP_OUT_X = LABEL_WIDTH / 2.0 + 4.0
LABEL_KEEP_OUT_Z_MIN = LABEL_CENTER_Z - (LABEL_HEIGHT / 2.0) - 5.0
LABEL_KEEP_OUT_Z_MAX = LABEL_CENTER_Z + (LABEL_HEIGHT / 2.0) + 5.0
HAND_KEEP_OUT_Y = HAND_PAD_LENGTH / 2.0 + 4.0
HAND_KEEP_OUT_Z_MIN = HAND_SLOT_CENTER_Z - (HAND_PAD_HEIGHT / 2.0) - 4.0
HAND_KEEP_OUT_Z_MAX = HAND_SLOT_CENTER_Z + (HAND_PAD_HEIGHT / 2.0) + 4.0

PLATE_COPY_SPACING = 72.0


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


def build_quarter_box() -> cq.Workplane:
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
    for feature in (
        _vertical_ribs(),
        _floor_ribs(),
        _hand_pad("left"),
        _hand_pad("right"),
        _label_plaque(),
    ):
        box = box.union(feature)
    box = box.cut(_visibility_hole_cutter())
    box = box.cut(_hand_slot_cutter())
    return box


def build_four_box_plate() -> cq.Workplane:
    quarter = build_quarter_box()
    plate: cq.Workplane | None = None
    half = PLATE_COPY_SPACING / 2.0
    for x_pos, y_pos in ((-half, -half), (half, -half), (-half, half), (half, half)):
        plate = _combine(plate, quarter.translate((x_pos, y_pos, 0.0)))
    if plate is None:
        raise RuntimeError("no plate copies were created")
    return plate


def export_all() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    single = build_quarter_box()
    plate = build_four_box_plate()

    single_stl = OUTPUT_DIR / f"{PART_NAME}_single.stl"
    plate_stl = OUTPUT_DIR / f"{PART_NAME}_four_on_plate.stl"
    single_step = OUTPUT_DIR / f"{PART_NAME}_single.step"
    plate_step = OUTPUT_DIR / f"{PART_NAME}_four_on_plate.step"
    manifest_path = OUTPUT_DIR / f"{PART_NAME}_manifest.json"

    cq.exporters.export(single, str(single_stl), tolerance=0.08, angularTolerance=0.16)
    cq.exporters.export(plate, str(plate_stl), tolerance=0.08, angularTolerance=0.16)
    cq.exporters.export(single, str(single_step))
    cq.exporters.export(plate, str(plate_step))

    single_bounds = _stl_bounds(single_stl)
    plate_bounds = _stl_bounds(plate_stl)
    _validate_bounds(single_bounds, TARGET_BUILD_VOLUME)
    _validate_bounds(plate_bounds, TARGET_BUILD_VOLUME)

    single_volume_mm3 = float(single.val().Volume())
    manifest = {
        "part_name": PART_NAME,
        "purpose": "Four printable quarter-size storage box validation copies for stacking and visibility checks.",
        "target_printer": "Creality K1",
        "target_build_volume_mm": list(TARGET_BUILD_VOLUME),
        "outputs": {
            "single_stl": str(single_stl),
            "single_step": str(single_step),
            "four_on_plate_stl": str(plate_stl),
            "four_on_plate_step": str(plate_step),
        },
        "single_bounds_mm": asdict(single_bounds) | {"size": list(single_bounds.size)},
        "four_on_plate_bounds_mm": asdict(plate_bounds) | {"size": list(plate_bounds.size)},
        "quarter_validation_dimensions_mm": {
            "top_outer": TOP_OUTER,
            "bottom_locator": BOTTOM_LOCATOR,
            "height": BOX_HEIGHT,
            "wall_thickness": WALL_THICKNESS,
            "base_thickness": BASE_THICKNESS,
            "top_opening": _top_opening(),
            "stack_clearance_per_side": (_top_opening() - BOTTOM_LOCATOR) / 2.0,
        },
        "features": {
            "copy_count": 4,
            "visibility_hole_shape": "diamond",
            "visibility_hole_width_mm": VISIBILITY_HOLE_WIDTH,
            "visibility_hole_height_mm": VISIBILITY_HOLE_HEIGHT,
            "front_back_visibility_hole_count": len(_front_back_hole_centers()),
            "side_visibility_hole_count": len(_side_hole_centers()),
            "hand_slot_length_mm": HAND_SLOT_LENGTH,
            "hand_slot_height_mm": HAND_SLOT_HEIGHT,
            "label_plaque_width_mm": LABEL_WIDTH,
            "label_plaque_height_mm": LABEL_HEIGHT,
        },
        "estimated_single_cad_mass_g": round(single_volume_mm3 * PETG_DENSITY_G_PER_MM3, 2),
        "estimated_four_cad_mass_g": round(single_volume_mm3 * 4.0 * PETG_DENSITY_G_PER_MM3, 2),
        "print_notes": [
            "Print the four-on-plate STL upright as one validation job.",
            "Use PETG with supports off.",
            "The mini boxes are quarter-envelope sized, but minimum wall and stack dimensions are kept printable.",
            "Validate stacking by checking all four combinations, then by stacking all four in one column.",
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
    for x_pos in (-18.0, 18.0):
        ribs = _combine(ribs, _face_rib("front", x_pos))
    for x_pos in (-18.0, 0.0, 18.0):
        ribs = _combine(ribs, _face_rib("back", x_pos))
    for y_pos in (-18.0, 18.0):
        ribs = _combine(ribs, _face_rib("left", y_pos))
        ribs = _combine(ribs, _face_rib("right", y_pos))
    if ribs is None:
        raise RuntimeError("no ribs were created")
    return ribs


def _face_rib(face: str, center: float) -> cq.Workplane:
    profiles: list[tuple[float, list[tuple[float, float]]]] = []
    for z_pos in (RIB_Z_MIN, RIB_Z_MAX):
        half = _outer_size(z_pos) / 2.0
        if face == "front":
            x0 = center - (RIB_WIDTH / 2.0)
            x1 = center + (RIB_WIDTH / 2.0)
            y0 = -half
            y1 = y0 + RIB_DEPTH
        elif face == "back":
            x0 = center - (RIB_WIDTH / 2.0)
            x1 = center + (RIB_WIDTH / 2.0)
            y1 = half
            y0 = y1 - RIB_DEPTH
        elif face == "left":
            y0 = center - (RIB_WIDTH / 2.0)
            y1 = center + (RIB_WIDTH / 2.0)
            x0 = -half
            x1 = x0 + RIB_DEPTH
        elif face == "right":
            y0 = center - (RIB_WIDTH / 2.0)
            y1 = center + (RIB_WIDTH / 2.0)
            x1 = half
            x0 = x1 - RIB_DEPTH
        else:
            raise ValueError(f"unknown face {face!r}")
        profiles.append((z_pos, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    return _loft_polygon(profiles)


def _floor_ribs() -> cq.Workplane:
    ribs: cq.Workplane | None = None
    span = BOTTOM_LOCATOR - 10.0
    for y_pos in (-14.0, 14.0):
        ribs = _combine(ribs, _box(span, FLOOR_RIB_WIDTH, FLOOR_RIB_HEIGHT, 0.0, y_pos, BASE_THICKNESS))
    for x_pos in (-14.0, 14.0):
        ribs = _combine(ribs, _box(FLOOR_RIB_WIDTH, span, FLOOR_RIB_HEIGHT, x_pos, 0.0, BASE_THICKNESS))
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
        .extrude(TOP_OUTER + 8.0, both=True)
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
    print(json.dumps(export_all(), indent=2))


if __name__ == "__main__":
    main()

"""Generate the K1 crate V2 light-slot artifact family.

All dimensions are millimeters.

Coordinate conventions:
- X and Y are centered on the crate footprint.
- Z=0 is the print-bed contact face.
- The crate prints upright with the open top facing up.

This generator uses the OpenCascade Python bindings directly because the local
CadQuery import path is currently blocked by an OCP/IVtk import mismatch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import struct

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Builder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.gp import gp_Pnt, gp_Vec
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.StlAPI import StlAPI_Writer
from OCP.TopoDS import TopoDS_Compound, TopoDS_Shape


PART_NAME = "k1_stackable_petg_crate_v2_light_slots"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output" / PART_NAME

TARGET_BUILD_VOLUME = (220.0, 220.0, 250.0)
BED_CENTER_OFFSET = 110.0
PETG_DENSITY_G_PER_MM3 = 1.27e-3
PLA_DENSITY_G_PER_MM3 = 1.24e-3
PREVIOUS_PETG_SLICER_ESTIMATE_G = 287.84
PREVIOUS_FAILED_FAMILY_CAD_ESTIMATE_G = 440.5

# Native K1-fit envelope. This is not a scaled STL workaround.
TOP_OUTER = 212.5
BOTTOM_LOCATOR = 200.5
STACK_STOP = 210.0
BOX_HEIGHT = 100.0

LOCATOR_HEIGHT = 5.0
STACK_STOP_HEIGHT = 10.0
BASE_THICKNESS = 1.6
WALL_THICKNESS = 0.9
TOP_RIM_HEIGHT = 8.0
TOP_RIM_WALL = 2.1

# Support-free handhold geometry. The top is peaked so there is no long bridge.
HAND_SLOT_WIDTH = 68.0
HAND_SLOT_HEIGHT = 24.0
HAND_SLOT_CENTER_Z = 58.0
HAND_PAD_WIDTH = 82.0
HAND_PAD_HEIGHT = 32.0
HAND_PAD_THICKNESS = 0.8

LABEL_WIDTH = 100.0
LABEL_HEIGHT = 24.0
LABEL_CENTER_Z = 45.0
LABEL_THICKNESS = 0.9

VERTICAL_RIB_WIDTH = 3.5
VERTICAL_RIB_DEPTH = 2.4
VERTICAL_RIB_Z_MIN = 13.0
VERTICAL_RIB_Z_MAX = BOX_HEIGHT - TOP_RIM_HEIGHT - 3.0
FLOOR_RIB_HEIGHT = 0.6
FLOOR_RIB_WIDTH = 3.5

# Visibility slots use short 45-degree cap facets rather than diamond points.
SLOT_WIDTH = 10.0
SLOT_HEIGHT = 24.0
FACE_CUT_DEPTH = 12.0
HANDLE_CUT_DEPTH = 14.0
SLOT_ROW_ZS = (24.0, 74.0)
SLOT_XS_PRIMARY = (-88.0, -66.0, -44.0, -22.0, 0.0, 22.0, 44.0, 66.0, 88.0)
SLOT_XS_STAGGERED = (-77.0, -55.0, -33.0, -11.0, 11.0, 33.0, 55.0, 77.0)
MIN_SLOT_LIGAMENT_MM = 12.0

LABEL_KEEP_OUT_X = LABEL_WIDTH / 2.0 + 8.0
LABEL_KEEP_OUT_Z_MIN = LABEL_CENTER_Z - (LABEL_HEIGHT / 2.0) - 7.0
LABEL_KEEP_OUT_Z_MAX = LABEL_CENTER_Z + (LABEL_HEIGHT / 2.0) + 7.0
HAND_KEEP_OUT_Y = HAND_PAD_WIDTH / 2.0 + 7.0
HAND_KEEP_OUT_Z_MIN = HAND_SLOT_CENTER_Z - (HAND_PAD_HEIGHT / 2.0) - 4.0
HAND_KEEP_OUT_Z_MAX = HAND_SLOT_CENTER_Z + (HAND_PAD_HEIGHT / 2.0) + 7.0


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


def build_crate() -> TopoDS_Shape:
    """Build the support-free V2 crate as one OpenCascade shape."""

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

    crate = _cut(outer, inner, "open crate interior")
    for feature in _additive_features():
        crate = _fuse(crate, feature, "crate reinforcing feature")

    cutters = _compound(_visibility_slot_cutters() + _side_handle_cutters())
    return _cut(crate, cutters, "support-free wall and handle cutouts")


def build_validation_coupon() -> TopoDS_Shape:
    """Build the small first-print coupon with slots, handle, and stack detail."""

    wall = _wall_feature_coupon().Moved(_translation(-42.0, 0.0, 0.0))
    receiver = _stack_receiver_coupon().Moved(_translation(54.0, -36.0, 0.0))
    locator = _stack_locator_coupon().Moved(_translation(54.0, 36.0, 0.0))
    return _compound([wall, receiver, locator])


def export_all() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    crate = build_crate()
    coupon = build_validation_coupon()

    crate_stl = OUTPUT_DIR / f"{PART_NAME}.stl"
    crate_step = OUTPUT_DIR / f"{PART_NAME}.step"
    crate_bed_stl = OUTPUT_DIR / f"{PART_NAME}_bed_placed.stl"
    coupon_stl = OUTPUT_DIR / f"{PART_NAME}_validation_coupon.stl"
    coupon_step = OUTPUT_DIR / f"{PART_NAME}_validation_coupon.step"
    coupon_bed_stl = OUTPUT_DIR / f"{PART_NAME}_validation_coupon_bed_placed.stl"
    manifest_path = OUTPUT_DIR / f"{PART_NAME}_manifest.json"

    _export_stl(crate, crate_stl, linear_deflection=0.12, angular_deflection=0.18)
    _export_step(crate, crate_step)
    _export_stl(
        crate.Moved(_translation(BED_CENTER_OFFSET, BED_CENTER_OFFSET, 0.0)),
        crate_bed_stl,
        linear_deflection=0.12,
        angular_deflection=0.18,
    )
    _export_stl(coupon, coupon_stl, linear_deflection=0.10, angular_deflection=0.18)
    _export_step(coupon, coupon_step)
    _export_stl(
        coupon.Moved(_translation(BED_CENTER_OFFSET, BED_CENTER_OFFSET, 0.0)),
        coupon_bed_stl,
        linear_deflection=0.10,
        angular_deflection=0.18,
    )

    crate_bounds = _stl_bounds(crate_stl)
    crate_bed_bounds = _stl_bounds(crate_bed_stl)
    coupon_bounds = _stl_bounds(coupon_stl)
    coupon_bed_bounds = _stl_bounds(coupon_bed_stl)
    _validate_bounds(crate_bounds, TARGET_BUILD_VOLUME)
    _validate_bounds(coupon_bounds, TARGET_BUILD_VOLUME)
    _validate_bed_placed_bounds(crate_bed_bounds, TARGET_BUILD_VOLUME)
    _validate_bed_placed_bounds(coupon_bed_bounds, TARGET_BUILD_VOLUME)

    crate_volume_mm3 = _volume(crate)
    coupon_volume_mm3 = _volume(coupon)
    front_back_count = len(_front_slot_centers()) + len(_back_slot_centers())
    side_count = len(_left_slot_centers()) + len(_right_slot_centers())
    bed_bounds = _bed_placement_bounds(crate_bounds)

    manifest = {
        "part_name": PART_NAME,
        "target_printer": "Creality K1",
        "target_build_volume_mm": list(TARGET_BUILD_VOLUME),
        "material": "PETG",
        "design_intent": "native K1 support-free V2 crate: lighter slots, no diamond stress points, self-stack only",
        "outputs": {
            "crate_stl": str(crate_stl),
            "crate_step": str(crate_step),
            "crate_bed_placed_stl_for_slicers": str(crate_bed_stl),
            "validation_coupon_stl": str(coupon_stl),
            "validation_coupon_step": str(coupon_step),
            "validation_coupon_bed_placed_stl_for_slicers": str(coupon_bed_stl),
            "manifest": str(manifest_path),
        },
        "crate_bounds_mm": asdict(crate_bounds) | {"size": list(crate_bounds.size)},
        "crate_bed_placed_bounds_mm": asdict(crate_bed_bounds) | {"size": list(crate_bed_bounds.size)},
        "coupon_bounds_mm": asdict(coupon_bounds) | {"size": list(coupon_bounds.size)},
        "coupon_bed_placed_bounds_mm": asdict(coupon_bed_bounds) | {"size": list(coupon_bed_bounds.size)},
        "bed_placement_if_centered_at_110_110_mm": bed_bounds,
        "geometry_mm": {
            "native_envelope": [TOP_OUTER, TOP_OUTER, BOX_HEIGHT],
            "wall_thickness": WALL_THICKNESS,
            "base_thickness": BASE_THICKNESS,
            "top_rim_wall": TOP_RIM_WALL,
            "top_rim_height": TOP_RIM_HEIGHT,
            "vertical_rib_width": VERTICAL_RIB_WIDTH,
            "vertical_rib_depth": VERTICAL_RIB_DEPTH,
        },
        "stacking": {
            "compatible_with": "k1_stackable_petg_crate_v2_light_slots only",
            "bottom_locator_mm": BOTTOM_LOCATOR,
            "top_opening_mm": _top_opening(),
            "clearance_per_side_mm": round((_top_opening() - BOTTOM_LOCATOR) / 2.0, 3),
            "locator_drop_depth_mm": STACK_STOP_HEIGHT,
            "stack_stop_outer_mm": STACK_STOP,
        },
        "cutouts": {
            "shape": "vertical slot windows with short 45-degree cap facets",
            "slot_target_width_mm": SLOT_WIDTH,
            "slot_target_height_mm": SLOT_HEIGHT,
            "minimum_material_between_same-row_openings_mm": MIN_SLOT_LIGAMENT_MM,
            "front_back_slot_count": front_back_count,
            "side_slot_count": side_count,
            "total_slot_count": front_back_count + side_count,
            "diamond_pattern_retired": True,
        },
        "handles": {
            "shape": "support-free peaked arch, no long horizontal bridge",
            "width_mm": HAND_SLOT_WIDTH,
            "height_mm": HAND_SLOT_HEIGHT,
            "center_z_mm": HAND_SLOT_CENTER_Z,
            "pad_width_mm": HAND_PAD_WIDTH,
            "pad_height_mm": HAND_PAD_HEIGHT,
            "pad_thickness_mm": HAND_PAD_THICKNESS,
        },
        "label_area": {
            "front_plaque_width_mm": LABEL_WIDTH,
            "front_plaque_height_mm": LABEL_HEIGHT,
            "center_z_mm": LABEL_CENTER_Z,
        },
        "estimates": {
            "crate_solid_model_volume_cm3": round(crate_volume_mm3 / 1000.0, 2),
            "crate_estimated_petg_mass_from_cad_g": round(crate_volume_mm3 * PETG_DENSITY_G_PER_MM3, 1),
            "crate_estimated_pla_mass_from_cad_g": round(crate_volume_mm3 * PLA_DENSITY_G_PER_MM3, 1),
            "coupon_solid_model_volume_cm3": round(coupon_volume_mm3 / 1000.0, 2),
            "coupon_estimated_petg_mass_from_cad_g": round(coupon_volume_mm3 * PETG_DENSITY_G_PER_MM3, 1),
            "previous_failed_job_petg_slicer_estimate_g": PREVIOUS_PETG_SLICER_ESTIMATE_G,
            "previous_failed_family_petg_mass_from_cad_g": PREVIOUS_FAILED_FAMILY_CAD_ESTIMATE_G,
            "cad_estimates_are_not_slicer_estimates": True,
        },
        "slice_profile_target": {
            "filament_profile": "CR/Generic PETG",
            "nozzle_temperature_c": 250,
            "bed_temperature_c": 70,
            "supports": "off",
            "enable_support_expected": 0,
            "brim": "off unless adhesion failure is proven",
        },
        "print_order": [
            "Print the validation coupon first.",
            "Inspect slot roofs, peaked handle roof, and stack-corner fit.",
            "Only slice and print the full crate after the coupon proves clean.",
        ],
        "support_free_design_notes": [
            "No slicer supports should be used.",
            "Slots use small cap facets instead of diamonds or circular bridge-heavy tops.",
            "Side handholds use a peaked upper profile to avoid a long unsupported bridge.",
            "Slots are kept out of corners, the label plaque, handle pads, the top rim, and the base.",
        ],
        "generator": {
            "script": str(Path(__file__).resolve()),
            "cad_kernel": "OpenCascade via OCP direct bindings",
            "cadquery_note": "CadQuery high-level import was unavailable locally; direct OCP export keeps STEP/STL output.",
        },
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


def _additive_features() -> list[TopoDS_Shape]:
    features: list[TopoDS_Shape] = []
    features.extend(_vertical_ribs())
    features.extend(_floor_ribs())
    features.append(_hand_pad("left"))
    features.append(_hand_pad("right"))
    features.append(_label_plaque())
    return features


def _vertical_ribs() -> list[TopoDS_Shape]:
    ribs: list[TopoDS_Shape] = []
    for x_pos in (-78.0, 78.0):
        ribs.append(_face_rib("front", x_pos))
        ribs.append(_face_rib("back", x_pos))
    for y_pos in (-78.0, 78.0):
        ribs.append(_face_rib("left", y_pos))
        ribs.append(_face_rib("right", y_pos))
    return ribs


def _face_rib(face: str, center: float) -> TopoDS_Shape:
    profiles: list[tuple[float, list[tuple[float, float]]]] = []
    for z_pos in (VERTICAL_RIB_Z_MIN, VERTICAL_RIB_Z_MAX):
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


def _floor_ribs() -> list[TopoDS_Shape]:
    rib_z = BASE_THICKNESS
    span = BOTTOM_LOCATOR - 34.0
    ribs: list[TopoDS_Shape] = []
    for y_pos in (-48.0, 0.0, 48.0):
        ribs.append(_box(span, FLOOR_RIB_WIDTH, FLOOR_RIB_HEIGHT, 0.0, y_pos, rib_z))
    for x_pos in (-48.0, 48.0):
        ribs.append(_box(FLOOR_RIB_WIDTH, span, FLOOR_RIB_HEIGHT, x_pos, 0.0, rib_z))
    return ribs


def _hand_pad(side: str) -> TopoDS_Shape:
    sign = -1.0 if side == "left" else 1.0
    center_x = sign * ((TOP_OUTER / 2.0) - (HAND_PAD_THICKNESS / 2.0))
    return _box(
        HAND_PAD_THICKNESS,
        HAND_PAD_WIDTH,
        HAND_PAD_HEIGHT,
        center_x,
        0.0,
        HAND_SLOT_CENTER_Z - (HAND_PAD_HEIGHT / 2.0),
    )


def _label_plaque() -> TopoDS_Shape:
    center_y = -(TOP_OUTER / 2.0) + (LABEL_THICKNESS / 2.0)
    return _box(
        LABEL_WIDTH,
        LABEL_THICKNESS,
        LABEL_HEIGHT,
        0.0,
        center_y,
        LABEL_CENTER_Z - (LABEL_HEIGHT / 2.0),
    )


def _visibility_slot_cutters() -> list[TopoDS_Shape]:
    cutters: list[TopoDS_Shape] = []
    for x_pos, z_pos in _front_slot_centers():
        cutters.append(_front_slot_cutter(x_pos, z_pos))
    for x_pos, z_pos in _back_slot_centers():
        cutters.append(_back_slot_cutter(x_pos, z_pos))
    for y_pos, z_pos in _left_slot_centers():
        cutters.append(_left_slot_cutter(y_pos, z_pos))
    for y_pos, z_pos in _right_slot_centers():
        cutters.append(_right_slot_cutter(y_pos, z_pos))
    return cutters


def _front_slot_centers() -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for row_index, z_pos in enumerate(SLOT_ROW_ZS):
        xs = SLOT_XS_PRIMARY if row_index % 2 == 0 else SLOT_XS_STAGGERED
        for x_pos in xs:
            if _slot_overlaps_label_keepout(x_pos, z_pos):
                continue
            centers.append((x_pos, z_pos))
    return centers


def _back_slot_centers() -> list[tuple[float, float]]:
    return [
        (x_pos, z_pos)
        for row_index, z_pos in enumerate(SLOT_ROW_ZS)
        for x_pos in (SLOT_XS_PRIMARY if row_index % 2 == 0 else SLOT_XS_STAGGERED)
    ]


def _left_slot_centers() -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for row_index, z_pos in enumerate(SLOT_ROW_ZS):
        ys = SLOT_XS_PRIMARY if row_index % 2 == 0 else SLOT_XS_STAGGERED
        for y_pos in ys:
            if _slot_overlaps_hand_keepout(y_pos, z_pos):
                continue
            centers.append((y_pos, z_pos))
    return centers


def _right_slot_centers() -> list[tuple[float, float]]:
    return list(_left_slot_centers())


def _slot_overlaps_label_keepout(x_pos: float, z_pos: float) -> bool:
    x0 = abs(x_pos) - (SLOT_WIDTH / 2.0)
    z_min = z_pos - (SLOT_HEIGHT / 2.0)
    z_max = z_pos + (SLOT_HEIGHT / 2.0)
    return (
        x0 <= LABEL_KEEP_OUT_X
        and z_max >= LABEL_KEEP_OUT_Z_MIN
        and z_min <= LABEL_KEEP_OUT_Z_MAX
    )


def _slot_overlaps_hand_keepout(y_pos: float, z_pos: float) -> bool:
    y0 = abs(y_pos) - (SLOT_WIDTH / 2.0)
    z_min = z_pos - (SLOT_HEIGHT / 2.0)
    z_max = z_pos + (SLOT_HEIGHT / 2.0)
    return (
        y0 <= HAND_KEEP_OUT_Y
        and z_max >= HAND_KEEP_OUT_Z_MIN
        and z_min <= HAND_KEEP_OUT_Z_MAX
    )


def _front_slot_cutter(x_pos: float, z_pos: float) -> TopoDS_Shape:
    y_start = -(TOP_OUTER / 2.0) - 3.0
    points = [(x_pos + px, y_start, z_pos + pz) for px, pz in _slot_points()]
    return _prism(points, (0.0, FACE_CUT_DEPTH, 0.0))


def _back_slot_cutter(x_pos: float, z_pos: float) -> TopoDS_Shape:
    y_start = (TOP_OUTER / 2.0) + 3.0
    points = [(x_pos + px, y_start, z_pos + pz) for px, pz in _slot_points()]
    return _prism(points, (0.0, -FACE_CUT_DEPTH, 0.0))


def _left_slot_cutter(y_pos: float, z_pos: float) -> TopoDS_Shape:
    x_start = -(TOP_OUTER / 2.0) - 3.0
    points = [(x_start, y_pos + py, z_pos + pz) for py, pz in _slot_points()]
    return _prism(points, (FACE_CUT_DEPTH, 0.0, 0.0))


def _right_slot_cutter(y_pos: float, z_pos: float) -> TopoDS_Shape:
    x_start = (TOP_OUTER / 2.0) + 3.0
    points = [(x_start, y_pos + py, z_pos + pz) for py, pz in _slot_points()]
    return _prism(points, (-FACE_CUT_DEPTH, 0.0, 0.0))


def _side_handle_cutters() -> list[TopoDS_Shape]:
    return [_side_handle_cutter("left"), _side_handle_cutter("right")]


def _side_handle_cutter(side: str) -> TopoDS_Shape:
    sign = -1.0 if side == "left" else 1.0
    x_start = sign * ((TOP_OUTER / 2.0) + 3.0)
    x_vector = -sign * HANDLE_CUT_DEPTH
    points = [
        (x_start, py, HAND_SLOT_CENTER_Z + pz)
        for py, pz in _arched_handle_points()
    ]
    return _prism(points, (x_vector, 0.0, 0.0))


def _slot_points() -> list[tuple[float, float]]:
    half_w = SLOT_WIDTH / 2.0
    half_h = SLOT_HEIGHT / 2.0
    cap = 3.0
    return [
        (-(half_w - cap), half_h),
        (half_w - cap, half_h),
        (half_w, half_h - cap),
        (half_w, -(half_h - cap)),
        (half_w - cap, -half_h),
        (-(half_w - cap), -half_h),
        (-half_w, -(half_h - cap)),
        (-half_w, half_h - cap),
    ]


def _arched_handle_points() -> list[tuple[float, float]]:
    half_w = HAND_SLOT_WIDTH / 2.0
    half_h = HAND_SLOT_HEIGHT / 2.0
    return [
        (-half_w + 5.0, -half_h),
        (half_w - 5.0, -half_h),
        (half_w, -half_h + 4.0),
        (half_w, -5.0),
        (4.0, half_h),
        (-4.0, half_h),
        (-half_w, -5.0),
        (-half_w, -half_h + 4.0),
    ]


def _wall_feature_coupon() -> TopoDS_Shape:
    panel = _box(118.0, WALL_THICKNESS, 70.0, 0.0, 0.0, 0.0)
    pad = _box(82.0, WALL_THICKNESS + HAND_PAD_THICKNESS, 32.0, 25.0, 0.0, 34.0)
    coupon = _fuse(panel, pad, "coupon handle pad")

    cutters = [
        _coupon_slot_cutter(-46.0, 18.0),
        _coupon_slot_cutter(-24.0, 48.0),
        _coupon_slot_cutter(-2.0, 18.0),
        _coupon_handle_cutter(25.0, 50.0),
    ]
    return _cut(coupon, _compound(cutters), "coupon slots and arched handle")


def _coupon_slot_cutter(x_pos: float, z_pos: float) -> TopoDS_Shape:
    points = [(x_pos + px, -8.0, z_pos + pz) for px, pz in _slot_points()]
    return _prism(points, (0.0, 16.0, 0.0))


def _coupon_handle_cutter(x_pos: float, z_pos: float) -> TopoDS_Shape:
    points = [(x_pos + px, -8.0, z_pos + pz) for px, pz in _arched_handle_points()]
    return _prism(points, (0.0, 16.0, 0.0))


def _stack_receiver_coupon() -> TopoDS_Shape:
    outer = _loft_rect([(0.0, 50.0, 50.0), (18.0, 50.0, 50.0)])
    inner = _loft_rect([(BASE_THICKNESS, 39.0, 39.0), (19.0, 39.0, 39.0)])
    receiver = _cut(outer, inner, "coupon stack receiver")
    lip_front = _box(50.0, 3.0, 7.0, 0.0, -23.5, 11.0)
    lip_left = _box(3.0, 50.0, 7.0, -23.5, 0.0, 11.0)
    return _fuse(_fuse(receiver, lip_front, "receiver front lip"), lip_left, "receiver left lip")


def _stack_locator_coupon() -> TopoDS_Shape:
    locator = _loft_rect(
        [
            (0.0, 39.0, 39.0),
            (LOCATOR_HEIGHT, 39.0, 39.0),
            (STACK_STOP_HEIGHT, 46.0, 46.0),
            (16.0, 48.0, 48.0),
        ]
    )
    inner = _loft_rect([(BASE_THICKNESS, 31.0, 31.0), (17.0, 31.0, 31.0)])
    return _cut(locator, inner, "coupon stack locator")


def _loft_rect(profiles: list[tuple[float, float, float]]) -> TopoDS_Shape:
    loft = BRepOffsetAPI_ThruSections(True, True)
    for z_pos, width, depth in profiles:
        loft.AddWire(_rect_wire(z_pos, width, depth))
    loft.Build()
    if not loft.IsDone():
        raise RuntimeError("rectangular loft failed")
    return loft.Shape()


def _loft_polygon(profiles: list[tuple[float, list[tuple[float, float]]]]) -> TopoDS_Shape:
    loft = BRepOffsetAPI_ThruSections(True, True)
    for z_pos, points in profiles:
        loft.AddWire(_wire([(x_pos, y_pos, z_pos) for x_pos, y_pos in points]))
    loft.Build()
    if not loft.IsDone():
        raise RuntimeError("polygon loft failed")
    return loft.Shape()


def _rect_wire(z_pos: float, width: float, depth: float):
    half_w = width / 2.0
    half_d = depth / 2.0
    return _wire(
        [
            (-half_w, -half_d, z_pos),
            (half_w, -half_d, z_pos),
            (half_w, half_d, z_pos),
            (-half_w, half_d, z_pos),
        ]
    )


def _wire(points: list[tuple[float, float, float]]):
    polygon = BRepBuilderAPI_MakePolygon()
    for x_pos, y_pos, z_pos in points:
        polygon.Add(gp_Pnt(x_pos, y_pos, z_pos))
    polygon.Close()
    return polygon.Wire()


def _prism(points: list[tuple[float, float, float]], vector: tuple[float, float, float]) -> TopoDS_Shape:
    face = BRepBuilderAPI_MakeFace(_wire(points)).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(*vector)).Shape()


def _box(
    width: float,
    depth: float,
    height: float,
    center_x: float,
    center_y: float,
    z_min: float,
) -> TopoDS_Shape:
    return BRepPrimAPI_MakeBox(
        gp_Pnt(center_x - width / 2.0, center_y - depth / 2.0, z_min),
        width,
        depth,
        height,
    ).Shape()


def _compound(shapes: list[TopoDS_Shape]) -> TopoDS_Compound:
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def _cut(base: TopoDS_Shape, tool: TopoDS_Shape, label: str) -> TopoDS_Shape:
    op = BRepAlgoAPI_Cut(base, tool)
    op.SetRunParallel(True)
    op.SetFuzzyValue(0.01)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean cut failed: {label}")
    return op.Shape()


def _fuse(base: TopoDS_Shape, addition: TopoDS_Shape, label: str) -> TopoDS_Shape:
    op = BRepAlgoAPI_Fuse(base, addition)
    op.SetRunParallel(True)
    op.SetFuzzyValue(0.01)
    op.Build()
    if not op.IsDone():
        raise RuntimeError(f"boolean fuse failed: {label}")
    return op.Shape()


def _translation(x_pos: float, y_pos: float, z_pos: float):
    from OCP.gp import gp_Trsf
    from OCP.TopLoc import TopLoc_Location

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(x_pos, y_pos, z_pos))
    return TopLoc_Location(trsf)


def _export_stl(
    shape: TopoDS_Shape,
    path: Path,
    *,
    linear_deflection: float,
    angular_deflection: float,
) -> None:
    mesher = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection, True)
    mesher.Perform()
    writer = StlAPI_Writer()
    writer.ASCIIMode = False
    if not writer.Write(shape, str(path)):
        raise RuntimeError(f"failed to write STL: {path}")


def _export_step(shape: TopoDS_Shape, path: Path) -> None:
    writer = STEPControl_Writer()
    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone:
        raise RuntimeError(f"failed to transfer STEP shape: {path}")
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"failed to write STEP: {path}")


def _shape_bounds(shape: TopoDS_Shape) -> Bounds:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    min_x, min_y, min_z, max_x, max_y, max_z = box.Get()
    return Bounds(
        min_x=round(min_x, 3),
        max_x=round(max_x, 3),
        min_y=round(min_y, 3),
        max_y=round(max_y, 3),
        min_z=round(min_z, 3),
        max_z=round(max_z, 3),
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


def _validate_bed_placed_bounds(bounds: Bounds, build_volume: tuple[float, float, float]) -> None:
    minimums = (bounds.min_x, bounds.min_y, bounds.min_z)
    maximums = (bounds.max_x, bounds.max_y, bounds.max_z)
    for axis, minimum, maximum, limit in zip(("X", "Y", "Z"), minimums, maximums, build_volume):
        if minimum < -0.001:
            raise ValueError(f"{axis} bed-placed minimum {minimum:.3f} is below 0")
        if maximum > limit + 0.001:
            raise ValueError(f"{axis} bed-placed maximum {maximum:.3f} exceeds {limit:.3f}")


def _bed_placement_bounds(bounds: Bounds) -> dict:
    return {
        "x_min": round(bounds.min_x + BED_CENTER_OFFSET, 3),
        "x_max": round(bounds.max_x + BED_CENTER_OFFSET, 3),
        "y_min": round(bounds.min_y + BED_CENTER_OFFSET, 3),
        "y_max": round(bounds.max_y + BED_CENTER_OFFSET, 3),
        "z_min": bounds.min_z,
        "z_max": bounds.max_z,
    }


def _volume(shape: TopoDS_Shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def main() -> None:
    manifest = export_all()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

"""Generate full robot-vac threshold ramp plates as direct STL/3MF meshes.

This generator is intentionally independent of CadQuery booleans so the final
print plates can include curved side-entry footprints and clean straight seams
without slow BREP operations.

Coordinate conventions before per-plate centering:
- X runs across the 680 mm doorway width.
- Y runs in the robot travel direction, from floor approach (-Y) to threshold (+Y).
- Z=0 is the floor-contact face.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from math import asin, cos, pi, sin, sqrt
import os
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE_NS)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REVISION = "full_d90_keyed_lightweight_v6"
DEFAULT_BRIEF_PATH = SCRIPT_DIR / "robot_vac_threshold_ramp_brief.json"
BRIEF_PATH = Path(os.environ.get("ROBOT_VAC_BRIEF_PATH", DEFAULT_BRIEF_PATH))

PROFILE_RAMP_SAMPLES = 28
QUARTER_ROUND_SEGMENTS = 14

SEAM_CLEARANCE = 0.35
SEAM_KEY_DEPTH = 3.2
SEAM_KEY_CENTERS_Y = (-58.0, -31.0)
SEAM_KEY_HALF_LENGTH_Y = 8.5
SEAM_RAIL_WIDTH = 18.0
SIDE_ENTRY_INSET = 42.0
SIDE_ENTRY_SLOPE_WIDTH = 48.0
SIDE_ENTRY_MIN_ACTIVE_WIDTH = 0.4
SIDE_ENTRY_EDGE_SCALE = 0.02
SIDE_ENTRY_COLUMN_FRACTIONS = (0.0, 0.33, 0.66, 1.0)
SIDE_ENTRY_FADE_START_Y = -58.0
SIDE_ENTRY_PROTECTED_REAR_Y = -8.0
UNDERSIDE_SHELL_THICKNESS = 3.2
UNDERSIDE_CAVITY_PEAK_Y = -24.0
UNDERSIDE_CAVITY_PEAK_Z = 8.0

TRACTION_LINE_COUNT = 5
TRACTION_LINE_HEIGHT = 0.4
TRACTION_LINE_WIDTH = 1.45
TRACTION_LINE_EMBED = 0.12
TRACTION_LINE_AMPLITUDE = 1.35
TRACTION_LINE_SAMPLES = 72
TRACTION_LINE_EDGE_MARGIN = 10.0


@dataclass(frozen=True)
class Triangle:
    v1: int
    v2: int
    v3: int


@dataclass(frozen=True)
class RampDimensions:
    part_name: str
    total_width: float
    height: float
    ramp_run_depth: float
    top_landing_depth: float
    quarter_round_radius: float
    segment_count: int

    @property
    def overall_depth(self) -> float:
        return self.ramp_run_depth + self.top_landing_depth

    @property
    def front_y(self) -> float:
        return -self.ramp_run_depth

    @property
    def back_y(self) -> float:
        return self.top_landing_depth

    @property
    def segment_nominal_width(self) -> float:
        return self.total_width / self.segment_count


@dataclass(frozen=True)
class PrinterTarget:
    model: str
    build_volume: tuple[float, float, float]
    max_segment_width: float | None


@dataclass(frozen=True)
class RampConfig:
    part_name: str
    revision: str
    output_dir: Path
    printer: PrinterTarget


def load_dimensions() -> RampDimensions:
    brief = json.loads(BRIEF_PATH.read_text())
    dimensions = brief["dimensions"]
    return RampDimensions(
        part_name=brief["name"],
        total_width=float(dimensions["total_width"]),
        height=float(dimensions["threshold_height"]),
        ramp_run_depth=float(dimensions["ramp_run_depth"]),
        top_landing_depth=float(dimensions["top_landing_depth"]),
        quarter_round_radius=float(dimensions["quarter_round_relief_radius"]),
        segment_count=int(dimensions["segment_count"]),
    )


def load_config(dimensions: RampDimensions) -> RampConfig:
    brief = json.loads(BRIEF_PATH.read_text())
    target = brief.get("target_printer", {})
    printer_model = str(target.get("model", "Generic FFF Printer"))
    build_volume = tuple(float(value) for value in target.get("build_volume", [256, 256, 256]))
    max_segment_width = target.get("max_segment_width")
    revision = build_revision_name(printer_model, dimensions.segment_count)
    return RampConfig(
        part_name=str(brief.get("name", "robot_vac_threshold_ramp")),
        revision=revision,
        output_dir=SCRIPT_DIR / "output" / f"{brief.get('name', 'robot_vac_threshold_ramp')}_{revision}",
        printer=PrinterTarget(
            model=printer_model,
            build_volume=(build_volume[0], build_volume[1], build_volume[2]),
            max_segment_width=float(max_segment_width) if max_segment_width is not None else None,
        ),
    )


def build_revision_name(printer_model: str, segment_count: int) -> str:
    if BRIEF_PATH == DEFAULT_BRIEF_PATH and printer_model == "Bambu Lab A1" and segment_count == 3:
        return DEFAULT_REVISION
    return f"{DEFAULT_REVISION}_{slugify(printer_model)}_{segment_count}seg"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def build_solid_profile(dimensions: RampDimensions) -> list[tuple[float, float]]:
    profile: list[tuple[float, float]] = [(dimensions.front_y, 0.0)]

    for step in range(1, PROFILE_RAMP_SAMPLES + 1):
        t = step / PROFILE_RAMP_SAMPLES
        y_pos = dimensions.front_y + (dimensions.ramp_run_depth * t)
        profile.append((y_pos, top_surface_z_at_y(y_pos, dimensions)))

    top_y = rear_profile_y_at_z(
        dimensions.height,
        dimensions.top_landing_depth,
        dimensions.quarter_round_radius,
    )
    if top_y > 0.0:
        profile.append((top_y, dimensions.height))

    start_angle = quarter_round_angle_for_z(dimensions.height, dimensions.quarter_round_radius)
    if dimensions.height > dimensions.quarter_round_radius:
        profile.append((dimensions.back_y, dimensions.quarter_round_radius))
        start_angle = pi / 2.0

    for step in range(1, QUARTER_ROUND_SEGMENTS + 1):
        angle = start_angle + ((pi - start_angle) * step / QUARTER_ROUND_SEGMENTS)
        profile.append(
            (
                dimensions.back_y + (dimensions.quarter_round_radius * cos(angle)),
                dimensions.quarter_round_radius * sin(angle),
            )
        )

    return ensure_ccw(remove_near_duplicates(profile))


def build_underside_relief_profile(dimensions: RampDimensions) -> list[tuple[float, float]]:
    """Conservative underside relief with solid front, side, seam, and rear zones."""

    outer = list(reversed(build_solid_profile(dimensions)))
    slope = dimensions.height / dimensions.ramp_run_depth
    inner_start_y = dimensions.front_y + (UNDERSIDE_SHELL_THICKNESS / slope)
    inner_peak_z = min(
        top_surface_z_at_y(UNDERSIDE_CAVITY_PEAK_Y, dimensions) - UNDERSIDE_SHELL_THICKNESS,
        UNDERSIDE_CAVITY_PEAK_Z,
    )
    inner_peak_z = max(UNDERSIDE_SHELL_THICKNESS, inner_peak_z)
    inner = [
        (UNDERSIDE_CAVITY_PEAK_Y, inner_peak_z),
        (inner_start_y, 0.0),
    ]
    return ensure_ccw(remove_near_duplicates(outer + inner))


def remove_near_duplicates(profile: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in profile:
        if cleaned and distance_2d(cleaned[-1], point) < 1e-6:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and distance_2d(cleaned[0], cleaned[-1]) < 1e-6:
        cleaned.pop()
    return cleaned


def distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return sqrt(((a[0] - b[0]) ** 2) + ((a[1] - b[1]) ** 2))


def quarter_round_angle_for_z(z_pos: float, radius: float) -> float:
    if z_pos >= radius:
        return pi / 2.0
    if z_pos <= 0.0:
        return pi
    return pi - asin(z_pos / radius)


def rear_profile_y_at_z(z_pos: float, top_landing_depth: float, radius: float) -> float:
    if z_pos <= 0.0:
        return top_landing_depth - radius
    if z_pos >= radius:
        return top_landing_depth
    return top_landing_depth - sqrt((radius * radius) - (z_pos * z_pos))


def top_surface_z_at_y(y_pos: float, dimensions: RampDimensions) -> float:
    if y_pos <= dimensions.front_y:
        return 0.0
    if y_pos >= 0.0:
        return dimensions.height
    return ((y_pos - dimensions.front_y) / dimensions.ramp_run_depth) * dimensions.height


def ensure_ccw(profile: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return profile if polygon_area(profile) > 0.0 else list(reversed(profile))


def polygon_area(profile: list[tuple[float, float]]) -> float:
    area = 0.0
    for index, (y1, z1) in enumerate(profile):
        y2, z2 = profile[(index + 1) % len(profile)]
        area += (y1 * z2) - (y2 * z1)
    return area / 2.0


def triangulate_polygon(profile: list[tuple[float, float]]) -> list[Triangle]:
    remaining = list(range(len(profile)))
    triangles: list[Triangle] = []

    while len(remaining) > 3:
        clipped = False
        for offset, current in enumerate(remaining):
            previous = remaining[offset - 1]
            following = remaining[(offset + 1) % len(remaining)]
            if not is_convex(profile[previous], profile[current], profile[following]):
                continue
            if any(
                point_in_triangle(profile[test], profile[previous], profile[current], profile[following])
                for test in remaining
                if test not in {previous, current, following}
            ):
                continue
            triangles.append(Triangle(previous, current, following))
            del remaining[offset]
            clipped = True
            break
        if not clipped:
            raise ValueError("profile triangulation failed")

    triangles.append(Triangle(remaining[0], remaining[1], remaining[2]))
    return triangles


def is_convex(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return cross_2d(a, b, c) > 1e-9


def cross_2d(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))


def point_in_triangle(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    c1 = cross_2d(a, b, point)
    c2 = cross_2d(b, c, point)
    c3 = cross_2d(c, a, point)
    return c1 >= -1e-9 and c2 >= -1e-9 and c3 >= -1e-9


def segment_bounds(segment_index: int, y_pos: float, dimensions: RampDimensions) -> tuple[float, float]:
    nominal_width = dimensions.segment_nominal_width
    x_min = -(dimensions.total_width / 2.0) + (segment_index * nominal_width)
    x_max = x_min + nominal_width

    if segment_index > 0:
        seam_x = -(dimensions.total_width / 2.0) + (segment_index * nominal_width)
        x_min = seam_x + seam_key_offset(y_pos) + (SEAM_CLEARANCE / 2.0)
    else:
        x_min += side_entry_inset(y_pos, dimensions)

    if segment_index < dimensions.segment_count - 1:
        seam_x = -(dimensions.total_width / 2.0) + ((segment_index + 1) * nominal_width)
        x_max = seam_x + seam_key_offset(y_pos) - (SEAM_CLEARANCE / 2.0)
    else:
        x_max -= side_entry_inset(y_pos, dimensions)

    if x_max - x_min < 30.0:
        raise ValueError("segment boundary collapsed")
    return x_min, x_max


def seam_key_offset(y_pos: float) -> float:
    offset = 0.0
    for center_y in SEAM_KEY_CENTERS_Y:
        distance = abs(y_pos - center_y)
        if distance >= SEAM_KEY_HALF_LENGTH_Y:
            continue
        t = 1.0 - (distance / SEAM_KEY_HALF_LENGTH_Y)
        offset += SEAM_KEY_DEPTH * smoothstep(t)
    return offset


def side_entry_inset(y_pos: float, dimensions: RampDimensions) -> float:
    t = clamp((y_pos - dimensions.front_y) / dimensions.ramp_run_depth, 0.0, 1.0)
    eased = smoothstep(t)
    return SIDE_ENTRY_INSET * (1.0 - eased) * side_entry_activity(y_pos)


def side_entry_activity(y_pos: float) -> float:
    if y_pos <= SIDE_ENTRY_FADE_START_Y:
        return 1.0
    if y_pos >= SIDE_ENTRY_PROTECTED_REAR_Y:
        return 0.0
    t = (y_pos - SIDE_ENTRY_FADE_START_Y) / (SIDE_ENTRY_PROTECTED_REAR_Y - SIDE_ENTRY_FADE_START_Y)
    return 1.0 - smoothstep(t)


def side_entry_slope_width(y_pos: float) -> float:
    return max(SIDE_ENTRY_MIN_ACTIVE_WIDTH, SIDE_ENTRY_SLOPE_WIDTH * side_entry_activity(y_pos))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(t: float) -> float:
    return t * t * (3.0 - (2.0 * t))


def add_swept_profile(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    profile: list[tuple[float, float]],
    dimensions: RampDimensions,
    segment_index: int,
    columns_for_y: Callable[[float], list[tuple[float, float]]],
) -> None:
    start = len(vertices)
    column_count = profile_column_count(columns_for_y)
    for y_pos, z_pos in profile:
        for x_pos, z_scale in columns_for_y(y_pos):
            vertices.append((x_pos, y_pos, z_pos * z_scale))

    side_count = len(profile)
    first_cap_profile = scaled_profile(profile, profile_column_scale(columns_for_y, 0))
    last_cap_profile = scaled_profile(profile, profile_column_scale(columns_for_y, column_count - 1))
    first_cap_triangles = triangulate_polygon(first_cap_profile)
    last_cap_triangles = triangulate_polygon(last_cap_profile)

    for triangle in first_cap_triangles:
        triangles.append(
            Triangle(
                start + (triangle.v1 * column_count),
                start + (triangle.v2 * column_count),
                start + (triangle.v3 * column_count),
            )
        )

    last_col = column_count - 1
    for triangle in last_cap_triangles:
        triangles.append(
            Triangle(
                start + (triangle.v1 * column_count) + last_col,
                start + (triangle.v3 * column_count) + last_col,
                start + (triangle.v2 * column_count) + last_col,
            )
        )

    for index in range(side_count):
        next_index = (index + 1) % side_count
        for column in range(column_count - 1):
            a = start + (index * column_count) + column
            b = a + 1
            c = start + (next_index * column_count) + column
            d = c + 1
            triangles.append(Triangle(a, b, d))
            triangles.append(Triangle(a, d, c))


def profile_column_count(columns_for_y: Callable[[float], list[tuple[float, float]]]) -> int:
    return len(columns_for_y(0.0))


def scaled_profile(profile: list[tuple[float, float]], z_scale: float) -> list[tuple[float, float]]:
    return ensure_ccw([(y_pos, z_pos * z_scale) for y_pos, z_pos in profile])


def profile_column_scale(columns_for_y: Callable[[float], list[tuple[float, float]]], column_index: int) -> float:
    columns = columns_for_y(0.0)
    if column_index < 0 or column_index >= len(columns):
        raise IndexError("column index out of range")
    return columns[column_index][1]


def clean_profile_columns(
    segment_index: int,
    y_pos: float,
    dimensions: RampDimensions,
) -> list[tuple[float, float]]:
    x_left, x_right = segment_bounds(segment_index, y_pos, dimensions)
    side_width = side_entry_slope_width(y_pos)

    if segment_index == 0:
        inner_left = min(x_left + side_width, x_right - 20.0)
        columns = [
            (x_left + ((inner_left - x_left) * fraction), side_entry_z_scale(fraction, y_pos))
            for fraction in SIDE_ENTRY_COLUMN_FRACTIONS
        ]
        columns.append((x_right, 1.0))
        return remove_near_duplicate_columns(columns)

    if segment_index == dimensions.segment_count - 1:
        inner_right = max(x_right - side_width, x_left + 20.0)
        columns = [(x_left, 1.0)]
        columns.extend(
            (inner_right + ((x_right - inner_right) * fraction), side_entry_z_scale(1.0 - fraction, y_pos))
            for fraction in SIDE_ENTRY_COLUMN_FRACTIONS
        )
        return remove_near_duplicate_columns(columns)

    return [(x_left, 1.0), (x_right, 1.0)]


def relief_strip_columns(
    segment_index: int,
    y_pos: float,
    dimensions: RampDimensions,
) -> list[tuple[float, float]]:
    x_left, x_right = segment_bounds(segment_index, y_pos, dimensions)
    side_width = side_entry_slope_width(y_pos)

    if segment_index == 0:
        start_x = min(x_left + side_width + 8.0, x_right - (SEAM_RAIL_WIDTH + 20.0))
        end_x = x_right - SEAM_RAIL_WIDTH
    elif segment_index == dimensions.segment_count - 1:
        start_x = x_left + SEAM_RAIL_WIDTH
        end_x = max(x_right - side_width - 8.0, x_left + (SEAM_RAIL_WIDTH + 20.0))
    else:
        start_x = x_left + SEAM_RAIL_WIDTH
        end_x = x_right - SEAM_RAIL_WIDTH

    if end_x - start_x < 30.0:
        mid_x = (x_left + x_right) / 2.0
        start_x = mid_x - 15.0
        end_x = mid_x + 15.0
    return [(start_x, 1.0), (end_x, 1.0)]


def solid_left_frame_columns(
    segment_index: int,
    y_pos: float,
    dimensions: RampDimensions,
) -> list[tuple[float, float]]:
    x_left, x_right = segment_bounds(segment_index, y_pos, dimensions)
    relief_columns = relief_strip_columns(segment_index, y_pos, dimensions)
    relief_left = relief_columns[0][0]

    if segment_index == 0:
        inner_left = min(x_left + side_entry_slope_width(y_pos), relief_left)
        columns = [
            (x_left + ((inner_left - x_left) * fraction), side_entry_z_scale(fraction, y_pos))
            for fraction in SIDE_ENTRY_COLUMN_FRACTIONS
        ]
        if relief_left > inner_left:
            columns.append((relief_left, 1.0))
        return remove_near_duplicate_columns(columns)

    return [(x_left, 1.0), (relief_left, 1.0)]


def solid_right_frame_columns(
    segment_index: int,
    y_pos: float,
    dimensions: RampDimensions,
) -> list[tuple[float, float]]:
    x_left, x_right = segment_bounds(segment_index, y_pos, dimensions)
    relief_columns = relief_strip_columns(segment_index, y_pos, dimensions)
    relief_right = relief_columns[-1][0]

    if segment_index == dimensions.segment_count - 1:
        inner_right = max(x_right - side_entry_slope_width(y_pos), relief_right)
        columns = [(relief_right, 1.0)]
        columns.extend(
            (inner_right + ((x_right - inner_right) * fraction), side_entry_z_scale(1.0 - fraction, y_pos))
            for fraction in SIDE_ENTRY_COLUMN_FRACTIONS
        )
        return remove_near_duplicate_columns(columns)

    return [(relief_right, 1.0), (x_right, 1.0)]


def side_entry_z_scale(fraction: float, y_pos: float) -> float:
    eased = smoothstep(clamp(fraction, 0.0, 1.0))
    active_scale = SIDE_ENTRY_EDGE_SCALE + ((1.0 - SIDE_ENTRY_EDGE_SCALE) * eased)
    activity = side_entry_activity(y_pos)
    return 1.0 - (activity * (1.0 - active_scale))


def remove_near_duplicate_columns(columns: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for x_pos, z_scale in columns:
        if cleaned and abs(cleaned[-1][0] - x_pos) < 1e-6:
            cleaned[-1] = (x_pos, max(cleaned[-1][1], z_scale))
        else:
            cleaned.append((x_pos, z_scale))
    return cleaned


def add_wavy_traction_lines(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    dimensions: RampDimensions,
    segment_index: int,
) -> None:
    line_spacing = dimensions.ramp_run_depth / (TRACTION_LINE_COUNT + 1)

    for line_index in range(TRACTION_LINE_COUNT):
        y_center = dimensions.front_y + (line_spacing * (line_index + 1))
        x_left, x_right = segment_bounds(segment_index, y_center, dimensions)
        if segment_index == 0:
            x_left += side_entry_slope_width(y_center)
        elif segment_index == dimensions.segment_count - 1:
            x_right -= side_entry_slope_width(y_center)
        x_min = x_left + TRACTION_LINE_EDGE_MARGIN
        x_max = x_right - TRACTION_LINE_EDGE_MARGIN
        if x_max <= x_min:
            continue
        add_wavy_ribbon(vertices, triangles, dimensions, x_min, x_max, y_center)


def add_wavy_ribbon(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    dimensions: RampDimensions,
    x_min: float,
    x_max: float,
    y_center: float,
) -> None:
    start = len(vertices)
    samples = TRACTION_LINE_SAMPLES

    for sample in range(samples + 1):
        t = sample / samples
        x_pos = x_min + ((x_max - x_min) * t)
        angle = 4.0 * pi * t
        y_pos = y_center + (TRACTION_LINE_AMPLITUDE * cos(angle))
        dy_dx = -TRACTION_LINE_AMPLITUDE * sin(angle) * (4.0 * pi / (x_max - x_min))
        normal_length = sqrt((dy_dx * dy_dx) + 1.0)
        normal_x = -dy_dx / normal_length
        normal_y = 1.0 / normal_length
        z_surface = top_surface_z_at_y(y_pos, dimensions)

        for side in (-0.5, 0.5):
            offset_x = normal_x * TRACTION_LINE_WIDTH * side
            offset_y = normal_y * TRACTION_LINE_WIDTH * side
            vertices.append((x_pos + offset_x, y_pos + offset_y, z_surface - TRACTION_LINE_EMBED))
        for side in (-0.5, 0.5):
            offset_x = normal_x * TRACTION_LINE_WIDTH * side
            offset_y = normal_y * TRACTION_LINE_WIDTH * side
            vertices.append((x_pos + offset_x, y_pos + offset_y, z_surface + TRACTION_LINE_HEIGHT))

    for sample in range(samples):
        base = start + (sample * 4)
        nxt = base + 4
        triangles.extend(
            [
                Triangle(base, nxt + 1, nxt),
                Triangle(base, base + 1, nxt + 1),
                Triangle(base + 2, nxt + 2, nxt + 3),
                Triangle(base + 2, nxt + 3, base + 3),
                Triangle(base, nxt, nxt + 2),
                Triangle(base, nxt + 2, base + 2),
                Triangle(base + 1, base + 3, nxt + 3),
                Triangle(base + 1, nxt + 3, nxt + 1),
            ]
        )

    first = start
    last = start + (samples * 4)
    triangles.extend(
        [
            Triangle(first, first + 2, first + 3),
            Triangle(first, first + 3, first + 1),
            Triangle(last, last + 1, last + 3),
            Triangle(last, last + 3, last + 2),
        ]
    )


def center_mesh_xy(vertices: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    min_x = min(vertex[0] for vertex in vertices)
    max_x = max(vertex[0] for vertex in vertices)
    min_y = min(vertex[1] for vertex in vertices)
    max_y = max(vertex[1] for vertex in vertices)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    return [(x - center_x, y - center_y, z) for x, y, z in vertices]


def build_segment_mesh(
    dimensions: RampDimensions,
    segment_index: int,
) -> tuple[list[tuple[float, float, float]], list[Triangle]]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[Triangle] = []
    solid_profile = build_solid_profile(dimensions)
    relief_profile = build_underside_relief_profile(dimensions)

    add_swept_profile(
        vertices,
        triangles,
        solid_profile,
        dimensions,
        segment_index,
        lambda y_pos: solid_left_frame_columns(segment_index, y_pos, dimensions),
    )
    add_swept_profile(
        vertices,
        triangles,
        relief_profile,
        dimensions,
        segment_index,
        lambda y_pos: relief_strip_columns(segment_index, y_pos, dimensions),
    )
    add_swept_profile(
        vertices,
        triangles,
        solid_profile,
        dimensions,
        segment_index,
        lambda y_pos: solid_right_frame_columns(segment_index, y_pos, dimensions),
    )

    add_wavy_traction_lines(vertices, triangles, dimensions, segment_index)
    return center_mesh_xy(vertices), triangles


def write_binary_stl(path: Path, vertices: list[tuple[float, float, float]], triangles: list[Triangle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        file.write(b"robot-vac-ramp-full".ljust(80, b"\0"))
        file.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            file.write(struct.pack("<fff", 0.0, 0.0, 0.0))
            for vertex_index in (triangle.v1, triangle.v2, triangle.v3):
                file.write(struct.pack("<fff", *vertices[vertex_index]))
            file.write(struct.pack("<H", 0))


def write_3mf(
    path: Path,
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    title: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", root_relationships_xml())
        archive.writestr("3D/3dmodel.model", model_xml(vertices, triangles, title))


def model_xml(vertices: list[tuple[float, float, float]], triangles: list[Triangle], title: str) -> bytes:
    model = ET.Element(
        f"{{{CORE_NS}}}model",
        attrib={"unit": "millimeter", "xml:lang": "en-US"},
    )
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", attrib={"name": "Application"}).text = "llm-to-3dprint"
    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    object_el = ET.SubElement(resources, f"{{{CORE_NS}}}object", attrib={"id": "1", "type": "model"})
    ET.SubElement(object_el, f"{{{CORE_NS}}}metadata", attrib={"name": "Title"}).text = title
    mesh_el = ET.SubElement(object_el, f"{{{CORE_NS}}}mesh")
    vertices_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}vertices")

    for x_pos, y_pos, z_pos in vertices:
        ET.SubElement(
            vertices_el,
            f"{{{CORE_NS}}}vertex",
            attrib={"x": f"{x_pos:.6f}", "y": f"{y_pos:.6f}", "z": f"{z_pos:.6f}"},
        )

    triangles_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}triangles")
    for triangle in triangles:
        ET.SubElement(
            triangles_el,
            f"{{{CORE_NS}}}triangle",
            attrib={"v1": str(triangle.v1), "v2": str(triangle.v2), "v3": str(triangle.v3)},
        )

    build = ET.SubElement(model, f"{{{CORE_NS}}}build")
    ET.SubElement(build, f"{{{CORE_NS}}}item", attrib={"objectid": "1", "printable": "1"})
    ET.indent(model)
    return ET.tostring(model, encoding="utf-8", xml_declaration=True)


def content_types_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""


def root_relationships_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def mesh_bounds(vertices: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    return {
        "min": [round(min(xs), 3), round(min(ys), 3), round(min(zs), 3)],
        "max": [round(max(xs), 3), round(max(ys), 3), round(max(zs), 3)],
        "size": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3), round(max(zs) - min(zs), 3)],
    }


def segment_labels(segment_count: int) -> list[str]:
    if segment_count == 1:
        return ["single"]
    if segment_count == 2:
        return ["left", "right"]
    if segment_count == 3:
        return ["left", "middle", "right"]
    if segment_count == 4:
        return ["left", "mid_left", "mid_right", "right"]

    labels = ["left"]
    labels.extend(f"inner_{index:02d}" for index in range(1, segment_count - 1))
    labels.append("right")
    return labels


def validate_plate_fit(
    label: str,
    bounds: dict[str, list[float]],
    printer: PrinterTarget,
) -> None:
    size_x, size_y, size_z = bounds["size"]
    build_x, build_y, build_z = printer.build_volume
    fits_xy = ((size_x <= build_x and size_y <= build_y) or (size_x <= build_y and size_y <= build_x))
    if not fits_xy or size_z > build_z:
        raise ValueError(
            f"{label} plate does not fit {printer.model}: "
            f"plate={size_x}x{size_y}x{size_z} mm build={build_x}x{build_y}x{build_z} mm"
        )
    if printer.max_segment_width is not None and max(size_x, size_y) > printer.max_segment_width:
        raise ValueError(
            f"{label} plate exceeds max_segment_width for {printer.model}: "
            f"plate max={max(size_x, size_y)} mm limit={printer.max_segment_width} mm"
        )


def write_handoff(
    path: Path,
    config: RampConfig,
    dimensions: RampDimensions,
    plates: list[dict[str, object]],
) -> None:
    handoff = {
        "name": f"{config.part_name}_{config.revision}",
        "units": "mm",
        "target_printer": config.printer.model,
        "printer_build_volume": list(config.printer.build_volume),
        "print_intent": f"{dimensions.segment_count} single-material plate files",
        "slope_ratio": round(dimensions.ramp_run_depth / dimensions.height, 2),
        "assembly": {
            "order": [plate["label"] for plate in plates],
            "straight_seam_clearance": SEAM_CLEARANCE,
            "rounded_key_depth": SEAM_KEY_DEPTH,
            "rounded_key_centers_y": list(SEAM_KEY_CENTERS_Y),
            "side_entry_curve_inset": SIDE_ENTRY_INSET,
            "side_entry_slope_width": SIDE_ENTRY_SLOPE_WIDTH,
            "side_entry_min_active_width": SIDE_ENTRY_MIN_ACTIVE_WIDTH,
            "side_entry_edge_height": round(dimensions.height * SIDE_ENTRY_EDGE_SCALE, 3),
            "side_entry_fade_start_y": SIDE_ENTRY_FADE_START_Y,
            "protected_rear_fit_zone_y": SIDE_ENTRY_PROTECTED_REAR_Y,
            "notes": "Uses two shallow rounded keyed seam bumps per join plus conservative underside relief; side-entry footprint and ramp width taper out gradually before the rear quarter-round fit zone.",
        },
        "filament_saving": {
            "underside_shell_thickness": UNDERSIDE_SHELL_THICKNESS,
            "relief_peak_y": UNDERSIDE_CAVITY_PEAK_Y,
            "relief_peak_z": UNDERSIDE_CAVITY_PEAK_Z,
            "kept_solid": "outer side ramps, seam rails, front lip, rear quarter-round, and top surface",
        },
        "plates": plates,
    }
    path.write_text(json.dumps(handoff, indent=2) + "\n")


def export_full_ramp() -> list[Path]:
    dimensions = load_dimensions()
    config = load_config(dimensions)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    labels = segment_labels(dimensions.segment_count)
    outputs: list[Path] = []
    plate_records: list[dict[str, object]] = []

    for segment_index, label in enumerate(labels):
        vertices, triangles = build_segment_mesh(dimensions, segment_index)
        title = f"{config.part_name}_{config.revision}_plate_{segment_index + 1}_{label}"
        stl_path = config.output_dir / f"{title}.stl"
        file_3mf = config.output_dir / f"{title}.3mf"
        write_binary_stl(stl_path, vertices, triangles)
        write_3mf(file_3mf, vertices, triangles, title)
        outputs.extend([stl_path, file_3mf])
        bounds = mesh_bounds(vertices)
        validate_plate_fit(label, bounds, config.printer)
        plate_records.append(
            {
                "label": label,
                "stl": stl_path.name,
                "3mf": file_3mf.name,
                "triangles": len(triangles),
                "bounds": bounds,
            }
        )

    handoff_path = config.output_dir / f"{config.part_name}_{config.revision}_handoff.json"
    write_handoff(handoff_path, config, dimensions, plate_records)
    outputs.append(handoff_path)
    return outputs


if __name__ == "__main__":
    for output in export_full_ramp():
        print(output)

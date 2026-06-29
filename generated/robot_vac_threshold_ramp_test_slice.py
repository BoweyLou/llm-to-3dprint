"""Export narrow robot-vac ramp test slices for quick fit checks.

The test coupons are direct meshes instead of CadQuery exports so dimensional
iterations do not wait on full BREP/boolean processing.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import asin, cos, pi, sin, sqrt
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE_NS)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
BRIEF_PATH = SCRIPT_DIR / "robot_vac_threshold_ramp_brief.json"

TEST_SLICE_WIDTH = 20.0
QUARTER_ROUND_SEGMENTS = 12
SHELL_THICKNESS = 2.4
LIGHTWEIGHT_CAVITY_PEAK_Y = -18.0
LIGHTWEIGHT_CAVITY_PEAK_Z = 10.0

TRACTION_LINE_COUNT = 3
TRACTION_LINE_HEIGHT = 0.4
TRACTION_LINE_WIDTH = 1.4
TRACTION_LINE_EMBED = 0.12
TRACTION_LINE_AMPLITUDE = 1.25
TRACTION_LINE_SAMPLES = 18
TRACTION_LINE_X_MARGIN = 2.0


@dataclass(frozen=True)
class Triangle:
    v1: int
    v2: int
    v3: int


@dataclass(frozen=True)
class RampDimensions:
    part_name: str
    height: float
    ramp_run_depth: float
    top_landing_depth: float
    quarter_round_radius: float


def load_dimensions() -> RampDimensions:
    brief = json.loads(BRIEF_PATH.read_text())
    dimensions = brief["dimensions"]
    return RampDimensions(
        part_name=brief["name"],
        height=float(dimensions["threshold_height"]),
        ramp_run_depth=float(dimensions["ramp_run_depth"]),
        top_landing_depth=float(dimensions["top_landing_depth"]),
        quarter_round_radius=float(dimensions["quarter_round_relief_radius"]),
    )


def build_solid_profile(dimensions: RampDimensions) -> list[tuple[float, float]]:
    front_y = -dimensions.ramp_run_depth
    threshold_y = 0.0
    back_y = dimensions.top_landing_depth
    top_y = rear_profile_y_at_z(
        dimensions.height,
        dimensions.top_landing_depth,
        dimensions.quarter_round_radius,
    )

    profile = [
        (front_y, 0.0),
        (threshold_y, dimensions.height),
        (top_y, dimensions.height),
    ]
    start_angle = quarter_round_angle_for_z(dimensions.height, dimensions.quarter_round_radius)
    if dimensions.height > dimensions.quarter_round_radius:
        profile.append((back_y, dimensions.quarter_round_radius))
        start_angle = pi / 2.0
    for step in range(1, QUARTER_ROUND_SEGMENTS + 1):
        angle = start_angle + ((pi - start_angle) * step / QUARTER_ROUND_SEGMENTS)
        profile.append(
            (
                back_y + (dimensions.quarter_round_radius * cos(angle)),
                dimensions.quarter_round_radius * sin(angle),
            )
        )
    return ensure_ccw(profile)


def build_lightweight_profile(dimensions: RampDimensions) -> list[tuple[float, float]]:
    # Build a support-free underside cutout that removes most of the wedge mass
    # while leaving the quarter-round end and top shell intact for the fit test.
    outer = list(reversed(build_solid_profile(dimensions)))
    slope = dimensions.height / dimensions.ramp_run_depth
    inner_start_y = -dimensions.ramp_run_depth + (SHELL_THICKNESS / slope)

    inner = [
        (
            LIGHTWEIGHT_CAVITY_PEAK_Y,
            min(dimensions.height - SHELL_THICKNESS, LIGHTWEIGHT_CAVITY_PEAK_Z),
        ),
        (inner_start_y, 0.0),
    ]
    return ensure_ccw(outer + inner)


def quarter_round_angle_for_z(z_pos: float, radius: float) -> float:
    if z_pos >= radius:
        return pi / 2.0
    if z_pos <= 0:
        return pi
    return pi - asin(z_pos / radius)


def rear_profile_y_at_z(z_pos: float, top_landing_depth: float, radius: float) -> float:
    if z_pos <= 0.0:
        return top_landing_depth - radius
    if z_pos >= radius:
        return top_landing_depth
    return top_landing_depth - sqrt((radius * radius) - (z_pos * z_pos))


def top_surface_z_at_y(y_pos: float, dimensions: RampDimensions) -> float:
    if y_pos <= -dimensions.ramp_run_depth:
        return 0.0
    if y_pos >= 0.0:
        return dimensions.height
    return ((y_pos + dimensions.ramp_run_depth) / dimensions.ramp_run_depth) * dimensions.height


def ensure_ccw(profile: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return profile if polygon_area(profile) > 0 else list(reversed(profile))


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


def add_extruded_profile(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    profile: list[tuple[float, float]],
    x_min: float,
    x_max: float,
) -> None:
    start = len(vertices)
    for x in (x_min, x_max):
        vertices.extend((x, y, z) for y, z in profile)

    side_count = len(profile)
    cap_triangles = triangulate_polygon(profile)
    right_offset = start + side_count

    for triangle in cap_triangles:
        triangles.append(Triangle(start + triangle.v1, start + triangle.v2, start + triangle.v3))
        triangles.append(
            Triangle(
                right_offset + triangle.v1,
                right_offset + triangle.v3,
                right_offset + triangle.v2,
            )
        )

    for index in range(side_count):
        next_index = (index + 1) % side_count
        left_1 = start + index
        left_2 = start + next_index
        right_1 = right_offset + index
        right_2 = right_offset + next_index
        triangles.append(Triangle(left_1, right_1, right_2))
        triangles.append(Triangle(left_1, right_2, left_2))


def add_wavy_traction_lines(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    dimensions: RampDimensions,
) -> None:
    x_min = -(TEST_SLICE_WIDTH / 2.0) + TRACTION_LINE_X_MARGIN
    x_max = (TEST_SLICE_WIDTH / 2.0) - TRACTION_LINE_X_MARGIN
    line_spacing = dimensions.ramp_run_depth / (TRACTION_LINE_COUNT + 1)

    for line_index in range(TRACTION_LINE_COUNT):
        y_center = -dimensions.ramp_run_depth + (line_spacing * (line_index + 1))
        phase = line_index * (pi / 3.0)
        add_wavy_ribbon(vertices, triangles, dimensions, x_min, x_max, y_center, phase)


def add_wavy_ribbon(
    vertices: list[tuple[float, float, float]],
    triangles: list[Triangle],
    dimensions: RampDimensions,
    x_min: float,
    x_max: float,
    y_center: float,
    phase: float,
) -> None:
    start = len(vertices)
    samples = TRACTION_LINE_SAMPLES

    for sample in range(samples + 1):
        t = sample / samples
        x = x_min + ((x_max - x_min) * t)
        angle = (2.0 * pi * t) + phase
        y = y_center + (TRACTION_LINE_AMPLITUDE * sin(angle))
        dy_dx = TRACTION_LINE_AMPLITUDE * cos(angle) * (2.0 * pi / (x_max - x_min))
        normal_length = sqrt((dy_dx * dy_dx) + 1.0)
        normal_x = -dy_dx / normal_length
        normal_y = 1.0 / normal_length
        z_surface = top_surface_z_at_y(y, dimensions)

        for side in (-0.5, 0.5):
            offset_x = normal_x * TRACTION_LINE_WIDTH * side
            offset_y = normal_y * TRACTION_LINE_WIDTH * side
            vertices.append((x + offset_x, y + offset_y, z_surface - TRACTION_LINE_EMBED))
        for side in (-0.5, 0.5):
            offset_x = normal_x * TRACTION_LINE_WIDTH * side
            offset_y = normal_y * TRACTION_LINE_WIDTH * side
            vertices.append((x + offset_x, y + offset_y, z_surface + TRACTION_LINE_HEIGHT))

    for sample in range(samples):
        base = start + (sample * 4)
        nxt = base + 4
        # bottom, top, left side, right side
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


def write_binary_stl(path: Path, vertices: list[tuple[float, float, float]], triangles: list[Triangle]) -> None:
    with path.open("wb") as file:
        file.write(b"robot-vac-ramp-test-slice".ljust(80, b"\0"))
        file.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            file.write(struct.pack("<fff", 0.0, 0.0, 0.0))
            for vertex_index in (triangle.v1, triangle.v2, triangle.v3):
                file.write(struct.pack("<fff", *vertices[vertex_index]))
            file.write(struct.pack("<H", 0))


def write_3mf(path: Path, vertices: list[tuple[float, float, float]], triangles: list[Triangle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("3D/3dmodel.model", _model_xml(vertices, triangles))


def _model_xml(vertices: list[tuple[float, float, float]], triangles: list[Triangle]) -> bytes:
    model = ET.Element(
        f"{{{CORE_NS}}}model",
        attrib={"unit": "millimeter", "xml:lang": "en-US"},
    )
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", attrib={"name": "Application"}).text = "llm-to-3dprint"
    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    object_el = ET.SubElement(resources, f"{{{CORE_NS}}}object", attrib={"id": "1", "type": "model"})
    ET.SubElement(object_el, f"{{{CORE_NS}}}metadata", attrib={"name": "Title"}).text = "test_slice_20mm_wide"
    mesh_el = ET.SubElement(object_el, f"{{{CORE_NS}}}mesh")
    vertices_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}vertices")

    for x, y, z in vertices:
        ET.SubElement(
            vertices_el,
            f"{{{CORE_NS}}}vertex",
            attrib={"x": f"{x:.6f}", "y": f"{y:.6f}", "z": f"{z:.6f}"},
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


def _content_types_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>"""


def _root_relationships_xml() -> bytes:
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def build_variant_mesh(dimensions: RampDimensions, lightweight: bool) -> tuple[list[tuple[float, float, float]], list[Triangle]]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[Triangle] = []
    profile = build_lightweight_profile(dimensions) if lightweight else build_solid_profile(dimensions)
    add_extruded_profile(
        vertices,
        triangles,
        profile,
        -(TEST_SLICE_WIDTH / 2.0),
        TEST_SLICE_WIDTH / 2.0,
    )
    add_wavy_traction_lines(vertices, triangles, dimensions)
    return vertices, triangles


def export_variant(dimensions: RampDimensions, variant: str, lightweight: bool) -> list[Path]:
    width_label = f"{TEST_SLICE_WIDTH:g}mm".replace(".", "p")
    height_label = f"{dimensions.height:g}mm".replace(".", "p")
    depth_label = f"{dimensions.ramp_run_depth + dimensions.top_landing_depth:g}mm".replace(".", "p")
    radius_label = f"{dimensions.quarter_round_radius:g}mm".replace(".", "p")
    stem = (
        f"{dimensions.part_name}_test_slice_{width_label}_wide_d{depth_label}_h{height_label}_"
        f"quarter_round_{radius_label}_{variant}"
    )
    stl_path = OUTPUT_DIR / f"{stem}.stl"
    file_3mf = OUTPUT_DIR / f"{stem}.3mf"
    vertices, triangles = build_variant_mesh(dimensions, lightweight=lightweight)
    write_binary_stl(stl_path, vertices, triangles)
    write_3mf(file_3mf, vertices, triangles)
    return [stl_path, file_3mf]


def export_test_slice() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dimensions = load_dimensions()
    outputs: list[Path] = []
    outputs.extend(export_variant(dimensions, "reinforced_solid_wavy", lightweight=False))
    outputs.extend(export_variant(dimensions, "reinforced_lightweight_wavy", lightweight=True))
    return outputs


if __name__ == "__main__":
    for output in export_test_slice():
        print(output)

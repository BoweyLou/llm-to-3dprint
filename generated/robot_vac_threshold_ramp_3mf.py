"""Create neutral 3MF plate files for the robot-vac threshold ramp.

This is a deterministic fallback when Bambu Studio's native project serializer
is unavailable or crashes. It intentionally writes a simple standards-oriented
3MF package so slicers see geometry without relying on Bambu project metadata.
"""

from __future__ import annotations

import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cadquery import exporters

import robot_vac_threshold_ramp as ramp


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
PART_NAME = "robot_vac_threshold_ramp"

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", CORE_NS)


@dataclass(frozen=True)
class Mesh:
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]


@dataclass(frozen=True)
class PlacedMesh:
    name: str
    stl_path: Path
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


def read_binary_stl(path: Path) -> Mesh:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{path} is too short to be a binary STL")

    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_length = 84 + (triangle_count * 50)
    if len(data) < expected_length:
        raise ValueError(f"{path} is truncated: expected {expected_length} bytes")

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_index: dict[tuple[float, float, float], int] = {}

    offset = 84
    for _ in range(triangle_count):
        offset += 12  # normal
        tri_indices: list[int] = []
        for _vertex in range(3):
            raw = struct.unpack_from("<fff", data, offset)
            offset += 12
            # Rounding deduplicates vertices without relying on exact float bytes.
            vertex = tuple(round(float(value), 6) for value in raw)
            if vertex not in vertex_index:
                vertex_index[vertex] = len(vertices)
                vertices.append(vertex)
            tri_indices.append(vertex_index[vertex])
        triangles.append((tri_indices[0], tri_indices[1], tri_indices[2]))
        offset += 2  # attribute byte count

    return Mesh(vertices=vertices, triangles=triangles)


def write_3mf(path: Path, placements: list[PlacedMesh]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr("3D/3dmodel.model", _top_model_xml(placements))


def _top_model_xml(placements: list[PlacedMesh]) -> bytes:
    model = _new_model_root()
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", attrib={"name": "Application"}).text = "llm-to-3dprint"

    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    build = ET.SubElement(model, f"{{{CORE_NS}}}build")

    for index, placement in enumerate(placements, start=1):
        object_id = index
        mesh = read_binary_stl(placement.stl_path)
        object_el = ET.SubElement(
            resources,
            f"{{{CORE_NS}}}object",
            attrib={
                "id": str(object_id),
                "type": "model",
            },
        )
        ET.SubElement(object_el, f"{{{CORE_NS}}}metadata", attrib={"name": "Title"}).text = placement.name
        _add_mesh(object_el, mesh)

        tx = 128.0 + placement.x
        ty = 150.0 + placement.y
        tz = placement.z
        transform = f"1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}"
        ET.SubElement(
            build,
            f"{{{CORE_NS}}}item",
            attrib={
                "objectid": str(object_id),
                "transform": transform,
                "printable": "1",
            },
        )

    return _xml_bytes(model)


def _add_mesh(object_el: ET.Element, mesh: Mesh) -> None:
    mesh_el = ET.SubElement(object_el, f"{{{CORE_NS}}}mesh")
    vertices_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}vertices")
    for x, y, z in mesh.vertices:
        ET.SubElement(
            vertices_el,
            f"{{{CORE_NS}}}vertex",
            attrib={"x": f"{x:.6f}", "y": f"{y:.6f}", "z": f"{z:.6f}"},
        )

    triangles_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}triangles")
    for v1, v2, v3 in mesh.triangles:
        ET.SubElement(
            triangles_el,
            f"{{{CORE_NS}}}triangle",
            attrib={"v1": str(v1), "v2": str(v2), "v3": str(v3)},
        )


def _new_model_root() -> ET.Element:
    return ET.Element(
        f"{{{CORE_NS}}}model",
        attrib={
            "unit": "millimeter",
            "xml:lang": "en-US",
        },
    )


def _xml_bytes(element: ET.Element) -> bytes:
    ET.indent(element)
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


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


def build_plate_files() -> list[Path]:
    plate_1 = OUTPUT_DIR / f"{PART_NAME}_plate_1_segment_1.3mf"
    plate_2 = OUTPUT_DIR / f"{PART_NAME}_plate_2_segment_2.3mf"
    plate_3 = OUTPUT_DIR / f"{PART_NAME}_plate_3_segment_3_and_keys.3mf"

    with tempfile.TemporaryDirectory(prefix=f"{PART_NAME}_meshes_") as tmpdir:
        tmp = Path(tmpdir)
        segment_paths: list[Path] = []
        for index in range(ramp.SEGMENT_COUNT):
            path = tmp / f"{PART_NAME}_segment_{index + 1}_of_{ramp.SEGMENT_COUNT}.stl"
            exporters.export(ramp.build_segment(index), str(path))
            segment_paths.append(path)

        connector = tmp / f"{PART_NAME}_connector_key.stl"
        exporters.export(ramp.build_connector_key(), str(connector))

        write_3mf(plate_1, [PlacedMesh("ramp_segment_1", segment_paths[0])])
        write_3mf(plate_2, [PlacedMesh("ramp_segment_2", segment_paths[1])])

        key_x_positions = (-95.0, -57.0, -19.0, 19.0, 57.0, 95.0)
        plate_3_placements = [PlacedMesh("ramp_segment_3", segment_paths[2])]
        plate_3_placements.extend(
            PlacedMesh(f"connector_key_{index}", connector, x=x_pos, y=75.0)
            for index, x_pos in enumerate(key_x_positions, start=1)
        )
        write_3mf(plate_3, plate_3_placements)

    return [plate_1, plate_2, plate_3]


if __name__ == "__main__":
    for output in build_plate_files():
        print(output)

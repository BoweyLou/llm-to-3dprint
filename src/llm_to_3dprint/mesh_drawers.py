from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

from llm_to_3dprint.brief import DesignBrief, DrawerPatchMask, DrawerStack


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("", CORE_NS)


@dataclass(frozen=True)
class Triangle:
    source_id: int | None
    vertices: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    @property
    def centroid(self) -> tuple[float, float, float]:
        return (
            sum(vertex[0] for vertex in self.vertices) / 3.0,
            sum(vertex[1] for vertex in self.vertices) / 3.0,
            sum(vertex[2] for vertex in self.vertices) / 3.0,
        )


@dataclass(slots=True)
class SourceMesh:
    source_path: Path
    model_member: str
    source_sha256: str
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]

    @property
    def facet_count(self) -> int:
        return len(self.triangles)

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    def source_triangle(self, index: int) -> Triangle:
        triangle = self.triangles[index]
        return Triangle(
            source_id=index,
            vertices=(
                self.vertices[triangle[0]],
                self.vertices[triangle[1]],
                self.vertices[triangle[2]],
            ),
        )


@dataclass(slots=True)
class MeshPart:
    name: str
    source_triangles: list[Triangle] = field(default_factory=list)
    skin_shell_triangles: list[Triangle] = field(default_factory=list)
    generated_triangles: list[Triangle] = field(default_factory=list)
    stl_path: str | None = None

    @property
    def source_triangle_ids(self) -> list[int]:
        return [
            triangle.source_id
            for triangle in self.source_triangles
            if triangle.source_id is not None
        ]

    @property
    def source_triangle_count(self) -> int:
        return len(self.source_triangles)

    @property
    def skin_shell_triangle_count(self) -> int:
        return len(self.skin_shell_triangles)

    @property
    def functional_triangle_count(self) -> int:
        return len(self.generated_triangles)

    @property
    def generated_triangle_count(self) -> int:
        return len(self.skin_shell_triangles) + len(self.generated_triangles)

    @property
    def triangles(self) -> list[Triangle]:
        return [*self.source_triangles, *self.skin_shell_triangles, *self.generated_triangles]


@dataclass(frozen=True)
class MeshPreservedDrawerBuildResult:
    output_dir: Path
    manifest_path: Path
    combined_3mf_path: Path
    assembled_preview_3mf_path: Path
    front_review_3mf_path: Path
    source_skin_preview_3mf_path: Path
    functional_3mf_path: Path
    bambu_project_path: Path
    part_stl_paths: list[Path]
    source_facet_count: int
    assigned_source_triangle_count: int
    duplicate_source_triangle_count: int
    unassigned_source_triangle_count: int
    nonmanifold_part_count: int = 0
    open_edge_count: int = 0
    functional_clearance_passes: bool = True

    @property
    def passes_triangle_accounting(self) -> bool:
        return (
            self.assigned_source_triangle_count == self.source_facet_count
            and self.duplicate_source_triangle_count == 0
            and self.unassigned_source_triangle_count == 0
        )

    @property
    def passes_geometry_health(self) -> bool:
        return (
            self.nonmanifold_part_count == 0
            and self.open_edge_count == 0
            and self.functional_clearance_passes
        )


def load_source_mesh(source_3mf: str | Path, source_model_member: str | None = None) -> SourceMesh:
    source_path = Path(source_3mf)
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(source_path) as archive:
        model_member = source_model_member or _find_mesh_model_member(archive)
        vertices: list[tuple[float, float, float]] = []
        triangles: list[tuple[int, int, int]] = []
        with archive.open(model_member) as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                tag = element.tag.rsplit("}", 1)[-1]
                if tag == "vertex":
                    vertices.append(
                        (
                            float(element.attrib["x"]),
                            float(element.attrib["y"]),
                            float(element.attrib["z"]),
                        )
                    )
                elif tag == "triangle":
                    triangles.append(
                        (
                            int(element.attrib["v1"]),
                            int(element.attrib["v2"]),
                            int(element.attrib["v3"]),
                        )
                    )
                element.clear()

    return SourceMesh(
        source_path=source_path,
        model_member=model_member,
        source_sha256=source_sha256,
        vertices=vertices,
        triangles=triangles,
    )


def build_mesh_preserved_drawers(
    brief: DesignBrief,
    output_dir: str | Path,
) -> MeshPreservedDrawerBuildResult:
    if brief.mesh_preservation is None or brief.drawer_stack is None:
        raise ValueError("Brief must include mesh_preservation and drawer_stack metadata")
    if brief.mesh_preservation.mesh_reuse_policy != "partition_visible_mesh":
        raise ValueError("Only mesh_reuse_policy='partition_visible_mesh' is supported")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    source_mesh = load_source_mesh(
        brief.mesh_preservation.source_3mf,
        source_model_member=brief.mesh_preservation.source_model_member,
    )

    parts = partition_drawer_mesh(source_mesh, brief)
    write_part_stls(parts, output, rotate_z_degrees=brief.mesh_preservation.canonical_rotate_z_degrees)
    combined_3mf_path = output / f"{brief.name}_plate.3mf"
    write_combined_3mf(
        combined_3mf_path,
        parts,
        rotate_z_degrees=brief.mesh_preservation.canonical_rotate_z_degrees,
        arrange_on_plate=True,
    )
    assembled_preview_3mf_path = output / f"{brief.name}_assembled_preview.3mf"
    write_assembled_preview_from_plate(combined_3mf_path, assembled_preview_3mf_path)
    front_review_3mf_path = output / f"{brief.name}_front_review.3mf"
    write_front_review_3mf_from_assembled(assembled_preview_3mf_path, front_review_3mf_path)
    source_skin_preview_3mf_path = output / f"{brief.name}_source_skin_preview.3mf"
    write_source_skin_preview_3mf(
        source_skin_preview_3mf_path,
        parts,
        rotate_z_degrees=brief.mesh_preservation.canonical_rotate_z_degrees,
    )
    functional_3mf_path = output / f"{brief.name}_functional_plate.3mf"
    write_functional_3mf(
        functional_3mf_path,
        parts,
        rotate_z_degrees=brief.mesh_preservation.canonical_rotate_z_degrees,
    )
    bambu_project_path = output / f"{brief.name}_bambu_project.json"
    write_bambu_project(
        brief,
        parts,
        bambu_project_path,
        combined_3mf_path,
        assembled_preview_3mf_path,
        front_review_3mf_path,
        source_skin_preview_3mf_path,
        functional_3mf_path,
    )
    manifest_path = output / f"{brief.name}_mesh_manifest.json"
    manifest = build_manifest(
        brief,
        source_mesh,
        parts,
        output,
        combined_3mf_path,
        assembled_preview_3mf_path,
        front_review_3mf_path,
        source_skin_preview_3mf_path,
        functional_3mf_path,
        bambu_project_path,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    accounting = manifest["triangle_accounting"]
    geometry = manifest["geometry_health"]
    return MeshPreservedDrawerBuildResult(
        output_dir=output,
        manifest_path=manifest_path,
        combined_3mf_path=combined_3mf_path,
        assembled_preview_3mf_path=assembled_preview_3mf_path,
        front_review_3mf_path=front_review_3mf_path,
        source_skin_preview_3mf_path=source_skin_preview_3mf_path,
        functional_3mf_path=functional_3mf_path,
        bambu_project_path=bambu_project_path,
        part_stl_paths=[Path(part.stl_path) for part in parts if part.stl_path],
        source_facet_count=manifest["source"]["source_facet_count"],
        assigned_source_triangle_count=accounting["assigned_source_triangle_count"],
        duplicate_source_triangle_count=accounting["duplicate_source_triangle_count"],
        unassigned_source_triangle_count=accounting["unassigned_source_triangle_count"],
        nonmanifold_part_count=geometry["nonmanifold_part_count"],
        open_edge_count=geometry["open_edge_count"],
        functional_clearance_passes=geometry["functional_clearance_passes"],
    )


def partition_drawer_mesh(source_mesh: SourceMesh, brief: DesignBrief) -> list[MeshPart]:
    if brief.drawer_stack is None:
        raise ValueError("Brief must include drawer_stack metadata")
    if brief.drawer_stack.face != "front":
        raise ValueError("mesh-preserved drawer partitioning currently supports front drawers only")

    drawer_parts = [
        MeshPart(name=f"{brief.name}_drawer_{index}")
        for index in range(1, brief.drawer_stack.drawer_count + 1)
    ]
    body = MeshPart(name=f"{brief.name}_body_preserved_mesh")

    source_triangles = [source_mesh.source_triangle(index) for index in range(source_mesh.facet_count)]
    assigned_to_drawer = _assign_front_visible_drawer_triangles(
        source_mesh,
        source_triangles,
        brief.drawer_stack,
    )
    for triangle_index, triangle in enumerate(source_triangles):
        drawer_index = assigned_to_drawer.get(triangle_index)
        if drawer_index is None:
            body.source_triangles.append(triangle)
        else:
            drawer_parts[drawer_index].source_triangles.append(triangle)

    _add_source_skin_shell_geometry(body, brief)
    for drawer_part, mask in zip(drawer_parts, brief.drawer_stack.patch_masks, strict=True):
        _add_drawer_front_backing_geometry(drawer_part, brief, mask)

    _add_generated_body_geometry(body, brief, drawer_parts)
    for drawer_part, mask in zip(drawer_parts, brief.drawer_stack.patch_masks, strict=True):
        _add_generated_drawer_geometry(drawer_part, brief, mask)

    return [body, *drawer_parts]


def build_manifest(
    brief: DesignBrief,
    source_mesh: SourceMesh,
    parts: list[MeshPart],
    output_dir: Path,
    combined_3mf_path: Path,
    assembled_preview_3mf_path: Path,
    front_review_3mf_path: Path,
    source_skin_preview_3mf_path: Path,
    functional_3mf_path: Path,
    bambu_project_path: Path,
) -> dict:
    assigned_ids: list[int] = []
    for part in parts:
        assigned_ids.extend(part.source_triangle_ids)

    counts = Counter(assigned_ids)
    duplicate_ids = sorted(source_id for source_id, count in counts.items() if count > 1)
    all_source_ids = set(range(source_mesh.facet_count))
    assigned_set = set(assigned_ids)
    unassigned_ids = sorted(all_source_ids - assigned_set)

    part_entries = []
    for part in parts:
        source_skin_health = audit_mesh_health(part.source_triangles)
        source_skin_shell_health = audit_mesh_health(
            [*part.source_triangles, *part.skin_shell_triangles]
        )
        functional_mesh_health = audit_mesh_health(part.generated_triangles)
        mesh_preserved_output_health = audit_mesh_health(part.triangles)
        part_entries.append(
            {
                "name": part.name,
                "stl_path": _relative_to(part.stl_path, output_dir) if part.stl_path else None,
                "source_triangle_count": part.source_triangle_count,
                "skin_shell_triangle_count": part.skin_shell_triangle_count,
                "functional_triangle_count": part.functional_triangle_count,
                "generated_triangle_count": part.generated_triangle_count,
                "source_triangle_ids": part.source_triangle_ids,
                "source_skin_health": source_skin_health,
                "source_skin_shell_health": source_skin_shell_health,
                "functional_mesh_health": functional_mesh_health,
                "mesh_preserved_output_health": mesh_preserved_output_health,
                "combined_mesh_health": mesh_preserved_output_health,
            }
        )
    clearance_checks = _drawer_clearance_checks(brief, parts)
    functional_health_entries = [part["functional_mesh_health"] for part in part_entries]
    functional_nonmanifold_part_count = sum(
        1 for health in functional_health_entries if not health["manifold"]
    )
    functional_open_edge_count = sum(health["open_edge_count"] for health in functional_health_entries)
    functional_nonmanifold_edge_count = sum(
        health["nonmanifold_edge_count"] for health in functional_health_entries
    )
    output_health_entries = [part["mesh_preserved_output_health"] for part in part_entries]
    strict_nonmanifold_part_count = sum(
        1 for health in output_health_entries if not health["manifold"]
    )
    nonmanifold_part_count = sum(
        1 for health in output_health_entries if not health["slicer_manifold"]
    )
    open_edge_count = sum(health["open_edge_count"] for health in output_health_entries)
    strict_nonmanifold_edge_count = sum(
        health["nonmanifold_edge_count"] for health in output_health_entries
    )
    nonmanifold_edge_count = sum(
        health["oriented_boundary_error_count"] for health in output_health_entries
    )

    return {
        "name": brief.name,
        "source": {
            "source_3mf": str(source_mesh.source_path),
            "source_sha256": source_mesh.source_sha256,
            "source_model_member": source_mesh.model_member,
            "source_vertex_count": source_mesh.vertex_count,
            "source_facet_count": source_mesh.facet_count,
            "canonical_transform": {
                "rotate_z_degrees": brief.mesh_preservation.canonical_rotate_z_degrees
                if brief.mesh_preservation
                else 0.0,
            },
        },
        "outputs": {
            "output_dir": str(output_dir),
            "mesh_preserved_print_3mf": str(combined_3mf_path),
            "assembled_preview_3mf": str(assembled_preview_3mf_path),
            "front_review_3mf": str(front_review_3mf_path),
            "source_skin_preview_3mf": str(source_skin_preview_3mf_path),
            "combined_review_3mf": str(combined_3mf_path),
            "functional_core_3mf": str(functional_3mf_path),
            "bambu_project": str(bambu_project_path),
        },
        "artifact_roles": {
            "mesh_preserved_print_3mf": {
                "path": str(combined_3mf_path),
                "contains_source_triangles": True,
                "contains_generated_shells": True,
                "contains_functional_cores": True,
                "print_readiness_gate": "mesh_preserved_output_health",
            },
            "functional_core_3mf": {
                "path": str(functional_3mf_path),
                "contains_source_triangles": False,
                "contains_generated_shells": False,
                "contains_functional_cores": True,
                "print_readiness_gate": "functional_mesh_health",
            },
            "assembled_preview_3mf": {
                "path": str(assembled_preview_3mf_path),
                "contains_source_triangles": True,
                "contains_generated_shells": True,
                "contains_functional_cores": True,
                "print_readiness_gate": "visual_review_only",
            },
            "front_review_3mf": {
                "path": str(front_review_3mf_path),
                "contains_source_triangles": True,
                "contains_generated_shells": True,
                "contains_functional_cores": True,
                "camera_orientation": "drawer_front",
                "print_readiness_gate": "visual_review_only",
            },
            "source_skin_preview_3mf": {
                "path": str(source_skin_preview_3mf_path),
                "contains_source_triangles": True,
                "contains_generated_shells": False,
                "contains_functional_cores": False,
                "source_facet_count": source_mesh.facet_count,
                "print_readiness_gate": "visual_review_only",
            },
        },
        "drawer_stack": asdict(brief.drawer_stack) if brief.drawer_stack else None,
        "functional_clearance_checks": clearance_checks,
        "parts": part_entries,
        "triangle_accounting": {
            "assigned_source_triangle_count": len(assigned_set),
            "duplicate_source_triangle_count": len(duplicate_ids),
            "unassigned_source_triangle_count": len(unassigned_ids),
            "passes": not duplicate_ids and not unassigned_ids,
            "duplicate_source_triangle_ids": duplicate_ids,
            "unassigned_source_triangle_ids": unassigned_ids,
        },
        "geometry_health": {
            "passes": (
                nonmanifold_part_count == 0
                and open_edge_count == 0
                and functional_nonmanifold_part_count == 0
                and functional_open_edge_count == 0
                and clearance_checks["passes"]
            ),
            "scope": "mesh_preserved_output_and_functional_generated_geometry",
            "part_count": len(output_health_entries),
            "nonmanifold_part_count": nonmanifold_part_count,
            "open_edge_count": open_edge_count,
            "nonmanifold_edge_count": nonmanifold_edge_count,
            "strict_nonmanifold_part_count": strict_nonmanifold_part_count,
            "strict_nonmanifold_edge_count": strict_nonmanifold_edge_count,
            "functional_nonmanifold_part_count": functional_nonmanifold_part_count,
            "functional_open_edge_count": functional_open_edge_count,
            "functional_nonmanifold_edge_count": functional_nonmanifold_edge_count,
            "mesh_preserved_output_nonmanifold_part_count": nonmanifold_part_count,
            "mesh_preserved_output_open_edge_count": open_edge_count,
            "mesh_preserved_output_nonmanifold_edge_count": nonmanifold_edge_count,
            "mesh_preserved_output_strict_nonmanifold_part_count": strict_nonmanifold_part_count,
            "mesh_preserved_output_strict_nonmanifold_edge_count": strict_nonmanifold_edge_count,
            "combined_review_nonmanifold_part_count": nonmanifold_part_count,
            "functional_clearance_passes": clearance_checks["passes"],
        },
    }


def validate_mesh_manifest(manifest_path: str | Path) -> dict:
    manifest = json.loads(Path(manifest_path).read_text())
    source_count = manifest["source"]["source_facet_count"]
    all_ids: list[int] = []
    for part in manifest["parts"]:
        all_ids.extend(part["source_triangle_ids"])

    counts = Counter(all_ids)
    duplicate_ids = sorted(source_id for source_id, count in counts.items() if count > 1)
    unassigned_ids = sorted(set(range(source_count)) - set(all_ids))
    source_accounting_passes = (
        not duplicate_ids and not unassigned_ids and len(set(all_ids)) == source_count
    )
    geometry = manifest.get("geometry_health")
    geometry_passes = True if geometry is None else bool(geometry.get("passes", False))
    clearance = manifest.get("functional_clearance_checks", {})
    clearance_passes = bool(clearance.get("passes", True))
    passes = source_accounting_passes and geometry_passes and clearance_passes
    return {
        "passes": passes,
        "source_accounting_passes": source_accounting_passes,
        "geometry_passes": geometry_passes,
        "functional_clearance_passes": clearance_passes,
        "source_facet_count": source_count,
        "assigned_source_triangle_count": len(set(all_ids)),
        "duplicate_source_triangle_count": len(duplicate_ids),
        "unassigned_source_triangle_count": len(unassigned_ids),
        "nonmanifold_part_count": geometry.get("nonmanifold_part_count", 0) if geometry else 0,
        "open_edge_count": geometry.get("open_edge_count", 0) if geometry else 0,
        "nonmanifold_edge_count": geometry.get("nonmanifold_edge_count", 0) if geometry else 0,
        "strict_nonmanifold_part_count": geometry.get("strict_nonmanifold_part_count", 0)
        if geometry
        else 0,
        "strict_nonmanifold_edge_count": geometry.get("strict_nonmanifold_edge_count", 0)
        if geometry
        else 0,
    }


def format_mesh_manifest_validation(result: dict) -> str:
    status = "PASS" if result["passes"] else "FAIL"
    return (
        f"{status} mesh manifest: source_facets={result['source_facet_count']}, "
        f"assigned={result['assigned_source_triangle_count']}, "
        f"duplicates={result['duplicate_source_triangle_count']}, "
        f"unassigned={result['unassigned_source_triangle_count']}, "
        f"geometry={'PASS' if result['geometry_passes'] else 'FAIL'}, "
        f"clearance={'PASS' if result['functional_clearance_passes'] else 'FAIL'}, "
        f"nonmanifold_parts={result['nonmanifold_part_count']}, "
        f"open_edges={result['open_edge_count']}, "
        f"nonmanifold_edges={result['nonmanifold_edge_count']}, "
        f"strict_nonmanifold_edges={result['strict_nonmanifold_edge_count']}"
    )


def write_part_stls(parts: list[MeshPart], output_dir: Path, *, rotate_z_degrees: float) -> None:
    for part in parts:
        stl_path = output_dir / f"{part.name}.stl"
        write_binary_stl(stl_path, part.triangles, rotate_z_degrees=rotate_z_degrees)
        part.stl_path = str(stl_path)


def audit_mesh_health(triangles: list[Triangle]) -> dict:
    edge_counts: Counter[
        tuple[tuple[float, float, float], tuple[float, float, float]]
    ] = Counter()
    directed_edge_counts: Counter[
        tuple[tuple[float, float, float], tuple[float, float, float]]
    ] = Counter()
    for triangle in triangles:
        points = triangle.vertices
        for a, b in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            key_a = _vertex_key(a)
            key_b = _vertex_key(b)
            key = (key_a, key_b) if key_a <= key_b else (key_b, key_a)
            edge_counts[key] += 1
            directed_edge_counts[(key_a, key_b)] += 1

    open_edge_count = sum(1 for count in edge_counts.values() if count == 1)
    nonmanifold_edge_count = sum(1 for count in edge_counts.values() if count > 2)
    oriented_boundary_error_count = 0
    for key_a, key_b in edge_counts:
        oriented_boundary_error_count += abs(
            directed_edge_counts[(key_a, key_b)] - directed_edge_counts[(key_b, key_a)]
        )
    return {
        "triangle_count": len(triangles),
        "edge_count": len(edge_counts),
        "open_edge_count": open_edge_count,
        "nonmanifold_edge_count": nonmanifold_edge_count,
        "oriented_boundary_error_count": oriented_boundary_error_count,
        "manifold": open_edge_count == 0 and nonmanifold_edge_count == 0,
        "slicer_manifold": open_edge_count == 0 and oriented_boundary_error_count == 0,
    }


def write_binary_stl(
    path: str | Path,
    triangles: list[Triangle],
    *,
    rotate_z_degrees: float = 0.0,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    header = b"llm-to-3dprint mesh-preserved drawer output"
    header = header[:80].ljust(80, b" ")
    with destination.open("wb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            vertices = tuple(_rotate_z(vertex, rotate_z_degrees) for vertex in triangle.vertices)
            normal = _triangle_normal(vertices)
            stream.write(struct.pack("<fff", *normal))
            for vertex in vertices:
                stream.write(struct.pack("<fff", *vertex))
            stream.write(struct.pack("<H", 0))


def write_combined_3mf(
    path: str | Path,
    parts: list[MeshPart],
    *,
    rotate_z_degrees: float = 0.0,
    arrange_on_plate: bool = True,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_relationships_xml())
        archive.writestr(
            "3D/3dmodel.model",
            _combined_3mf_model_xml(parts, rotate_z_degrees, arrange_on_plate=arrange_on_plate),
        )


def write_functional_3mf(
    path: str | Path,
    parts: list[MeshPart],
    *,
    rotate_z_degrees: float = 0.0,
) -> None:
    functional_parts = [
        MeshPart(name=f"{part.name}_functional_core", generated_triangles=part.generated_triangles)
        for part in parts
    ]
    write_combined_3mf(path, functional_parts, rotate_z_degrees=rotate_z_degrees)


def write_source_skin_preview_3mf(
    path: str | Path,
    parts: list[MeshPart],
    *,
    rotate_z_degrees: float = 0.0,
) -> None:
    source_skin_parts = [
        MeshPart(name=f"{part.name}_source_skin", source_triangles=part.source_triangles)
        for part in parts
    ]
    write_combined_3mf(
        path,
        source_skin_parts,
        rotate_z_degrees=rotate_z_degrees,
        arrange_on_plate=False,
    )


def write_assembled_preview_from_plate(source_3mf: str | Path, destination_3mf: str | Path) -> None:
    source = Path(source_3mf)
    destination = Path(destination_3mf)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source, "r") as input_archive:
        model = ET.fromstring(input_archive.read("3D/3dmodel.model"))
        for item in model.findall(f".//{{{CORE_NS}}}item"):
            item.set("transform", "1 0 0 0 1 0 0 0 1 0.000000 0.000000 0.000000")
        ET.indent(model)
        model_bytes = ET.tostring(model, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output_archive:
            for entry in input_archive.infolist():
                data = model_bytes if entry.filename == "3D/3dmodel.model" else input_archive.read(entry.filename)
                output_archive.writestr(entry.filename, data)


def write_front_review_3mf_from_assembled(source_3mf: str | Path, destination_3mf: str | Path) -> None:
    """Write a view-only copy rotated so Bambu's default camera sees drawer fronts."""
    source = Path(source_3mf)
    destination = Path(destination_3mf)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source, "r") as input_archive:
        model = ET.fromstring(input_archive.read("3D/3dmodel.model"))
        for vertex in model.findall(f".//{{{CORE_NS}}}vertex"):
            x = float(vertex.attrib["x"])
            y = float(vertex.attrib["y"])
            vertex.set("x", f"{-x:.6f}")
            vertex.set("y", f"{-y:.6f}")
        ET.indent(model)
        model_bytes = ET.tostring(model, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output_archive:
            for entry in input_archive.infolist():
                data = model_bytes if entry.filename == "3D/3dmodel.model" else input_archive.read(entry.filename)
                output_archive.writestr(entry.filename, data)


def write_bambu_project(
    brief: DesignBrief,
    parts: list[MeshPart],
    path: str | Path,
    combined_3mf_path: Path,
    assembled_preview_3mf_path: Path,
    front_review_3mf_path: Path,
    source_skin_preview_3mf_path: Path,
    functional_3mf_path: Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": f"{brief.name}_a1_handoff",
        "description": (
            "Bambu A1 handoff for mesh-preserved functional drawer organiser. "
            "Source mesh triangles are partitioned across the fixed body and drawer fronts."
        ),
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "none",
        "filament_count": 1,
        "export_backend": "clean_room_3mf",
        "output_3mf": str(combined_3mf_path),
        "mesh_preserved_print_3mf": str(combined_3mf_path),
        "assembled_preview_3mf": str(assembled_preview_3mf_path),
        "front_review_3mf": str(front_review_3mf_path),
        "source_skin_preview_3mf": str(source_skin_preview_3mf_path),
        "combined_review_3mf": str(combined_3mf_path),
        "functional_core_3mf": str(functional_3mf_path),
        "source_brief": brief.name,
        "parts": [
            {
                "name": part.name,
                "path": part.stl_path,
                "part_name": part.name,
                "load_strategy": "separate_object",
                "print_mode": "standalone",
                "plate": 1,
                "filament": 1,
                "notes": (
                    f"{part.source_triangle_count} preserved source triangles; "
                    f"{part.skin_shell_triangle_count} generated skin-shell triangles; "
                    f"{part.functional_triangle_count} generated functional triangles."
                ),
            }
            for part in parts
        ],
        "notes": [
            "Single-material Bambu A1 project.",
            "The mesh-preserved print 3MF and per-part STLs retain the source triangle skin.",
            "The front-review 3MF is view-only and rotated for Bambu's camera to show the drawer side.",
            "The source-skin preview 3MF contains only the original source triangles for visual proof.",
            "The functional-core 3MF is diagnostic generated geometry only.",
            "STEP is intentionally not emitted for the preserved mesh skin.",
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


def _find_mesh_model_member(archive: zipfile.ZipFile) -> str:
    object_models = [
        name
        for name in archive.namelist()
        if name.startswith("3D/Objects/") and name.endswith(".model")
    ]
    if object_models:
        return sorted(object_models)[0]
    if "3D/3dmodel.model" in archive.namelist():
        return "3D/3dmodel.model"
    raise ValueError("3MF package does not contain a readable mesh model")


def _mask_contains_triangle(mask: DrawerPatchMask, triangle: Triangle) -> bool:
    x, y, z = triangle.centroid
    return (
        mask.x_min <= x < mask.x_max
        and mask.y_min <= y < mask.y_max
        and mask.z_min <= z < mask.z_max
    )


def _assign_front_visible_drawer_triangles(
    source_mesh: SourceMesh,
    source_triangles: list[Triangle],
    stack: DrawerStack,
) -> dict[int, int]:
    assigned: dict[int, int] = {}
    for drawer_index, mask in enumerate(stack.patch_masks):
        candidate_entries = _front_visible_candidates(source_mesh, source_triangles, mask, stack)
        selected = _select_front_visible_patch(candidate_entries, mask, stack)
        for triangle_index in selected:
            if triangle_index in assigned:
                raise ValueError(f"source triangle {triangle_index} matched multiple drawer masks")
            assigned[triangle_index] = drawer_index
    return assigned


def _front_visible_candidates(
    source_mesh: SourceMesh,
    source_triangles: list[Triangle],
    mask: DrawerPatchMask,
    stack: DrawerStack,
) -> list[tuple[int, Triangle]]:
    if stack.skin_selection_strategy == "front_visible_raycast":
        raycast_ids = _open3d_front_visible_triangle_ids(source_mesh, mask, stack)
        if raycast_ids is not None:
            return [
                (triangle_index, source_triangles[triangle_index])
                for triangle_index in sorted(raycast_ids)
                if _mask_contains_triangle(mask, source_triangles[triangle_index])
            ]

    return [
        (triangle_index, triangle)
        for triangle_index, triangle in enumerate(source_triangles)
        if _mask_contains_triangle(mask, triangle)
    ]


def _open3d_front_visible_triangle_ids(
    source_mesh: SourceMesh,
    mask: DrawerPatchMask,
    stack: DrawerStack,
) -> set[int] | None:
    try:
        import numpy as np
        import open3d as o3d
    except ImportError:
        return None

    if not source_mesh.vertices or not source_mesh.triangles:
        return set()

    vertices = np.asarray(source_mesh.vertices, dtype=np.float32)
    triangles = np.asarray(source_mesh.triangles, dtype=np.uint32)
    mesh = o3d.t.geometry.TriangleMesh()
    mesh.vertex["positions"] = o3d.core.Tensor(vertices, dtype=o3d.core.Dtype.Float32)
    mesh.triangle["indices"] = o3d.core.Tensor(triangles, dtype=o3d.core.Dtype.UInt32)
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(mesh)

    x_count = max(1, int(math.ceil((mask.x_max - mask.x_min) / stack.visibility_grid)) + 1)
    z_count = max(1, int(math.ceil((mask.z_max - mask.z_min) / stack.visibility_grid)) + 1)
    origin_y = max(vertex[1] for vertex in source_mesh.vertices) + 5.0
    rays = np.zeros((x_count * z_count, 6), dtype=np.float32)
    index = 0
    for x_index in range(x_count):
        x = min(mask.x_max, mask.x_min + (x_index * stack.visibility_grid))
        for z_index in range(z_count):
            z = min(mask.z_max, mask.z_min + (z_index * stack.visibility_grid))
            rays[index] = (x, origin_y, z, 0.0, -1.0, 0.0)
            index += 1

    hits = scene.cast_rays(o3d.core.Tensor(rays, dtype=o3d.core.Dtype.Float32))
    primitive_ids = hits["primitive_ids"].numpy()
    invalid_id = np.iinfo(primitive_ids.dtype).max
    return {int(primitive_id) for primitive_id in primitive_ids if primitive_id != invalid_id}


def _select_front_visible_patch(
    candidates: list[tuple[int, Triangle]],
    mask: DrawerPatchMask,
    stack: DrawerStack,
) -> set[int]:
    if not candidates:
        return set()

    cell_front_y: dict[tuple[int, int], float] = {}
    cell_by_triangle: dict[int, tuple[int, int]] = {}
    patch_front_y = max(triangle.centroid[1] for _index, triangle in candidates)
    for triangle_index, triangle in candidates:
        x, y, z = triangle.centroid
        cell = (
            int((x - mask.x_min) / stack.visibility_grid),
            int((z - mask.z_min) / stack.visibility_grid),
        )
        cell_by_triangle[triangle_index] = cell
        cell_front_y[cell] = max(cell_front_y.get(cell, -math.inf), y)

    selected: list[tuple[int, Triangle]] = []
    selected_without_normal_check: list[tuple[int, Triangle]] = []
    for triangle_index, triangle in candidates:
        _x, y, _z = triangle.centroid
        cell = cell_by_triangle[triangle_index]
        is_front_shell = y >= patch_front_y - stack.front_visibility_depth
        is_local_front = y >= cell_front_y[cell] - stack.local_visibility_depth
        if not (is_front_shell and is_local_front):
            continue
        selected_without_normal_check.append((triangle_index, triangle))
        if _triangle_normal(triangle.vertices)[1] >= stack.front_normal_min_y:
            selected.append((triangle_index, triangle))

    # Tiny fixture meshes and occasional near-flat source artifacts can have normals that do
    # not match the source's front axis. Keep the visibility result instead of dropping a patch.
    if not selected:
        selected = selected_without_normal_check

    return {
        triangle_index
        for triangle_index, _triangle in _filter_small_patch_components(
            selected,
            min_component_triangles=stack.min_patch_component_triangles,
        )
    }


def _filter_small_patch_components(
    triangles: list[tuple[int, Triangle]],
    *,
    min_component_triangles: int,
) -> list[tuple[int, Triangle]]:
    if min_component_triangles <= 1 or not triangles:
        return triangles

    vertex_to_triangles: defaultdict[
        tuple[float, float, float],
        list[int],
    ] = defaultdict(list)
    for local_index, (_source_id, triangle) in enumerate(triangles):
        for vertex in triangle.vertices:
            vertex_to_triangles[_vertex_key(vertex)].append(local_index)

    selected: list[tuple[int, Triangle]] = []
    seen = [False] * len(triangles)
    for local_index in range(len(triangles)):
        if seen[local_index]:
            continue
        stack = [local_index]
        seen[local_index] = True
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for vertex in triangles[current][1].vertices:
                for neighbour in vertex_to_triangles[_vertex_key(vertex)]:
                    if not seen[neighbour]:
                        seen[neighbour] = True
                        stack.append(neighbour)
        if len(component) >= min_component_triangles:
            selected.extend(triangles[index] for index in component)
    return selected if selected else triangles


def _add_source_skin_shell_geometry(part: MeshPart, brief: DesignBrief) -> None:
    stack = brief.drawer_stack
    if stack is None or not part.source_triangles:
        return
    part.skin_shell_triangles.extend(
        _source_skin_shell_triangles(
            part.source_triangles,
            shell_thickness=stack.source_skin_shell_thickness,
        )
    )


def _add_drawer_front_backing_geometry(
    part: MeshPart,
    brief: DesignBrief,
    mask: DrawerPatchMask,
) -> None:
    stack = brief.drawer_stack
    if stack is None or not part.source_triangles:
        return
    part.skin_shell_triangles.extend(
        _flat_backed_source_skin_shell_triangles(
            part.source_triangles,
            backing_y=_drawer_backing_y(part, mask, stack),
        )
    )


def _add_generated_body_geometry(
    part: MeshPart,
    brief: DesignBrief,
    drawer_parts: list[MeshPart],
) -> None:
    stack = brief.drawer_stack
    if stack is None:
        return
    rail = stack.body_wall_thickness

    for mask, drawer_part in zip(stack.patch_masks, drawer_parts, strict=True):
        y_front = _drawer_backing_y(drawer_part, mask, stack)
        y_back = y_front - stack.drawer_depth - rail
        part.generated_triangles.extend(
            _rectangular_tube_triangles(
                mask.x_min - rail,
                mask.x_max + rail,
                y_back,
                y_front,
                mask.z_min - rail,
                mask.z_max + rail,
                rail,
            )
        )


def _add_generated_drawer_geometry(part: MeshPart, brief: DesignBrief, mask: DrawerPatchMask) -> None:
    stack = brief.drawer_stack
    if stack is None:
        return
    clearance = stack.clearance
    wall = stack.drawer_wall_thickness

    x_min = mask.x_min + clearance
    x_max = mask.x_max - clearance
    z_min = mask.z_min + clearance
    z_max = mask.z_max - clearance
    y_front = _drawer_backing_y(part, mask, stack)
    y_back = y_front - stack.drawer_depth

    # The source mesh patch remains the visible skin. The generated drawer is a
    # clean manifold tray core that can be validated independently.
    part.generated_triangles.extend(
        _open_top_box_triangles(x_min, x_max, y_back, y_front, z_min, z_max, wall)
    )


def _drawer_clearance_checks(brief: DesignBrief, parts: list[MeshPart]) -> dict:
    stack = brief.drawer_stack
    if stack is None:
        return {"passes": True, "drawers": []}

    checks = []
    drawer_parts = parts[1:]
    for index, (drawer_part, mask) in enumerate(zip(drawer_parts, stack.patch_masks, strict=True), start=1):
        y_front = _drawer_backing_y(drawer_part, mask, stack)
        cavity = {
            "x_min": mask.x_min,
            "x_max": mask.x_max,
            "y_min": y_front - stack.drawer_depth - stack.body_wall_thickness,
            "y_max": y_front,
            "z_min": mask.z_min,
            "z_max": mask.z_max,
        }
        drawer = {
            "x_min": mask.x_min + stack.clearance,
            "x_max": mask.x_max - stack.clearance,
            "y_min": y_front - stack.drawer_depth,
            "y_max": y_front,
            "z_min": mask.z_min + stack.clearance,
            "z_max": mask.z_max - stack.clearance,
        }
        clearances = {
            "left": drawer["x_min"] - cavity["x_min"],
            "right": cavity["x_max"] - drawer["x_max"],
            "bottom": drawer["z_min"] - cavity["z_min"],
            "top": cavity["z_max"] - drawer["z_max"],
            "back": drawer["y_min"] - cavity["y_min"],
            "front": cavity["y_max"] - drawer["y_max"],
            "front_skin_proud": stack.front_backing_offset if drawer_part.source_triangles else 0.0,
        }
        sliding_clearances = [
            clearances["left"],
            clearances["right"],
            clearances["bottom"],
            clearances["top"],
        ]
        clearance_passes = all(
            stack.min_clearance <= value <= stack.max_clearance for value in sliding_clearances
        )
        fit_passes = (
            drawer["x_min"] >= cavity["x_min"]
            and drawer["x_max"] <= cavity["x_max"]
            and drawer["y_min"] >= cavity["y_min"]
            and drawer["y_max"] <= cavity["y_max"]
            and drawer["z_min"] >= cavity["z_min"]
            and drawer["z_max"] <= cavity["z_max"]
            and clearances["front_skin_proud"] > 0
        )
        checks.append(
            {
                "drawer_index": index,
                "part_name": drawer_part.name,
                "cavity_bounds": cavity,
                "drawer_bounds": drawer,
                "clearances": clearances,
                "passes": clearance_passes and fit_passes,
            }
        )

    return {
        "passes": all(check["passes"] for check in checks),
        "target_clearance": stack.clearance,
        "acceptable_clearance_range": {
            "min": stack.min_clearance,
            "max": stack.max_clearance,
        },
        "drawers": checks,
    }


def _drawer_backing_y(part: MeshPart, mask: DrawerPatchMask, stack: DrawerStack) -> float:
    if not part.source_triangles:
        return mask.y_max - stack.front_lip_depth
    skin_min_y = min(vertex[1] for triangle in part.source_triangles for vertex in triangle.vertices)
    return skin_min_y - stack.front_backing_offset


def _source_skin_shell_triangles(
    source_triangles: list[Triangle],
    *,
    shell_thickness: float,
) -> list[Triangle]:
    generated: list[Triangle] = []
    y_offset = -shell_thickness

    for triangle in source_triangles:
        inner = tuple(_offset_y(vertex, y_offset) for vertex in triangle.vertices)
        generated.append(Triangle(None, (inner[2], inner[1], inner[0])))

    for a, b in _boundary_edges(source_triangles):
        inner_a = _offset_y(a, y_offset)
        inner_b = _offset_y(b, y_offset)
        generated.extend(_quad_triangles(b, a, inner_a, inner_b))

    return generated


def _flat_backed_source_skin_shell_triangles(
    source_triangles: list[Triangle],
    *,
    backing_y: float,
) -> list[Triangle]:
    # Drawer fronts use a flat backing cap instead of a full duplicate of the
    # sculpted source skin, which avoids turning decorative relief boundaries
    # into visible fins while keeping the part slicer-closed.
    generated: list[Triangle] = []
    boundary_edges = _boundary_edges(source_triangles)

    for a, b in boundary_edges:
        projected_a = _project_y(a, backing_y)
        projected_b = _project_y(b, backing_y)
        generated.extend(_quad_triangles(b, a, projected_a, projected_b))

    for component in _boundary_edge_components(boundary_edges):
        generated.extend(_projected_boundary_fan_triangles(boundary_edges, component, backing_y))

    return generated


def _projected_boundary_fan_triangles(
    edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    component: list[int],
    target_y: float,
) -> list[Triangle]:
    projected_vertices = [
        _project_y(vertex, target_y)
        for edge_index in component
        for vertex in edges[edge_index]
    ]
    center = (
        sum(vertex[0] for vertex in projected_vertices) / len(projected_vertices),
        target_y,
        sum(vertex[2] for vertex in projected_vertices) / len(projected_vertices),
    )
    return [
        Triangle(
            None,
            (
                _project_y(edges[edge_index][1], target_y),
                _project_y(edges[edge_index][0], target_y),
                center,
            ),
        )
        for edge_index in component
    ]


def _quad_triangles(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
    d: tuple[float, float, float],
) -> list[Triangle]:
    return [Triangle(None, (a, b, c)), Triangle(None, (a, c, d))]


def _open_top_box_triangles(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    wall: float,
) -> list[Triangle]:
    x0, x1, x2, x3 = x_min, x_min + wall, x_max - wall, x_max
    y0, y1, y2, y3 = y_min, y_min + wall, y_max - wall, y_max
    z0, z1, z2 = z_min, z_min + wall, z_max
    if x1 >= x2 or y1 >= y2 or z1 >= z2:
        raise ValueError("open-top box wall is too large for the requested drawer dimensions")

    occupied = {
        (x_index, y_index, z_index)
        for x_index in range(3)
        for y_index in range(3)
        for z_index in range(2)
        if x_index in {0, 2} or y_index in {0, 2} or z_index == 0
    }
    return _orthogonal_grid_triangles([x0, x1, x2, x3], [y0, y1, y2, y3], [z0, z1, z2], occupied)


def _rectangular_tube_triangles(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
    wall: float,
) -> list[Triangle]:
    x0, x1, x2, x3 = x_min, x_min + wall, x_max - wall, x_max
    y0, y3 = y_min, y_max
    z0, z1, z2, z3 = z_min, z_min + wall, z_max - wall, z_max
    if x1 >= x2 or z1 >= z2:
        raise ValueError("rectangular tube wall is too large for the requested cavity dimensions")

    occupied = {
        (x_index, 0, z_index)
        for x_index in range(3)
        for z_index in range(3)
        if x_index in {0, 2} or z_index in {0, 2}
    }
    return _orthogonal_grid_triangles([x0, x1, x2, x3], [y0, y3], [z0, z1, z2, z3], occupied)


def _orthogonal_grid_triangles(
    x_coords: list[float],
    y_coords: list[float],
    z_coords: list[float],
    occupied_cells: set[tuple[int, int, int]],
) -> list[Triangle]:
    triangles: list[Triangle] = []
    directions = (
        (-1, 0, 0),
        (1, 0, 0),
        (0, -1, 0),
        (0, 1, 0),
        (0, 0, -1),
        (0, 0, 1),
    )
    for x_index, y_index, z_index in occupied_cells:
        x_min, x_max = x_coords[x_index], x_coords[x_index + 1]
        y_min, y_max = y_coords[y_index], y_coords[y_index + 1]
        z_min, z_max = z_coords[z_index], z_coords[z_index + 1]
        for dx, dy, dz in directions:
            neighbour = (x_index + dx, y_index + dy, z_index + dz)
            if neighbour in occupied_cells:
                continue
            if dx == -1:
                quad = ((x_min, y_min, z_min), (x_min, y_min, z_max), (x_min, y_max, z_max), (x_min, y_max, z_min))
            elif dx == 1:
                quad = ((x_max, y_min, z_min), (x_max, y_max, z_min), (x_max, y_max, z_max), (x_max, y_min, z_max))
            elif dy == -1:
                quad = ((x_min, y_min, z_min), (x_max, y_min, z_min), (x_max, y_min, z_max), (x_min, y_min, z_max))
            elif dy == 1:
                quad = ((x_min, y_max, z_min), (x_min, y_max, z_max), (x_max, y_max, z_max), (x_max, y_max, z_min))
            elif dz == -1:
                quad = ((x_min, y_min, z_min), (x_min, y_max, z_min), (x_max, y_max, z_min), (x_max, y_min, z_min))
            else:
                quad = ((x_min, y_min, z_max), (x_max, y_min, z_max), (x_max, y_max, z_max), (x_min, y_max, z_max))
            triangles.extend(_quad_triangles(*quad))
    return triangles


def _box_triangles(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    z_min: float,
    z_max: float,
) -> list[Triangle]:
    vertices = {
        "000": (x_min, y_min, z_min),
        "100": (x_max, y_min, z_min),
        "110": (x_max, y_max, z_min),
        "010": (x_min, y_max, z_min),
        "001": (x_min, y_min, z_max),
        "101": (x_max, y_min, z_max),
        "111": (x_max, y_max, z_max),
        "011": (x_min, y_max, z_max),
    }
    faces = [
        ("000", "100", "110", "010"),
        ("001", "011", "111", "101"),
        ("000", "001", "101", "100"),
        ("010", "110", "111", "011"),
        ("000", "010", "011", "001"),
        ("100", "101", "111", "110"),
    ]
    triangles: list[Triangle] = []
    for a, b, c, d in faces:
        triangles.append(Triangle(None, (vertices[a], vertices[b], vertices[c])))
        triangles.append(Triangle(None, (vertices[a], vertices[c], vertices[d])))
    return triangles


def _projected_patch_closure(source_triangles: list[Triangle], target_y: float) -> list[Triangle]:
    generated: list[Triangle] = []
    for triangle in source_triangles:
        projected = tuple(_project_y(vertex, target_y) for vertex in triangle.vertices)
        generated.append(Triangle(None, (projected[2], projected[1], projected[0])))

    for a, b in _boundary_edges(source_triangles):
        pa = _project_y(a, target_y)
        pb = _project_y(b, target_y)
        generated.append(Triangle(None, (a, b, pb)))
        generated.append(Triangle(None, (a, pb, pa)))

    return generated


def _boundary_edges(
    triangles: list[Triangle],
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    counts: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    edges: dict[tuple[tuple[float, float, float], tuple[float, float, float]], tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
    for triangle in triangles:
        points = triangle.vertices
        for a, b in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            key_a = _vertex_key(a)
            key_b = _vertex_key(b)
            key = (key_a, key_b) if key_a <= key_b else (key_b, key_a)
            counts[key] += 1
            edges[key] = (a, b)
    return [edges[key] for key, count in counts.items() if count == 1]


def _boundary_edge_components(
    edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> list[list[int]]:
    vertex_to_edges: defaultdict[tuple[float, float, float], list[int]] = defaultdict(list)
    for edge_index, (a, b) in enumerate(edges):
        vertex_to_edges[_vertex_key(a)].append(edge_index)
        vertex_to_edges[_vertex_key(b)].append(edge_index)

    components: list[list[int]] = []
    seen = [False] * len(edges)
    for edge_index in range(len(edges)):
        if seen[edge_index]:
            continue
        stack = [edge_index]
        seen[edge_index] = True
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for vertex in edges[current]:
                for neighbour in vertex_to_edges[_vertex_key(vertex)]:
                    if not seen[neighbour]:
                        seen[neighbour] = True
                        stack.append(neighbour)
        components.append(component)
    return components


def _vertex_key(vertex: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(round(component, 6) for component in vertex)


def _project_y(vertex: tuple[float, float, float], target_y: float) -> tuple[float, float, float]:
    return (vertex[0], target_y, vertex[2])


def _offset_y(vertex: tuple[float, float, float], offset: float) -> tuple[float, float, float]:
    return (vertex[0], vertex[1] + offset, vertex[2])


def _rotate_z(vertex: tuple[float, float, float], degrees: float) -> tuple[float, float, float]:
    if degrees == 0:
        return vertex
    angle = math.radians(degrees)
    x, y, z = vertex
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (
        (x * cos_a) - (y * sin_a),
        (x * sin_a) + (y * cos_a),
        z,
    )


def _triangle_normal(
    vertices: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
) -> tuple[float, float, float]:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vertices
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = (uy * vz) - (uz * vy)
    ny = (uz * vx) - (ux * vz)
    nz = (ux * vy) - (uy * vx)
    length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def _combined_3mf_model_xml(
    parts: list[MeshPart],
    rotate_z_degrees: float,
    *,
    arrange_on_plate: bool,
) -> bytes:
    model = ET.Element(
        f"{{{CORE_NS}}}model",
        attrib={
            "unit": "millimeter",
            "xml:lang": "en-US",
        },
    )
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", attrib={"name": "Application"}).text = (
        "llm-to-3dprint"
    )
    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    build = ET.SubElement(model, f"{{{CORE_NS}}}build")

    for index, part in enumerate(parts, start=1):
        object_el = ET.SubElement(
            resources,
            f"{{{CORE_NS}}}object",
            attrib={"id": str(index), "type": "model"},
        )
        ET.SubElement(object_el, f"{{{CORE_NS}}}metadata", attrib={"name": "Title"}).text = part.name
        _add_3mf_mesh(object_el, part.triangles, rotate_z_degrees)
        transform = (
            f"1 0 0 0 1 0 0 0 1 {20.0 + ((index - 1) * 70.0):.6f} 128.000000 46.626000"
            if arrange_on_plate
            else "1 0 0 0 1 0 0 0 1 0.000000 0.000000 0.000000"
        )
        ET.SubElement(
            build,
            f"{{{CORE_NS}}}item",
            attrib={
                "objectid": str(index),
                "transform": transform,
                "printable": "1",
            },
        )

    ET.indent(model)
    return ET.tostring(model, encoding="utf-8", xml_declaration=True)


def _add_3mf_mesh(object_el: ET.Element, triangles: list[Triangle], rotate_z_degrees: float) -> None:
    mesh_el = ET.SubElement(object_el, f"{{{CORE_NS}}}mesh")
    vertices_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}vertices")
    triangles_el = ET.SubElement(mesh_el, f"{{{CORE_NS}}}triangles")
    vertex_index: dict[tuple[float, float, float], int] = {}

    def add_vertex(vertex: tuple[float, float, float]) -> int:
        transformed = _rotate_z(vertex, rotate_z_degrees)
        key = tuple(round(component, 6) for component in transformed)
        existing = vertex_index.get(key)
        if existing is not None:
            return existing
        vertex_index[key] = len(vertex_index)
        ET.SubElement(
            vertices_el,
            f"{{{CORE_NS}}}vertex",
            attrib={
                "x": f"{key[0]:.6f}",
                "y": f"{key[1]:.6f}",
                "z": f"{key[2]:.6f}",
            },
        )
        return vertex_index[key]

    for triangle in triangles:
        indices = [add_vertex(vertex) for vertex in triangle.vertices]
        ET.SubElement(
            triangles_el,
            f"{{{CORE_NS}}}triangle",
            attrib={
                "v1": str(indices[0]),
                "v2": str(indices[1]),
                "v3": str(indices[2]),
            },
        )


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


def _relative_to(path: str | None, base: Path) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    try:
        return str(resolved_path.relative_to(base))
    except ValueError:
        return str(resolved_path)

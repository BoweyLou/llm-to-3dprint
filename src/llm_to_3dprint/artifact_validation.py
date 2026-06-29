from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
import struct
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from llm_to_3dprint.bambu import BambuProjectSpec


PRINTER_BUILD_VOLUMES_MM: dict[str, tuple[float, float, float]] = {
    "a1": (256.0, 256.0, 256.0),
    "bambu lab a1": (256.0, 256.0, 256.0),
    "a1 mini": (180.0, 180.0, 180.0),
    "a1mini": (180.0, 180.0, 180.0),
    "bambu lab a1 mini": (180.0, 180.0, 180.0),
    "p1p": (256.0, 256.0, 256.0),
    "p1s": (256.0, 256.0, 256.0),
    "x1c": (256.0, 256.0, 256.0),
    "x1 carbon": (256.0, 256.0, 256.0),
}


@dataclass(slots=True)
class ArtifactIssue:
    code: str
    message: str
    severity: str = "error"
    path: str | None = None


@dataclass(slots=True)
class ArtifactMetrics:
    part_name: str
    source_path: str
    resolved_path: str
    suffix: str
    exists: bool
    size_bytes: int = 0
    metric_source: str = "none"
    facet_count: int | None = None
    bounds: dict[str, float] | None = None
    dimensions: dict[str, float] | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArtifactValidationReport:
    project_name: str
    target_printer: str
    build_volume: tuple[float, float, float] | None
    artifacts: list[ArtifactMetrics] = field(default_factory=list)
    issues: list[ArtifactIssue] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "target_printer": self.target_printer,
            "build_volume": self.build_volume,
            "passes": self.passes,
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
            "issues": [asdict(issue) for issue in self.issues],
        }


def validate_bambu_project_artifacts(
    spec: BambuProjectSpec,
    *,
    base_dir: str | Path = ".",
    require_mesh_metrics: bool = False,
) -> ArtifactValidationReport:
    """Validate handoff artifacts before Bambu export."""

    build_volume = _build_volume_for_printer(spec.target_printer)
    report = ArtifactValidationReport(
        project_name=spec.name,
        target_printer=spec.target_printer,
        build_volume=build_volume,
    )
    if build_volume is None:
        _add_issue(
            report,
            "unknown_printer_build_volume",
            f"No build-volume rule is known for target_printer={spec.target_printer!r}.",
            severity="warning",
        )

    for part in spec.parts:
        metrics = inspect_artifact(part.name, part.path, base_dir=base_dir)
        report.artifacts.append(metrics)
        _validate_artifact_metrics(report, metrics, build_volume, require_mesh_metrics)

    return report


def inspect_artifact(part_name: str, path: str, *, base_dir: str | Path = ".") -> ArtifactMetrics:
    source_path = Path(path)
    resolved_path = source_path if source_path.is_absolute() else Path(base_dir) / source_path
    suffix = resolved_path.suffix.lower()
    if not resolved_path.exists():
        return ArtifactMetrics(
            part_name=part_name,
            source_path=path,
            resolved_path=str(resolved_path),
            suffix=suffix,
            exists=False,
            notes=["Artifact path does not exist."],
        )

    metrics = ArtifactMetrics(
        part_name=part_name,
        source_path=path,
        resolved_path=str(resolved_path),
        suffix=suffix,
        exists=True,
        size_bytes=resolved_path.stat().st_size,
    )
    if metrics.size_bytes == 0:
        metrics.notes.append("Artifact is empty.")
        return metrics

    try:
        if suffix == ".stl":
            vertices, facet_count = _read_stl_vertices(resolved_path)
            _apply_vertex_metrics(metrics, vertices, facet_count, "stl")
        elif suffix == ".obj":
            vertices, facet_count = _read_obj_vertices(resolved_path)
            _apply_vertex_metrics(metrics, vertices, facet_count, "obj")
        elif suffix == ".3mf":
            vertices, facet_count = _read_3mf_vertices(resolved_path)
            _apply_vertex_metrics(metrics, vertices, facet_count, "3mf")
        elif suffix in {".step", ".stp"}:
            metrics.metric_source = "step-header"
            if not _looks_like_step(resolved_path):
                metrics.notes.append("STEP file does not contain an ISO-10303 header marker.")
            metrics.notes.append("STEP bounds require a CAD kernel; only existence and size were checked.")
        else:
            metrics.notes.append("No geometry parser is available for this artifact suffix.")
    except Exception as exc:
        metrics.notes.append(f"Unable to inspect geometry metrics: {exc}")

    return metrics


def format_artifact_validation_report(report: ArtifactValidationReport) -> str:
    status = "PASS" if report.passes else "FAIL"
    volume = (
        "unknown"
        if report.build_volume is None
        else " x ".join(f"{value:g}" for value in report.build_volume)
    )
    lines = [
        f"{status} {report.project_name}: artifacts={len(report.artifacts)}, build_volume={volume} mm"
    ]
    for artifact in report.artifacts:
        dims = artifact.dimensions or {}
        if dims:
            dim_text = (
                f"{dims['x']:.2f} x {dims['y']:.2f} x {dims['z']:.2f} mm"
            )
        else:
            dim_text = "bounds unavailable"
        lines.append(
            f"- {artifact.part_name}: {artifact.suffix or 'no suffix'}, "
            f"{dim_text}, facets={artifact.facet_count if artifact.facet_count is not None else 'unknown'}"
        )
        for note in artifact.notes:
            lines.append(f"  note: {note}")
    for issue in report.issues:
        prefix = "warning" if issue.severity == "warning" else "error"
        path = f" ({issue.path})" if issue.path else ""
        lines.append(f"- {prefix}:{issue.code}{path}: {issue.message}")
    return "\n".join(lines)


def _validate_artifact_metrics(
    report: ArtifactValidationReport,
    metrics: ArtifactMetrics,
    build_volume: tuple[float, float, float] | None,
    require_mesh_metrics: bool,
) -> None:
    if not metrics.exists:
        _add_issue(report, "missing_artifact", "Referenced artifact does not exist.", path=metrics.source_path)
        return
    if metrics.size_bytes <= 0:
        _add_issue(report, "empty_artifact", "Referenced artifact is empty.", path=metrics.source_path)
    if metrics.suffix in {".stl", ".obj", ".3mf"} and metrics.facet_count == 0:
        _add_issue(report, "empty_mesh", "Mesh artifact contains no facets.", path=metrics.source_path)
    if require_mesh_metrics and metrics.dimensions is None:
        _add_issue(
            report,
            "missing_geometry_metrics",
            "Geometry metrics were required but could not be computed for this artifact.",
            path=metrics.source_path,
        )
    if build_volume is not None and metrics.dimensions is not None:
        over = [
            axis
            for axis, limit in zip(("x", "y", "z"), build_volume)
            if metrics.dimensions[axis] > limit
        ]
        if over:
            _add_issue(
                report,
                "artifact_exceeds_build_volume",
                (
                    f"Artifact dimensions {metrics.dimensions['x']:.2f} x "
                    f"{metrics.dimensions['y']:.2f} x {metrics.dimensions['z']:.2f} mm "
                    f"exceed the {report.target_printer} build volume on axis {', '.join(over)}."
                ),
                path=metrics.source_path,
            )


def _read_stl_vertices(path: Path) -> tuple[list[tuple[float, float, float]], int]:
    data = path.read_bytes()
    if len(data) >= 84:
        triangle_count = struct.unpack("<I", data[80:84])[0]
        expected_length = 84 + triangle_count * 50
        if expected_length == len(data):
            vertices: list[tuple[float, float, float]] = []
            offset = 84
            for _ in range(triangle_count):
                values = struct.unpack("<12fH", data[offset : offset + 50])
                vertices.extend(
                    [
                        (values[3], values[4], values[5]),
                        (values[6], values[7], values[8]),
                        (values[9], values[10], values[11]),
                    ]
                )
                offset += 50
            return vertices, triangle_count

    vertices = []
    for line in data.decode("utf-8", errors="ignore").splitlines():
        bits = line.strip().split()
        if len(bits) == 4 and bits[0].lower() == "vertex":
            vertices.append((float(bits[1]), float(bits[2]), float(bits[3])))
    return vertices, len(vertices) // 3


def _read_obj_vertices(path: Path) -> tuple[list[tuple[float, float, float]], int]:
    vertices: list[tuple[float, float, float]] = []
    facet_count = 0
    for line in path.read_text(errors="ignore").splitlines():
        bits = line.strip().split()
        if not bits:
            continue
        if bits[0] == "v" and len(bits) >= 4:
            vertices.append((float(bits[1]), float(bits[2]), float(bits[3])))
        elif bits[0] == "f":
            facet_count += max(1, len(bits) - 3)
    return vertices, facet_count


def _read_3mf_vertices(path: Path) -> tuple[list[tuple[float, float, float]], int]:
    vertices: list[tuple[float, float, float]] = []
    facet_count = 0
    with zipfile.ZipFile(path) as archive:
        members = [
            name
            for name in archive.namelist()
            if name.startswith("3D/") and name.endswith(".model")
        ]
        for member in members:
            root = ET.fromstring(archive.read(member))
            for element in root.iter():
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
                    facet_count += 1
    return vertices, facet_count


def _apply_vertex_metrics(
    metrics: ArtifactMetrics,
    vertices: list[tuple[float, float, float]],
    facet_count: int,
    metric_source: str,
) -> None:
    metrics.metric_source = metric_source
    metrics.facet_count = facet_count
    if not vertices:
        return
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    bounds = {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "min_z": min(zs),
        "max_z": max(zs),
    }
    metrics.bounds = {key: round(value, 4) for key, value in bounds.items()}
    metrics.dimensions = {
        "x": round(math.dist((bounds["min_x"],), (bounds["max_x"],)), 4),
        "y": round(math.dist((bounds["min_y"],), (bounds["max_y"],)), 4),
        "z": round(math.dist((bounds["min_z"],), (bounds["max_z"],)), 4),
    }


def _looks_like_step(path: Path) -> bool:
    return "ISO-10303" in path.read_text(errors="ignore")[:2048]


def _build_volume_for_printer(target_printer: str) -> tuple[float, float, float] | None:
    return PRINTER_BUILD_VOLUMES_MM.get(target_printer.strip().lower())


def _add_issue(
    report: ArtifactValidationReport,
    code: str,
    message: str,
    *,
    severity: str = "error",
    path: str | None = None,
) -> None:
    report.issues.append(ArtifactIssue(code=code, message=message, severity=severity, path=path))

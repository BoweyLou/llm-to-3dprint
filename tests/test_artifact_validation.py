from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_to_3dprint.artifact_validation import (
    format_artifact_validation_report,
    validate_bambu_project_artifacts,
)
from llm_to_3dprint.bambu import BambuProjectSpec
from llm_to_3dprint.cli import main as cli_main


def write_ascii_stl(path: Path, *, width: float = 10.0, depth: float = 10.0, height: float = 1.0) -> Path:
    path.write_text(
        "\n".join(
            [
                "solid test",
                "  facet normal 0 0 1",
                "    outer loop",
                "      vertex 0 0 0",
                f"      vertex {width} 0 0",
                f"      vertex 0 {depth} {height}",
                "    endloop",
                "  endfacet",
                "endsolid test",
                "",
            ]
        )
    )
    return path


def project_payload(part_path: str) -> dict:
    return {
        "name": "artifact_check_project",
        "description": "Project for artifact validation.",
        "target_printer": "A1",
        "nozzle_diameter": 0.4,
        "ams": "none",
        "filament_count": 1,
        "export_backend": "clean_room_3mf",
        "output_3mf": "generated/output/artifact_check.3mf",
        "parts": [
            {
                "name": "body",
                "path": part_path,
                "load_strategy": "separate_object",
                "print_mode": "standalone",
                "plate": 1,
                "filament": 1,
            }
        ],
    }


def test_validate_bambu_project_artifacts_passes_for_mesh_inside_bed(tmp_path: Path) -> None:
    stl = write_ascii_stl(tmp_path / "body.stl")
    spec = BambuProjectSpec.from_dict(project_payload(str(stl)))

    report = validate_bambu_project_artifacts(spec)

    assert report.passes is True
    assert report.artifacts[0].facet_count == 1
    assert report.artifacts[0].dimensions == {"x": 10.0, "y": 10.0, "z": 1.0}
    assert format_artifact_validation_report(report).startswith("PASS artifact_check_project")


def test_validate_bambu_project_artifacts_fails_missing_path(tmp_path: Path) -> None:
    spec = BambuProjectSpec.from_dict(project_payload(str(tmp_path / "missing.stl")))

    report = validate_bambu_project_artifacts(spec)

    assert report.passes is False
    assert [issue.code for issue in report.issues] == ["missing_artifact"]


def test_validate_bambu_project_artifacts_fails_oversized_mesh(tmp_path: Path) -> None:
    stl = write_ascii_stl(tmp_path / "body.stl", width=300.0)
    spec = BambuProjectSpec.from_dict(project_payload(str(stl)))

    report = validate_bambu_project_artifacts(spec)

    assert report.passes is False
    assert "artifact_exceeds_build_volume" in [issue.code for issue in report.issues]


def test_cli_validate_artifacts_exits_nonzero_for_missing_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    project.write_text(json.dumps(project_payload(str(tmp_path / "missing.stl"))) + "\n")

    output = io.StringIO()
    with patch.object(sys, "argv", ["llm-to-3dprint", "validate-artifacts", str(project)]):
        with redirect_stdout(output):
            with pytest.raises(SystemExit) as raised:
                cli_main()

    assert raised.value.code == 1
    assert "missing_artifact" in output.getvalue()

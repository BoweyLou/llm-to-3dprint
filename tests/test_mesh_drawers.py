from __future__ import annotations

import json
from pathlib import Path

from llm_to_3dprint.brief import DesignBrief
from llm_to_3dprint.mesh_drawers import (
    SourceMesh,
    Triangle,
    audit_mesh_health,
    build_manifest,
    format_mesh_manifest_validation,
    partition_drawer_mesh,
    validate_mesh_manifest,
)


def mesh_drawer_brief() -> DesignBrief:
    return DesignBrief.from_dict(
        {
            "name": "desk_organiser_mesh_preserved_drawers",
            "description": "Mesh-preserved desk organiser with functional drawers.",
            "object_type": "mesh_preserved_drawer_organiser",
            "library": "mesh",
            "units": "mm",
            "base_shape": "rectangular",
            "internal_dimensions": {"length": 10.0, "width": 10.0, "height": 10.0},
            "wall_thickness": 2.2,
            "mesh_preservation": {
                "source_3mf": "/tmp/source.3mf",
                "mesh_reuse_policy": "partition_visible_mesh",
            },
            "drawer_stack": {
                "drawer_count": 1,
                "clearance": 0.5,
                "min_clearance": 0.4,
                "max_clearance": 0.6,
                "drawer_wall_thickness": 0.2,
                "body_wall_thickness": 0.2,
                "drawer_depth": 4.0,
                "patch_masks": [
                    {
                        "name": "drawer_1_front",
                        "x_min": 0.0,
                        "x_max": 2.0,
                        "y_min": 0.0,
                        "y_max": 2.0,
                        "z_min": 0.0,
                        "z_max": 2.0,
                    }
                ],
            },
        }
    )


def source_mesh() -> SourceMesh:
    return SourceMesh(
        source_path=Path("/tmp/source.3mf"),
        model_member="3D/Objects/object_1.model",
        source_sha256="abc123",
        vertices=[
            (0.0, 1.0, 0.0),
            (0.0, 1.0, 1.0),
            (1.0, 1.0, 0.0),
            (5.0, 5.0, 5.0),
            (6.0, 5.0, 5.0),
            (5.0, 6.0, 5.0),
        ],
        triangles=[
            (0, 1, 2),
            (3, 4, 5),
        ],
    )


def test_partition_assigns_each_source_triangle_once() -> None:
    brief = mesh_drawer_brief()
    mesh = source_mesh()

    parts = partition_drawer_mesh(mesh, brief)
    manifest = build_manifest(
        brief,
        mesh,
        parts,
        Path("/tmp/out"),
        Path("/tmp/out/combined.3mf"),
        Path("/tmp/out/assembled_preview.3mf"),
        Path("/tmp/out/front_review.3mf"),
        Path("/tmp/out/source_skin_preview.3mf"),
        Path("/tmp/out/functional.3mf"),
        Path("/tmp/out/bambu.json"),
    )

    assert manifest["triangle_accounting"]["passes"] is True
    assert manifest["geometry_health"]["passes"] is True
    assert manifest["outputs"]["mesh_preserved_print_3mf"] == "/tmp/out/combined.3mf"
    assert manifest["outputs"]["assembled_preview_3mf"] == "/tmp/out/assembled_preview.3mf"
    assert manifest["outputs"]["front_review_3mf"] == "/tmp/out/front_review.3mf"
    assert manifest["outputs"]["source_skin_preview_3mf"] == "/tmp/out/source_skin_preview.3mf"
    assert manifest["artifact_roles"]["source_skin_preview_3mf"]["source_facet_count"] == 2
    assert manifest["functional_clearance_checks"]["passes"] is True
    assert manifest["functional_clearance_checks"]["drawers"][0]["clearances"]["left"] == 0.5
    assert manifest["parts"][0]["name"].endswith("body_preserved_mesh")
    assert manifest["parts"][0]["source_triangle_ids"] == [1]
    assert manifest["parts"][1]["source_triangle_ids"] == [0]
    assert manifest["parts"][1]["generated_triangle_count"] > 0
    assert manifest["parts"][1]["skin_shell_triangle_count"] > 0
    assert manifest["parts"][1]["functional_triangle_count"] > 0
    assert manifest["parts"][1]["mesh_preserved_output_health"]["manifold"] is True


def test_front_visible_partition_excludes_recessed_triangles() -> None:
    brief = DesignBrief.from_dict(
        {
            **mesh_drawer_brief().to_dict(),
            "drawer_stack": {
                **mesh_drawer_brief().to_dict()["drawer_stack"],
                "front_visibility_depth": 1.0,
                "local_visibility_depth": 0.5,
                "patch_masks": [
                    {
                        "name": "drawer_1_front",
                        "x_min": 0.0,
                        "x_max": 2.0,
                        "y_min": 0.0,
                        "y_max": 2.0,
                        "z_min": 0.0,
                        "z_max": 2.0,
                    }
                ],
            },
        }
    )
    mesh = SourceMesh(
        source_path=Path("/tmp/source.3mf"),
        model_member="3D/Objects/object_1.model",
        source_sha256="abc123",
        vertices=[
            (0.0, 1.8, 0.0),
            (0.0, 1.8, 0.6),
            (0.6, 1.8, 0.0),
            (0.0, 0.2, 0.0),
            (0.0, 0.2, 0.6),
            (0.6, 0.2, 0.0),
            (5.0, 5.0, 5.0),
            (6.0, 5.0, 5.0),
            (5.0, 6.0, 5.0),
        ],
        triangles=[
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
        ],
    )

    parts = partition_drawer_mesh(mesh, brief)

    assert parts[0].source_triangle_ids == [1, 2]
    assert parts[1].source_triangle_ids == [0]


def test_front_visible_partition_rejects_side_normal_artifacts() -> None:
    brief = DesignBrief.from_dict(
        {
            **mesh_drawer_brief().to_dict(),
            "drawer_stack": {
                **mesh_drawer_brief().to_dict()["drawer_stack"],
                "front_normal_min_y": 0.25,
                "patch_masks": [
                    {
                        "name": "drawer_1_front",
                        "x_min": 0.0,
                        "x_max": 2.0,
                        "y_min": 0.0,
                        "y_max": 2.0,
                        "z_min": 0.0,
                        "z_max": 2.0,
                    }
                ],
            },
        }
    )
    mesh = SourceMesh(
        source_path=Path("/tmp/source.3mf"),
        model_member="3D/Objects/object_1.model",
        source_sha256="abc123",
        vertices=[
            (0.0, 1.8, 0.0),
            (0.0, 1.8, 0.8),
            (0.8, 1.8, 0.0),
            (0.0, 1.8, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 1.8, 0.8),
            (5.0, 5.0, 5.0),
            (6.0, 5.0, 5.0),
            (5.0, 6.0, 5.0),
        ],
        triangles=[
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
        ],
    )

    parts = partition_drawer_mesh(mesh, brief)

    assert parts[0].source_triangle_ids == [1, 2]
    assert parts[1].source_triangle_ids == [0]


def test_drawer_functional_core_is_manifold() -> None:
    brief = mesh_drawer_brief()
    mesh = source_mesh()

    parts = partition_drawer_mesh(mesh, brief)
    drawer = parts[1]

    assert audit_mesh_health(drawer.generated_triangles)["manifold"] is True


def test_preserved_source_skin_shell_closes_final_drawer_part() -> None:
    brief = mesh_drawer_brief()
    mesh = source_mesh()

    parts = partition_drawer_mesh(mesh, brief)
    drawer = parts[1]

    assert drawer.source_triangle_count == 1
    assert drawer.skin_shell_triangle_count > 0
    assert drawer.functional_triangle_count > 0
    assert audit_mesh_health(drawer.triangles)["manifold"] is True
    assert audit_mesh_health(drawer.triangles)["slicer_manifold"] is True


def test_validate_mesh_manifest_reports_duplicate_or_missing_source_ids(tmp_path: Path) -> None:
    manifest = {
        "source": {"source_facet_count": 3},
        "parts": [
            {"source_triangle_ids": [0, 1]},
            {"source_triangle_ids": [1]},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest) + "\n")

    result = validate_mesh_manifest(manifest_path)

    assert result["passes"] is False
    assert result["duplicate_source_triangle_count"] == 1
    assert result["unassigned_source_triangle_count"] == 1
    assert format_mesh_manifest_validation(result).startswith("FAIL mesh manifest")


def test_mesh_health_detects_open_and_closed_meshes() -> None:
    open_health = audit_mesh_health(
        [Triangle(None, ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))]
    )
    closed_health = audit_mesh_health(
        [
            Triangle(None, ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))),
            Triangle(None, ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))),
            Triangle(None, ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))),
            Triangle(None, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))),
        ]
    )

    assert open_health["manifold"] is False
    assert open_health["slicer_manifold"] is False
    assert open_health["open_edge_count"] == 3
    assert closed_health["manifold"] is True
    assert closed_health["slicer_manifold"] is True
    assert closed_health["open_edge_count"] == 0
    assert closed_health["nonmanifold_edge_count"] == 0


def test_validate_mesh_manifest_fails_nonmanifold_geometry(tmp_path: Path) -> None:
    manifest = {
        "source": {"source_facet_count": 1},
        "parts": [{"source_triangle_ids": [0]}],
        "geometry_health": {
            "passes": False,
            "nonmanifold_part_count": 1,
            "open_edge_count": 3,
            "nonmanifold_edge_count": 0,
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest) + "\n")

    result = validate_mesh_manifest(manifest_path)

    assert result["passes"] is False
    assert result["source_accounting_passes"] is True
    assert result["geometry_passes"] is False
    assert result["open_edge_count"] == 3

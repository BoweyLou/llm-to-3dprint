from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from llm_to_3dprint.bambu import BambuProjectSpec


CANONICAL_VIEWS: tuple[dict[str, Any], ...] = (
    {"name": "front", "camera_location": (0.0, -240.0, 90.0), "rotation_degrees": (65.0, 0.0, 0.0)},
    {"name": "right", "camera_location": (240.0, 0.0, 90.0), "rotation_degrees": (65.0, 0.0, 90.0)},
    {"name": "top", "camera_location": (0.0, 0.0, 260.0), "rotation_degrees": (0.0, 0.0, 0.0)},
    {"name": "isometric", "camera_location": (180.0, -220.0, 160.0), "rotation_degrees": (60.0, 0.0, 38.0)},
)


@dataclass(slots=True)
class BlenderReviewArtifact:
    name: str
    path: str
    role: str
    import_supported: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BlenderReviewPlan:
    project_name: str
    output_dir: str
    script_path: str
    report_path: str
    plan_path: str
    artifacts: list[BlenderReviewArtifact]
    views: list[dict[str, Any]]
    blender_executable: str | None
    command: list[str] | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "output_dir": self.output_dir,
            "script_path": self.script_path,
            "report_path": self.report_path,
            "plan_path": self.plan_path,
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
            "views": self.views,
            "blender_executable": self.blender_executable,
            "command": self.command,
            "notes": self.notes,
        }


@dataclass(slots=True)
class BlenderReviewRunResult:
    command: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    rendered_images: list[str]
    error_text: str | None = None

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.error_text is None


def write_blender_review_plan(
    spec: BambuProjectSpec,
    output_dir: str | Path,
    *,
    base_dir: str | Path = ".",
    blender_executable: str | None = None,
) -> BlenderReviewPlan:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = _review_artifacts(spec, base_dir=base_dir)
    script_path = output / f"{spec.name}_blender_review.py"
    report_path = output / f"{spec.name}_blender_review.md"
    plan_path = output / f"{spec.name}_blender_review.json"
    executable = blender_executable or shutil.which("blender")
    command = [executable, "--background", "--python", str(script_path)] if executable else None
    notes = [
        "Blender is optional review tooling. CAD source and design contracts remain authoritative.",
        "STEP and 3MF import support depends on Blender add-ons; STL and OBJ are imported by the generated script.",
    ]
    if executable is None:
        notes.append("No blender executable was found on PATH; render the generated script later from Blender.")

    plan = BlenderReviewPlan(
        project_name=spec.name,
        output_dir=str(output),
        script_path=str(script_path),
        report_path=str(report_path),
        plan_path=str(plan_path),
        artifacts=artifacts,
        views=[dict(view) for view in CANONICAL_VIEWS],
        blender_executable=executable,
        command=command,
        notes=notes,
    )
    script_path.write_text(_render_blender_script(plan))
    report_path.write_text(format_blender_review_plan(plan) + "\n")
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2) + "\n")
    return plan


def run_blender_review(plan: BlenderReviewPlan) -> BlenderReviewRunResult:
    if not plan.command:
        return BlenderReviewRunResult(
            command=[],
            returncode=None,
            stdout="",
            stderr="",
            rendered_images=[],
            error_text="No blender executable is configured.",
        )
    completed = subprocess.run(plan.command, capture_output=True, text=True, check=False)
    rendered = [
        str(Path(plan.output_dir) / f"{view['name']}.png")
        for view in plan.views
        if (Path(plan.output_dir) / f"{view['name']}.png").exists()
    ]
    return BlenderReviewRunResult(
        command=plan.command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        rendered_images=rendered,
        error_text=None if completed.returncode == 0 else "Blender render command failed.",
    )


def format_blender_review_plan(plan: BlenderReviewPlan) -> str:
    lines = [
        f"# Blender Review: {plan.project_name}",
        "",
        "## Artifacts",
        "",
    ]
    for artifact in plan.artifacts:
        support = "import" if artifact.import_supported else "manual/add-on"
        lines.append(f"- `{artifact.path}` ({artifact.role}, {support})")
        for note in artifact.notes:
            lines.append(f"  - {note}")
    lines.extend(["", "## Views", ""])
    for view in plan.views:
        lines.append(f"- {view['name']}: `{Path(plan.output_dir) / (view['name'] + '.png')}`")
    lines.extend(["", "## Command", ""])
    if plan.command:
        lines.append("```bash")
        lines.append(" ".join(plan.command))
        lines.append("```")
    else:
        lines.append("Open Blender and run the generated Python script manually:")
        lines.append("")
        lines.append(f"`{plan.script_path}`")
    if plan.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in plan.notes)
    return "\n".join(lines)


def _review_artifacts(spec: BambuProjectSpec, *, base_dir: str | Path) -> list[BlenderReviewArtifact]:
    base = Path(base_dir)
    artifacts: list[BlenderReviewArtifact] = []
    for part in spec.parts:
        path = Path(part.path)
        resolved = path if path.is_absolute() else base / path
        suffix = resolved.suffix.lower()
        supported = suffix in {".stl", ".obj"}
        notes = []
        if suffix in {".step", ".stp"}:
            notes.append("STEP should be reviewed in CAD Explorer or imported through a Blender CAD add-on.")
        elif suffix == ".3mf":
            notes.append("3MF should be reviewed in Bambu Studio unless a Blender 3MF importer is installed.")
        elif not supported:
            notes.append("The generated script does not have a native importer for this suffix.")
        artifacts.append(
            BlenderReviewArtifact(
                name=part.name,
                path=str(resolved),
                role=f"plate {part.plate} / filament {part.filament}",
                import_supported=supported,
                notes=notes,
            )
        )
    return artifacts


def _render_blender_script(plan: BlenderReviewPlan) -> str:
    artifacts_json = json.dumps([asdict(artifact) for artifact in plan.artifacts], indent=2)
    views_json = json.dumps(plan.views, indent=2)
    output_json = json.dumps(plan.output_dir)
    return f"""from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

ARTIFACTS = json.loads({artifacts_json!r})
VIEWS = json.loads({views_json!r})
OUTPUT_DIR = Path(json.loads({output_json!r}))


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_supported_artifacts():
    imported = []
    for artifact in ARTIFACTS:
        if not artifact["import_supported"]:
            print(f"Skipping unsupported Blender import: {{artifact['path']}}")
            continue
        path = Path(artifact["path"])
        if not path.exists():
            print(f"Skipping missing artifact: {{path}}")
            continue
        suffix = path.suffix.lower()
        if suffix == ".stl":
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=str(path))
            else:
                bpy.ops.import_mesh.stl(filepath=str(path))
        elif suffix == ".obj":
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(filepath=str(path))
            else:
                bpy.ops.import_scene.obj(filepath=str(path))
        imported.extend(bpy.context.selected_objects)
    return imported


def add_camera(view):
    bpy.ops.object.camera_add(location=view["camera_location"])
    camera = bpy.context.object
    rotation = [math.radians(value) for value in view["rotation_degrees"]]
    camera.rotation_euler = rotation
    bpy.context.scene.camera = camera
    return camera


def add_light():
    bpy.ops.object.light_add(type="AREA", location=(0, -160, 180))
    light = bpy.context.object
    light.data.energy = 600
    light.data.size = 120


def render_views():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.resolution_x = 1600
    bpy.context.scene.render.resolution_y = 1200
    for view in VIEWS:
        add_camera(view)
        bpy.context.scene.render.filepath = str(OUTPUT_DIR / f"{{view['name']}}.png")
        bpy.ops.render.render(write_still=True)


clear_scene()
objects = import_supported_artifacts()
add_light()
if objects:
    render_views()
else:
    print("No supported artifacts were imported; no screenshots rendered.")
"""

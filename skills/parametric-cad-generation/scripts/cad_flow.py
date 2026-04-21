#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

SUPPORTED_LIBRARIES = {"cadquery", "build123d"}
SUPPORTED_FACES = {"front", "back", "left", "right", "top", "bottom"}
SUPPORTED_SHAPES = {"rectangular", "circular"}


@dataclass(slots=True)
class Dimensions:
    length: float
    width: float
    height: float

    def validate(self) -> None:
        for label, value in (
            ("length", self.length),
            ("width", self.width),
            ("height", self.height),
        ):
            if value <= 0:
                raise ValueError(f"internal_dimensions.{label} must be > 0, got {value!r}")


@dataclass(slots=True)
class Cutout:
    name: str
    face: str
    shape: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    width: float | None = None
    height: float | None = None
    diameter: float | None = None
    depth: float | None = None
    notes: str = ""

    def validate(self) -> None:
        if not self.name:
            raise ValueError("cutout.name must not be empty")
        if self.face not in SUPPORTED_FACES:
            raise ValueError(f"cutout.face must be one of {sorted(SUPPORTED_FACES)}, got {self.face!r}")
        if self.shape not in SUPPORTED_SHAPES:
            raise ValueError(
                f"cutout.shape must be one of {sorted(SUPPORTED_SHAPES)}, got {self.shape!r}"
            )
        if self.depth is not None and self.depth <= 0:
            raise ValueError(f"cutout.depth must be > 0, got {self.depth!r}")
        if self.shape == "rectangular":
            if not self.width or self.width <= 0:
                raise ValueError("rectangular cutouts require width > 0")
            if not self.height or self.height <= 0:
                raise ValueError("rectangular cutouts require height > 0")
        if self.shape == "circular":
            if not self.diameter or self.diameter <= 0:
                raise ValueError("circular cutouts require diameter > 0")


@dataclass(slots=True)
class MountingHole:
    name: str
    x: float
    y: float
    diameter: float
    depth: float | None = None

    def validate(self) -> None:
        if not self.name:
            raise ValueError("mounting_hole.name must not be empty")
        if self.diameter <= 0:
            raise ValueError(f"mounting_hole.diameter must be > 0, got {self.diameter!r}")
        if self.depth is not None and self.depth <= 0:
            raise ValueError(f"mounting_hole.depth must be > 0, got {self.depth!r}")


@dataclass(slots=True)
class DesignBrief:
    name: str
    description: str
    object_type: str
    library: str
    units: str
    base_shape: str
    internal_dimensions: Dimensions
    wall_thickness: float
    base_thickness: float | None = None
    fillet_radius: float = 0.0
    lid_style: str = "open_top"
    requirements: list[str] = field(default_factory=list)
    cutouts: list[Cutout] = field(default_factory=list)
    mounting_holes: list[MountingHole] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def resolved_base_thickness(self) -> float:
        return self.base_thickness if self.base_thickness is not None else self.wall_thickness

    @property
    def outer_length(self) -> float:
        return self.internal_dimensions.length + (2 * self.wall_thickness)

    @property
    def outer_width(self) -> float:
        return self.internal_dimensions.width + (2 * self.wall_thickness)

    @property
    def outer_height(self) -> float:
        return self.internal_dimensions.height + self.resolved_base_thickness

    def validate(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.description:
            raise ValueError("description must not be empty")
        if self.library not in SUPPORTED_LIBRARIES:
            raise ValueError(f"library must be one of {sorted(SUPPORTED_LIBRARIES)}, got {self.library!r}")
        if self.wall_thickness <= 0:
            raise ValueError(f"wall_thickness must be > 0, got {self.wall_thickness!r}")
        if self.resolved_base_thickness <= 0:
            raise ValueError(f"base_thickness must be > 0, got {self.resolved_base_thickness!r}")
        if self.fillet_radius < 0:
            raise ValueError(f"fillet_radius must be >= 0, got {self.fillet_radius!r}")

        self.internal_dimensions.validate()

        if self.fillet_radius * 2 >= min(self.outer_length, self.outer_width):
            raise ValueError("fillet_radius is too large for the computed outer footprint")

        x_limit = self.outer_length / 2
        y_limit = self.outer_width / 2

        for cutout in self.cutouts:
            cutout.validate()
            if cutout.face in {"front", "back", "left", "right"} and not (0 <= cutout.z <= self.outer_height):
                raise ValueError(f"cutout {cutout.name!r} z must stay within 0..{self.outer_height}")
            if cutout.face in {"top", "bottom"}:
                if not (-x_limit <= cutout.x <= x_limit):
                    raise ValueError(f"cutout {cutout.name!r} x exceeds top/bottom face limits")
                if not (-y_limit <= cutout.y <= y_limit):
                    raise ValueError(f"cutout {cutout.name!r} y exceeds top/bottom face limits")

        for hole in self.mounting_holes:
            hole.validate()
            if not (-x_limit <= hole.x <= x_limit):
                raise ValueError(f"mounting hole {hole.name!r} x exceeds the outer footprint")
            if not (-y_limit <= hole.y <= y_limit):
                raise ValueError(f"mounting hole {hole.name!r} y exceeds the outer footprint")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DesignBrief":
        brief = cls(
            name=payload["name"],
            description=payload["description"],
            object_type=payload["object_type"],
            library=payload.get("library", "cadquery"),
            units=payload.get("units", "mm"),
            base_shape=payload.get("base_shape", "rectangular"),
            internal_dimensions=Dimensions(**payload["internal_dimensions"]),
            wall_thickness=payload["wall_thickness"],
            base_thickness=payload.get("base_thickness"),
            fillet_radius=payload.get("fillet_radius", 0.0),
            lid_style=payload.get("lid_style", "open_top"),
            requirements=payload.get("requirements", []),
            cutouts=[Cutout(**item) for item in payload.get("cutouts", [])],
            mounting_holes=[MountingHole(**item) for item in payload.get("mounting_holes", [])],
            notes=payload.get("notes", []),
        )
        brief.validate()
        return brief

    @classmethod
    def load(cls, path: str | Path) -> "DesignBrief":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")


def preset_rectangular_enclosure() -> DesignBrief:
    return DesignBrief.from_dict(
        {
            "name": "rectangular_enclosure_demo",
            "description": "Open-top electronics enclosure with a front display cutout and four base mounting holes.",
            "object_type": "enclosure",
            "library": "cadquery",
            "units": "mm",
            "base_shape": "rectangular",
            "internal_dimensions": {"length": 80.0, "width": 50.0, "height": 25.0},
            "wall_thickness": 2.0,
            "base_thickness": 2.5,
            "fillet_radius": 2.0,
            "lid_style": "open_top",
            "requirements": [
                "Keep the interior footprint clear for a PCB and wiring.",
                "Avoid support-heavy geometry in a typical FDM print orientation.",
                "Use relative references wherever practical.",
            ],
            "cutouts": [
                {
                    "name": "front_display",
                    "face": "front",
                    "shape": "rectangular",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 14.0,
                    "width": 40.0,
                    "height": 20.0,
                    "depth": 4.0,
                    "notes": "Centered display or label window.",
                },
                {
                    "name": "side_cable",
                    "face": "right",
                    "shape": "circular",
                    "x": 0.0,
                    "y": 0.0,
                    "z": 9.0,
                    "diameter": 8.0,
                    "depth": 4.0,
                    "notes": "Cable pass-through on the right wall.",
                },
            ],
            "mounting_holes": [
                {"name": "front_left", "x": -28.0, "y": 16.0, "diameter": 3.2, "depth": 3.0},
                {"name": "front_right", "x": 28.0, "y": 16.0, "diameter": 3.2, "depth": 3.0},
                {"name": "rear_left", "x": -28.0, "y": -16.0, "diameter": 3.2, "depth": 3.0},
                {"name": "rear_right", "x": 28.0, "y": -16.0, "diameter": 3.2, "depth": 3.0},
            ],
            "notes": [
                "Origin is centered in X and Y, with Z measured upward from the bottom face."
            ],
        }
    )


def build_generation_prompt(brief: DesignBrief) -> str:
    cutout_lines: list[str] = []
    for cutout in brief.cutouts:
        size_bits: list[str] = []
        if cutout.width is not None:
            size_bits.append(f"width={cutout.width}")
        if cutout.height is not None:
            size_bits.append(f"height={cutout.height}")
        if cutout.diameter is not None:
            size_bits.append(f"diameter={cutout.diameter}")
        if cutout.depth is not None:
            size_bits.append(f"depth={cutout.depth}")
        cutout_lines.append(
            f"- {cutout.name}: face={cutout.face}, shape={cutout.shape}, "
            f"x={cutout.x}, y={cutout.y}, z={cutout.z}, " + ", ".join(size_bits)
        )

    hole_lines = [
        f"- {hole.name}: x={hole.x}, y={hole.y}, diameter={hole.diameter}, depth={hole.depth or brief.resolved_base_thickness}"
        for hole in brief.mounting_holes
    ]

    cutout_block = "\n".join(cutout_lines) if cutout_lines else "- No cutouts requested."
    hole_block = "\n".join(hole_lines) if hole_lines else "- No mounting holes requested."
    requirement_block = "\n".join(f"- {item}" for item in brief.requirements) or "- No extra requirements provided."
    note_block = "\n".join(f"- {item}" for item in brief.notes) or "- No extra notes provided."

    return f"""You are generating a Python CAD script.

Target library: {brief.library}
Object name: {brief.name}
Object type: {brief.object_type}
Units: {brief.units}
Base shape: {brief.base_shape}

Description:
{brief.description}

Core dimensions:
- internal length: {brief.internal_dimensions.length}
- internal width: {brief.internal_dimensions.width}
- internal height: {brief.internal_dimensions.height}
- wall thickness: {brief.wall_thickness}
- base thickness: {brief.resolved_base_thickness}
- fillet radius: {brief.fillet_radius}
- lid style: {brief.lid_style}

Cutouts:
{cutout_block}

Mounting holes:
{hole_block}

Requirements:
{requirement_block}

Notes:
{note_block}

Coordinate conventions:
- origin is centered in X and Y
- Z=0 is the bottom face
- X spans the part length
- Y spans the part width
- cutout coordinates describe the feature center

Generate a complete Python script that:
1. Defines every critical dimension as a named parameter near the top of the file.
2. Uses relative references and reusable helper functions where practical.
3. Builds the final solid in {brief.library}.
4. Exports both STL and STEP files.
5. Includes brief comments explaining parameter groups and coordinate assumptions.
6. Avoids brittle absolute magic numbers.

If geometry is ambiguous, choose conservative printable defaults and state them in code comments.
"""


def render_script(brief: DesignBrief) -> str:
    if brief.library != "cadquery":
        raise ValueError(
            f"Only cadquery rendering is implemented today, got {brief.library!r}. "
            "Use the prompt generator for build123d briefs."
        )
    if brief.base_shape != "rectangular":
        raise ValueError(
            f"Only rectangular base shapes are implemented today, got {brief.base_shape!r}."
        )

    cutouts_json = json.dumps([asdict(cutout) for cutout in brief.cutouts], indent=4)
    holes_json = json.dumps([asdict(hole) for hole in brief.mounting_holes], indent=4)

    return f'''"""Generated from a structured design brief.

Part: {brief.name}
Description: {brief.description}
Units: {brief.units}

Coordinate conventions:
- X is centered across the part length.
- Y is centered across the part width.
- Z=0 is the bottom face.
- Face cutouts use X/Y/Z values in world coordinates.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq


PART_NAME = "{brief.name}"
INNER_LENGTH = {brief.internal_dimensions.length}
INNER_WIDTH = {brief.internal_dimensions.width}
INNER_HEIGHT = {brief.internal_dimensions.height}
WALL_THICKNESS = {brief.wall_thickness}
BASE_THICKNESS = {brief.resolved_base_thickness}
FILLET_RADIUS = {brief.fillet_radius}
DEFAULT_CUT_DEPTH = max(WALL_THICKNESS, BASE_THICKNESS) + 1.0
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

CUTOUTS = {cutouts_json}
MOUNTING_HOLES = {holes_json}


def build_enclosure() -> cq.Workplane:
    outer_length = INNER_LENGTH + (2 * WALL_THICKNESS)
    outer_width = INNER_WIDTH + (2 * WALL_THICKNESS)
    outer_height = INNER_HEIGHT + BASE_THICKNESS

    shell = cq.Workplane("XY").box(
        outer_length,
        outer_width,
        outer_height,
        centered=(True, True, False),
    )
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=BASE_THICKNESS)
        .box(
            INNER_LENGTH,
            INNER_WIDTH,
            INNER_HEIGHT,
            centered=(True, True, False),
        )
    )
    model = shell.cut(cavity)

    if FILLET_RADIUS > 0:
        model = model.edges("|Z").fillet(FILLET_RADIUS)

    for hole in MOUNTING_HOLES:
        depth = hole.get("depth") or BASE_THICKNESS
        cutter = (
            cq.Workplane("XY")
            .center(hole["x"], hole["y"])
            .circle(hole["diameter"] / 2.0)
            .extrude(depth)
        )
        model = model.cut(cutter)

    for cutout in CUTOUTS:
        model = model.cut(_make_cutout(cutout, outer_length, outer_width, outer_height))

    return model


def _make_cutout(
    cutout: dict[str, float | str | None],
    outer_length: float,
    outer_width: float,
    outer_height: float,
) -> cq.Workplane:
    face = cutout["face"]
    shape = cutout["shape"]
    depth = float(cutout.get("depth") or DEFAULT_CUT_DEPTH)

    if face == "front":
        workplane = cq.Workplane("XZ").workplane(offset=outer_width / 2.0)
        center = (float(cutout["x"]), float(cutout["z"]))
        direction = -depth
    elif face == "back":
        workplane = cq.Workplane("XZ").workplane(offset=-outer_width / 2.0)
        center = (float(cutout["x"]), float(cutout["z"]))
        direction = depth
    elif face == "right":
        workplane = cq.Workplane("YZ").workplane(offset=outer_length / 2.0)
        center = (float(cutout["y"]), float(cutout["z"]))
        direction = -depth
    elif face == "left":
        workplane = cq.Workplane("YZ").workplane(offset=-outer_length / 2.0)
        center = (float(cutout["y"]), float(cutout["z"]))
        direction = depth
    elif face == "top":
        workplane = cq.Workplane("XY").workplane(offset=outer_height)
        center = (float(cutout["x"]), float(cutout["y"]))
        direction = -depth
    elif face == "bottom":
        workplane = cq.Workplane("XY")
        center = (float(cutout["x"]), float(cutout["y"]))
        direction = depth
    else:
        raise ValueError(f"Unsupported face: {{face!r}}")

    if shape == "rectangular":
        return (
            workplane
            .center(*center)
            .rect(float(cutout["width"]), float(cutout["height"]))
            .extrude(direction)
        )

    if shape == "circular":
        return workplane.center(*center).circle(float(cutout["diameter"]) / 2.0).extrude(direction)

    raise ValueError(f"Unsupported cutout shape: {{shape!r}}")


def export_model(model: cq.Workplane) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(model, str(OUTPUT_DIR / f"{{PART_NAME}}.stl"))
    cq.exporters.export(model, str(OUTPUT_DIR / f"{{PART_NAME}}.step"))


result = build_enclosure()

if __name__ == "__main__":
    export_model(result)
'''


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cad_flow",
        description="Structured briefs, prompts, and starter scripts for parametric Python CAD generation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-brief", help="Write a starter design brief JSON file.")
    init_parser.add_argument("--output", "-o", required=True, help="Path to the JSON file to create.")

    validate_parser = subparsers.add_parser("validate", help="Validate a design brief JSON file.")
    validate_parser.add_argument("brief", help="Path to the JSON brief.")

    prompt_parser = subparsers.add_parser("prompt", help="Generate an LLM prompt from a brief.")
    prompt_parser.add_argument("brief", help="Path to the JSON brief.")
    prompt_parser.add_argument("--output", "-o", help="Optional file to write instead of stdout.")

    render_parser = subparsers.add_parser("render", help="Render a starter Python CAD script.")
    render_parser.add_argument("brief", help="Path to the JSON brief.")
    render_parser.add_argument("--output", "-o", required=True, help="Path to the Python file to write.")

    return parser


def write_text(path: str | Path, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-brief":
        preset_rectangular_enclosure().dump(args.output)
        print(f"Wrote starter brief to {args.output}")
        return

    if args.command == "validate":
        brief = DesignBrief.load(args.brief)
        print(
            "Validated "
            f"{brief.name}: outer {brief.outer_length:.1f} x {brief.outer_width:.1f} x {brief.outer_height:.1f} {brief.units}"
        )
        return

    if args.command == "prompt":
        brief = DesignBrief.load(args.brief)
        prompt = build_generation_prompt(brief)
        if args.output:
            write_text(args.output, prompt)
            print(f"Wrote prompt to {args.output}")
        else:
            print(prompt)
        return

    if args.command == "render":
        brief = DesignBrief.load(args.brief)
        script = render_script(brief)
        write_text(args.output, script)
        print(f"Wrote script to {args.output}")
        return

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()

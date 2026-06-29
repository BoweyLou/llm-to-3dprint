from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

SUPPORTED_LIBRARIES = {"cadquery", "build123d", "mesh"}
SUPPORTED_FACES = {"front", "back", "left", "right", "top", "bottom"}
SUPPORTED_SHAPES = {"rectangular", "circular"}
SUPPORTED_SYMMETRY = {"none", "x", "y", "xy", "radial"}
SUPPORTED_MESH_REUSE_POLICIES = {"partition_visible_mesh"}
SUPPORTED_DRAWER_MODES = {"separate_removable_trays"}
SUPPORTED_SKIN_SELECTION_STRATEGIES = {"front_visible_grid", "front_visible_raycast"}


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
class Closure:
    type: str
    insert_depth: float | None = None
    seat_z: float | None = None
    target_clearance: float | None = None
    assembled_orientation: str | None = None
    print_orientation: str | None = None
    supports_allowed: bool | None = None
    decorate_exterior_only: bool | None = None
    notes: str = ""

    def validate(self, *, outer_height: float) -> None:
        if not self.type:
            raise ValueError("closure.type must not be empty")
        if self.type != "open_top" and self.insert_depth is None and self.seat_z is None:
            raise ValueError("closure must define insert_depth or seat_z for non-open_top lid styles")
        if self.insert_depth is not None and self.insert_depth <= 0:
            raise ValueError(f"closure.insert_depth must be > 0, got {self.insert_depth!r}")
        if self.insert_depth is not None and self.insert_depth > outer_height:
            raise ValueError("closure.insert_depth must not exceed the enclosure outer height")
        if self.seat_z is not None and not (0 <= self.seat_z <= outer_height):
            raise ValueError(f"closure.seat_z must stay within 0..{outer_height}, got {self.seat_z!r}")
        if self.target_clearance is not None and self.target_clearance <= 0:
            raise ValueError(
                f"closure.target_clearance must be > 0, got {self.target_clearance!r}"
            )
        if self.assembled_orientation is not None and not self.assembled_orientation:
            raise ValueError("closure.assembled_orientation must not be empty when provided")
        if self.print_orientation is not None and not self.print_orientation:
            raise ValueError("closure.print_orientation must not be empty when provided")


@dataclass(slots=True)
class DesignIntent:
    silhouette: str | None = None
    visual_style: str | None = None
    symmetry: str | None = None
    surface_continuity: str | None = None
    must_be_smooth: bool | None = None
    max_slope_degrees: float | None = None
    min_wall_thickness: float | None = None
    forbidden_features: list[str] = field(default_factory=list)
    cross_sections: list[str] = field(default_factory=list)
    notes: str = ""

    def validate(self) -> None:
        for label, value in (
            ("silhouette", self.silhouette),
            ("visual_style", self.visual_style),
            ("surface_continuity", self.surface_continuity),
        ):
            if value is not None and not value:
                raise ValueError(f"design_intent.{label} must not be empty when provided")
        if self.symmetry is not None and self.symmetry not in SUPPORTED_SYMMETRY:
            raise ValueError(
                f"design_intent.symmetry must be one of {sorted(SUPPORTED_SYMMETRY)}, got {self.symmetry!r}"
            )
        if self.max_slope_degrees is not None and not (0 < self.max_slope_degrees <= 90):
            raise ValueError(
                f"design_intent.max_slope_degrees must be > 0 and <= 90, got {self.max_slope_degrees!r}"
            )
        if self.min_wall_thickness is not None and self.min_wall_thickness <= 0:
            raise ValueError(
                f"design_intent.min_wall_thickness must be > 0, got {self.min_wall_thickness!r}"
            )
        for feature in self.forbidden_features:
            if not feature:
                raise ValueError("design_intent.forbidden_features must not contain empty items")
        for section in self.cross_sections:
            if not section:
                raise ValueError("design_intent.cross_sections must not contain empty items")


@dataclass(slots=True)
class DrawerPatchMask:
    name: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    notes: str = ""

    def validate(self) -> None:
        if not self.name:
            raise ValueError("drawer patch mask name must not be empty")
        for low_label, high_label, low, high in (
            ("x_min", "x_max", self.x_min, self.x_max),
            ("y_min", "y_max", self.y_min, self.y_max),
            ("z_min", "z_max", self.z_min, self.z_max),
        ):
            if low >= high:
                raise ValueError(f"drawer patch mask {self.name!r} requires {low_label} < {high_label}")


@dataclass(slots=True)
class DrawerStack:
    drawer_count: int
    face: str = "front"
    mode: str = "separate_removable_trays"
    clearance: float = 0.5
    min_clearance: float = 0.4
    max_clearance: float = 0.6
    drawer_wall_thickness: float = 1.4
    body_wall_thickness: float = 2.2
    drawer_depth: float = 30.0
    front_lip_depth: float = 2.0
    front_visibility_depth: float = 2.2
    local_visibility_depth: float = 1.4
    visibility_grid: float = 0.35
    skin_selection_strategy: str = "front_visible_raycast"
    front_normal_min_y: float = 0.25
    min_patch_component_triangles: int = 20
    front_backing_offset: float = 0.8
    source_skin_shell_thickness: float = 0.8
    front_patch_includes: list[str] = field(default_factory=list)
    patch_masks: list[DrawerPatchMask] = field(default_factory=list)
    notes: str = ""

    def validate(self) -> None:
        if self.drawer_count <= 0:
            raise ValueError(f"drawer_stack.drawer_count must be > 0, got {self.drawer_count!r}")
        if self.face not in SUPPORTED_FACES:
            raise ValueError(f"drawer_stack.face must be one of {sorted(SUPPORTED_FACES)}, got {self.face!r}")
        if self.mode not in SUPPORTED_DRAWER_MODES:
            raise ValueError(
                f"drawer_stack.mode must be one of {sorted(SUPPORTED_DRAWER_MODES)}, got {self.mode!r}"
            )
        if self.clearance <= 0:
            raise ValueError(f"drawer_stack.clearance must be > 0, got {self.clearance!r}")
        if self.min_clearance <= 0 or self.max_clearance <= 0:
            raise ValueError("drawer_stack clearance bounds must be > 0")
        if self.min_clearance > self.max_clearance:
            raise ValueError("drawer_stack.min_clearance must not exceed max_clearance")
        if not (self.min_clearance <= self.clearance <= self.max_clearance):
            raise ValueError(
                "drawer_stack.clearance must stay within "
                f"{self.min_clearance:g}..{self.max_clearance:g}"
            )
        if self.drawer_wall_thickness <= 0:
            raise ValueError("drawer_stack.drawer_wall_thickness must be > 0")
        if self.body_wall_thickness <= 0:
            raise ValueError("drawer_stack.body_wall_thickness must be > 0")
        if self.drawer_depth <= 0:
            raise ValueError("drawer_stack.drawer_depth must be > 0")
        if self.front_lip_depth <= 0:
            raise ValueError("drawer_stack.front_lip_depth must be > 0")
        if self.front_visibility_depth <= 0:
            raise ValueError("drawer_stack.front_visibility_depth must be > 0")
        if self.local_visibility_depth <= 0:
            raise ValueError("drawer_stack.local_visibility_depth must be > 0")
        if self.visibility_grid <= 0:
            raise ValueError("drawer_stack.visibility_grid must be > 0")
        if self.skin_selection_strategy not in SUPPORTED_SKIN_SELECTION_STRATEGIES:
            raise ValueError(
                "drawer_stack.skin_selection_strategy must be one of "
                f"{sorted(SUPPORTED_SKIN_SELECTION_STRATEGIES)}, got {self.skin_selection_strategy!r}"
            )
        if not -1 <= self.front_normal_min_y <= 1:
            raise ValueError("drawer_stack.front_normal_min_y must stay within -1..1")
        if self.min_patch_component_triangles < 0:
            raise ValueError("drawer_stack.min_patch_component_triangles must be >= 0")
        if self.front_backing_offset <= 0:
            raise ValueError("drawer_stack.front_backing_offset must be > 0")
        if self.source_skin_shell_thickness <= 0:
            raise ValueError("drawer_stack.source_skin_shell_thickness must be > 0")
        if len(self.patch_masks) != self.drawer_count:
            raise ValueError("drawer_stack.patch_masks must define exactly one mask per drawer")
        seen: set[str] = set()
        for mask in self.patch_masks:
            mask.validate()
            if mask.name in seen:
                raise ValueError(f"drawer_stack.patch_masks contains duplicate name {mask.name!r}")
            seen.add(mask.name)


@dataclass(slots=True)
class MeshPreservation:
    source_3mf: str
    mesh_reuse_policy: str
    canonical_orientation: str = "front_rotated_180"
    canonical_rotate_z_degrees: float = 180.0
    source_model_member: str | None = None
    require_triangle_accounting: bool = True
    notes: str = ""

    def validate(self) -> None:
        if not self.source_3mf:
            raise ValueError("mesh_preservation.source_3mf must not be empty")
        if self.mesh_reuse_policy not in SUPPORTED_MESH_REUSE_POLICIES:
            raise ValueError(
                "mesh_preservation.mesh_reuse_policy must be one of "
                f"{sorted(SUPPORTED_MESH_REUSE_POLICIES)}, got {self.mesh_reuse_policy!r}"
            )
        if not self.canonical_orientation:
            raise ValueError("mesh_preservation.canonical_orientation must not be empty")


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
    closure: Closure | None = None
    design_intent: DesignIntent | None = None
    mesh_preservation: MeshPreservation | None = None
    drawer_stack: DrawerStack | None = None
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

    @property
    def resolved_lid_seat_z(self) -> float | None:
        if self.closure is None:
            return None
        if self.closure.seat_z is not None:
            return self.closure.seat_z
        if self.closure.insert_depth is not None:
            return self.outer_height - self.closure.insert_depth
        return None

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
        if self.closure is not None:
            if self.lid_style and self.lid_style != self.closure.type:
                raise ValueError("lid_style must match closure.type when closure metadata is provided")
            self.closure.validate(outer_height=self.outer_height)
        if self.design_intent is not None:
            self.design_intent.validate()
            if (
                self.design_intent.min_wall_thickness is not None
                and self.design_intent.min_wall_thickness > self.wall_thickness
            ):
                raise ValueError("design_intent.min_wall_thickness must not exceed wall_thickness")
        if self.mesh_preservation is not None:
            self.mesh_preservation.validate()
        if self.drawer_stack is not None:
            self.drawer_stack.validate()
        if (self.mesh_preservation is None) != (self.drawer_stack is None):
            raise ValueError("mesh_preservation and drawer_stack must be provided together")

        for cutout in self.cutouts:
            cutout.validate()
            if cutout.face in {"front", "back"} and not (0 <= cutout.z <= self.outer_height):
                raise ValueError(f"cutout {cutout.name!r} z must stay within 0..{self.outer_height}")
            if cutout.face in {"left", "right"} and not (0 <= cutout.z <= self.outer_height):
                raise ValueError(f"cutout {cutout.name!r} z must stay within 0..{self.outer_height}")
            if cutout.face in {"top", "bottom"}:
                x_limit = self.outer_length / 2
                y_limit = self.outer_width / 2
                if not (-x_limit <= cutout.x <= x_limit):
                    raise ValueError(f"cutout {cutout.name!r} x exceeds top/bottom face limits")
                if not (-y_limit <= cutout.y <= y_limit):
                    raise ValueError(f"cutout {cutout.name!r} y exceeds top/bottom face limits")

        x_limit = self.outer_length / 2
        y_limit = self.outer_width / 2
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
        internal_dimensions = Dimensions(**payload["internal_dimensions"])
        closure_payload = payload.get("closure")
        closure = Closure(**closure_payload) if closure_payload else None
        design_intent_payload = payload.get("design_intent")
        design_intent = DesignIntent(**design_intent_payload) if design_intent_payload else None
        mesh_preservation_payload = payload.get("mesh_preservation")
        mesh_preservation = (
            MeshPreservation(**mesh_preservation_payload) if mesh_preservation_payload else None
        )
        drawer_stack_payload = payload.get("drawer_stack")
        drawer_stack = None
        if drawer_stack_payload:
            drawer_payload = dict(drawer_stack_payload)
            drawer_payload["patch_masks"] = [
                DrawerPatchMask(**item) for item in drawer_payload.get("patch_masks", [])
            ]
            drawer_stack = DrawerStack(**drawer_payload)
        cutouts = [Cutout(**item) for item in payload.get("cutouts", [])]
        mounting_holes = [MountingHole(**item) for item in payload.get("mounting_holes", [])]
        brief = cls(
            name=payload["name"],
            description=payload["description"],
            object_type=payload["object_type"],
            library=payload.get("library", "cadquery"),
            units=payload.get("units", "mm"),
            base_shape=payload.get("base_shape", "rectangular"),
            internal_dimensions=internal_dimensions,
            wall_thickness=payload["wall_thickness"],
            base_thickness=payload.get("base_thickness"),
            fillet_radius=payload.get("fillet_radius", 0.0),
            lid_style=payload.get("lid_style", "open_top"),
            closure=closure,
            design_intent=design_intent,
            mesh_preservation=mesh_preservation,
            drawer_stack=drawer_stack,
            requirements=payload.get("requirements", []),
            cutouts=cutouts,
            mounting_holes=mounting_holes,
            notes=payload.get("notes", []),
        )
        brief.validate()
        return brief

    @classmethod
    def load(cls, path: str | Path) -> "DesignBrief":
        payload = json.loads(Path(path).read_text())
        return cls.from_dict(payload)

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")


def preset_rectangular_enclosure() -> DesignBrief:
    return DesignBrief.from_dict(
        {
            "name": "rectangular_enclosure_demo",
            "description": (
                "Open-top electronics enclosure with a front display cutout and four base mounting holes."
            ),
            "object_type": "enclosure",
            "library": "cadquery",
            "units": "mm",
            "base_shape": "rectangular",
            "internal_dimensions": {
                "length": 80.0,
                "width": 50.0,
                "height": 25.0,
            },
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
                }
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

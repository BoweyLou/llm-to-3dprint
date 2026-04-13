from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from uuid import uuid4


class FitCheckError(RuntimeError):
    """Raised when a CAD script cannot be fit-checked."""


@dataclass(slots=True)
class EnclosureProtocol:
    build_base: Callable[[], Any]
    build_lid: Callable[[], Any]
    seat_z: float


@dataclass(slots=True)
class FitCheckResult:
    seat_z: float
    overlap_solids: int
    overlap_volume: float

    @property
    def passes(self) -> bool:
        return self.overlap_solids == 0 and self.overlap_volume == 0.0


def load_script_module(path: str | Path) -> ModuleType:
    script_path = Path(path)
    if not script_path.exists():
        raise FitCheckError(f"Script not found: {script_path}")

    module_name = f"llm_to_3dprint_fitcheck_{script_path.stem}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise FitCheckError(f"Unable to import CAD script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_enclosure_protocol(module: ModuleType) -> EnclosureProtocol:
    build_base = getattr(module, "build_base", None)
    build_lid = getattr(module, "build_lid", None)
    if not callable(build_base) or not callable(build_lid):
        raise FitCheckError(
            "CAD script must expose callable build_base() and build_lid() functions for fit checks."
        )

    seat_z = _resolve_seat_height(module)
    return EnclosureProtocol(build_base=build_base, build_lid=build_lid, seat_z=seat_z)


def check_script_fit(path: str | Path) -> FitCheckResult:
    protocol = resolve_enclosure_protocol(load_script_module(path))
    return check_enclosure_fit(protocol)


def check_enclosure_fit(protocol: EnclosureProtocol) -> FitCheckResult:
    base = protocol.build_base()
    lid = protocol.build_lid()
    placed_lid = lid.translate((0.0, 0.0, protocol.seat_z))
    intersection = base.intersect(placed_lid)
    overlap_solids = len(intersection.solids().vals())
    overlap_volume = 0.0
    if overlap_solids:
        overlap_volume = float(intersection.val().Volume())

    return FitCheckResult(
        seat_z=protocol.seat_z,
        overlap_solids=overlap_solids,
        overlap_volume=overlap_volume,
    )


def _resolve_seat_height(module: ModuleType) -> float:
    seat_getter = getattr(module, "get_lid_seat_height", None)
    if callable(seat_getter):
        return float(seat_getter())

    explicit_seat = getattr(module, "LID_SEAT_Z", None)
    if explicit_seat is not None:
        return float(explicit_seat)

    base_outer_height = getattr(module, "BASE_OUTER_HEIGHT", None)
    lid_lip_depth = getattr(module, "LID_LIP_DEPTH", None)
    if base_outer_height is not None and lid_lip_depth is not None:
        return float(base_outer_height) - float(lid_lip_depth)

    raise FitCheckError(
        "CAD script must define get_lid_seat_height(), LID_SEAT_Z, or "
        "BASE_OUTER_HEIGHT and LID_LIP_DEPTH for fit checks."
    )

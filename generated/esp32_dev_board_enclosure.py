"""Parametric enclosure for a generic ESP32 development board.

Defaults assume a common dev-board envelope around 52 x 29 x 14 mm with a USB
connector centered on one short edge. All dimensions are millimeters.

Coordinate conventions:
- X runs along the board length.
- Y runs across the board width.
- Z=0 is the bottom face of each printed part.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq


PART_NAME = "esp32_dev_board_enclosure"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Board envelope and placement assumptions.
BOARD_LENGTH = 52.0
BOARD_WIDTH = 29.0
BOARD_THICKNESS = 1.6
BOARD_COMPONENT_HEIGHT = 14.0
BOARD_SUPPORT_HEIGHT = 3.0

USB_END_CLEARANCE = 8.0
FAR_END_CLEARANCE = 6.0
SIDE_CLEARANCE = 5.0
TOP_CLEARANCE = 2.0

# Base shell.
WALL_THICKNESS = 2.4
BASE_THICKNESS = 2.8
BASE_FILLET_RADIUS = 2.0

# Simple board support features. The lid holds the board down after assembly.
SUPPORT_PAD_LENGTH = 5.0
SUPPORT_PAD_WIDTH = 5.0
SUPPORT_PAD_INSET_X = 6.0
SUPPORT_PAD_INSET_Y = 4.0
LOCATOR_SIZE = 2.4
LOCATOR_BOARD_GAP = 0.6
LOCATOR_HEIGHT = BOARD_SUPPORT_HEIGHT + BOARD_THICKNESS + 1.0

# Cable opening on the USB side wall.
USB_OPENING_WIDTH = 12.0
USB_OPENING_HEIGHT = 8.0
USB_OPENING_BOTTOM_Z = BASE_THICKNESS + BOARD_SUPPORT_HEIGHT + 1.0
USB_OPENING_DEPTH = WALL_THICKNESS + 1.0

# Lid sized to print flat on the build plate.
LID_TOP_THICKNESS = 2.0
LID_LIP_DEPTH = 4.0
LID_LIP_THICKNESS = 1.6
LID_CLEARANCE = 0.35
VENT_SLOT_COUNT = 5
VENT_SLOT_LENGTH = 16.0
VENT_SLOT_WIDTH = 2.0
VENT_SLOT_PITCH = 4.0

ASSEMBLY_GAP = 8.0

INNER_LENGTH = BOARD_LENGTH + USB_END_CLEARANCE + FAR_END_CLEARANCE
INNER_WIDTH = BOARD_WIDTH + (2.0 * SIDE_CLEARANCE)
INNER_HEIGHT = BOARD_SUPPORT_HEIGHT + BOARD_COMPONENT_HEIGHT + TOP_CLEARANCE

OUTER_LENGTH = INNER_LENGTH + (2.0 * WALL_THICKNESS)
OUTER_WIDTH = INNER_WIDTH + (2.0 * WALL_THICKNESS)
BASE_OUTER_HEIGHT = INNER_HEIGHT + BASE_THICKNESS

BOARD_CENTER_X = (USB_END_CLEARANCE - FAR_END_CLEARANCE) / 2.0
USB_OPENING_CENTER_Z = USB_OPENING_BOTTOM_Z + (USB_OPENING_HEIGHT / 2.0)

LID_LIP_OUTER_LENGTH = INNER_LENGTH - (2.0 * LID_CLEARANCE)
LID_LIP_OUTER_WIDTH = INNER_WIDTH - (2.0 * LID_CLEARANCE)
LID_LIP_INNER_LENGTH = LID_LIP_OUTER_LENGTH - (2.0 * LID_LIP_THICKNESS)
LID_LIP_INNER_WIDTH = LID_LIP_OUTER_WIDTH - (2.0 * LID_LIP_THICKNESS)


def build_base() -> cq.Workplane:
    """Build the main enclosure body."""

    _validate_dimensions()

    shell = cq.Workplane("XY").box(
        OUTER_LENGTH,
        OUTER_WIDTH,
        BASE_OUTER_HEIGHT,
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

    if BASE_FILLET_RADIUS > 0:
        model = model.edges("|Z").fillet(BASE_FILLET_RADIUS)

    model = model.cut(_make_usb_cutout())
    model = model.union(_union_solids(_make_support_pads()))
    model = model.union(_union_solids(_make_corner_locators()))
    return model


def build_lid() -> cq.Workplane:
    """Build a simple friction-fit lid with vent slots."""

    _validate_dimensions()

    top = cq.Workplane("XY").box(
        OUTER_LENGTH,
        OUTER_WIDTH,
        LID_TOP_THICKNESS,
        centered=(True, True, False),
    )
    lip_outer = (
        cq.Workplane("XY")
        .workplane(offset=LID_TOP_THICKNESS)
        .box(
            LID_LIP_OUTER_LENGTH,
            LID_LIP_OUTER_WIDTH,
            LID_LIP_DEPTH,
            centered=(True, True, False),
        )
    )
    lip_inner = (
        cq.Workplane("XY")
        .workplane(offset=LID_TOP_THICKNESS)
        .box(
            LID_LIP_INNER_LENGTH,
            LID_LIP_INNER_WIDTH,
            LID_LIP_DEPTH,
            centered=(True, True, False),
        )
    )
    lid = top.union(lip_outer.cut(lip_inner))
    return lid.cut(_union_solids(_make_vent_slots()))


def build_preview_assembly() -> cq.Compound:
    """Return a simple exploded assembly for quick inspection."""

    base = build_base()
    lid = build_lid().translate((0.0, 0.0, BASE_OUTER_HEIGHT + ASSEMBLY_GAP))
    return cq.Compound.makeCompound([base.val(), lid.val()])


def export_parts() -> None:
    """Export the base, lid, and exploded assembly."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base = build_base()
    lid = build_lid()
    assembly = build_preview_assembly()

    cq.exporters.export(base, str(OUTPUT_DIR / f"{PART_NAME}_base.stl"))
    cq.exporters.export(base, str(OUTPUT_DIR / f"{PART_NAME}_base.step"))
    cq.exporters.export(lid, str(OUTPUT_DIR / f"{PART_NAME}_lid.stl"))
    cq.exporters.export(lid, str(OUTPUT_DIR / f"{PART_NAME}_lid.step"))
    cq.exporters.export(assembly, str(OUTPUT_DIR / f"{PART_NAME}_assembly.step"))


def _make_usb_cutout() -> cq.Workplane:
    return (
        cq.Workplane("YZ")
        .workplane(offset=-(OUTER_LENGTH / 2.0))
        .center(0.0, USB_OPENING_CENTER_Z)
        .rect(USB_OPENING_WIDTH, USB_OPENING_HEIGHT)
        .extrude(USB_OPENING_DEPTH)
    )


def _make_support_pads() -> list[cq.Workplane]:
    z_offset = BASE_THICKNESS
    x_offset = (BOARD_LENGTH / 2.0) - SUPPORT_PAD_INSET_X
    y_offset = (BOARD_WIDTH / 2.0) - SUPPORT_PAD_INSET_Y

    pads: list[cq.Workplane] = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            pads.append(
                cq.Workplane("XY")
                .workplane(offset=z_offset)
                .center(
                    BOARD_CENTER_X + (x_sign * x_offset),
                    y_sign * y_offset,
                )
                .box(
                    SUPPORT_PAD_LENGTH,
                    SUPPORT_PAD_WIDTH,
                    BOARD_SUPPORT_HEIGHT,
                    centered=(True, True, False),
                )
            )
    return pads


def _make_corner_locators() -> list[cq.Workplane]:
    z_offset = BASE_THICKNESS
    x_offset = (BOARD_LENGTH / 2.0) + LOCATOR_BOARD_GAP + (LOCATOR_SIZE / 2.0)
    y_offset = (BOARD_WIDTH / 2.0) + LOCATOR_BOARD_GAP + (LOCATOR_SIZE / 2.0)

    locators: list[cq.Workplane] = []
    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            locators.append(
                cq.Workplane("XY")
                .workplane(offset=z_offset)
                .center(
                    BOARD_CENTER_X + (x_sign * x_offset),
                    y_sign * y_offset,
                )
                .box(
                    LOCATOR_SIZE,
                    LOCATOR_SIZE,
                    LOCATOR_HEIGHT,
                    centered=(True, True, False),
                )
            )
    return locators


def _make_vent_slots() -> list[cq.Workplane]:
    slots: list[cq.Workplane] = []
    start_y = -((VENT_SLOT_COUNT - 1) * VENT_SLOT_PITCH) / 2.0
    for index in range(VENT_SLOT_COUNT):
        slots.append(
            cq.Workplane("XY")
            .center(BOARD_CENTER_X, start_y + (index * VENT_SLOT_PITCH))
            .rect(VENT_SLOT_LENGTH, VENT_SLOT_WIDTH)
            .extrude(LID_TOP_THICKNESS + 0.5)
        )
    return slots


def _union_solids(solids: list[cq.Workplane]) -> cq.Workplane:
    iterator = iter(solids)
    first = next(iterator)
    result = first
    for solid in iterator:
        result = result.union(solid)
    return result


def _validate_dimensions() -> None:
    if LID_LIP_INNER_LENGTH <= 0 or LID_LIP_INNER_WIDTH <= 0:
        raise ValueError("Lid lip dimensions are invalid; reduce thickness or increase enclosure size.")
    if USB_OPENING_BOTTOM_Z + USB_OPENING_HEIGHT >= BASE_OUTER_HEIGHT:
        raise ValueError("USB opening exceeds the enclosure wall height.")


if "show_object" in globals():
    show_object(build_base(), name="base")
    show_object(build_lid().translate((0.0, 0.0, BASE_OUTER_HEIGHT + ASSEMBLY_GAP)), name="lid")


if __name__ == "__main__":
    export_parts()

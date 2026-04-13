"""Retro-futurist ESP32 enclosure with a hybrid-color A1-friendly lid.

This variant keeps the same generic ESP32 dev-board fit as the plain enclosure
while splitting the Fallout-like styling into two workflows: flush in-place
color inserts that can print as part of the lid, and a separate vent shroud
that can print side by side as a glue-on accent. The vent openings remain
functional and the structural lid stays mechanically simple.

All dimensions are millimeters.

Coordinate conventions:
- X runs along the board length.
- Y runs across the board width.
- Z=0 is the bottom face of each printed part in assembled orientation.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq
from cadquery import exporters


PART_NAME = "esp32_dev_board_enclosure_retro_futurist"
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
WALL_THICKNESS = 2.6
BASE_THICKNESS = 3.0
BASE_FILLET_RADIUS = 3.0

# Board support features. The lid constrains the PCB vertically after assembly.
SUPPORT_PAD_LENGTH = 5.0
SUPPORT_PAD_WIDTH = 5.0
SUPPORT_PAD_INSET_X = 6.0
SUPPORT_PAD_INSET_Y = 4.0
LOCATOR_SIZE = 2.6
LOCATOR_BOARD_GAP = 0.6
LOCATOR_HEIGHT = BOARD_SUPPORT_HEIGHT + BOARD_THICKNESS + 1.0

# Retro wall treatments.
SERVICE_PANEL_DEPTH = 0.8
SERVICE_PANEL_Z = 10.0
SERVICE_PANEL_HEIGHT = 12.0
FRONT_PANEL_WIDTH = 48.0
SIDE_PANEL_WIDTH = 24.0
USB_FRAME_WIDTH = 18.0
USB_FRAME_HEIGHT = 12.0

# Cable opening on the USB side wall.
USB_OPENING_WIDTH = 12.5
USB_OPENING_HEIGHT = 8.5
USB_OPENING_BOTTOM_Z = BASE_THICKNESS + BOARD_SUPPORT_HEIGHT + 1.0
USB_OPENING_DEPTH = WALL_THICKNESS + 1.0

# Lid shell proportions.
LID_TOP_THICKNESS = 2.6
LID_LIP_DEPTH = 4.2
LID_LIP_THICKNESS = 1.6
LID_CLEARANCE = 0.35
LID_LIP_FILLET = 2.2
LID_LEAD_IN_CHAMFER = 0.5
LID_CORNER_FILLET = 2.0
LID_PULL_NOTCH_WIDTH = 11.0
LID_PULL_NOTCH_HEIGHT = 3.2
LID_PULL_NOTCH_DEPTH = 4.0
LID_PULL_NOTCH_OFFSET_Z = 1.2

# Functional vent openings in the lid shell.
VENT_SLOT_COUNT = 6
VENT_SLOT_LENGTH = 12.0
VENT_SLOT_WIDTH = 1.8
VENT_SLOT_PITCH = 3.2
VENT_BANK_CENTER_X = 10.0

# Flush in-place color inserts for same-object multi-color printing.
INSERT_DEPTH = 0.8
INSERT_BADGE_LENGTH = 12.5
INSERT_BADGE_WIDTH = 7.0
INSERT_BADGE_OFFSET_X = -10.0
INSERT_BADGE_OFFSET_Y = 0.0

INSERT_DIAL_RING_OUTER_DIAMETER = 8.8
INSERT_DIAL_RING_INNER_DIAMETER = 5.2
INSERT_DIAL_RING_OFFSET_X = 2.0
INSERT_DIAL_RING_OFFSET_Y = 0.0
INSERT_DIAL_POINTER_LENGTH = 4.6
INSERT_DIAL_POINTER_WIDTH = 1.2

INSERT_BOLT_DIAMETER = 4.8
INSERT_BOLT_INSET_X = 16.5
INSERT_BOLT_INSET_Y = 8.0

# Separate side-by-side vent shroud accent.
ACCENT_SHROUD_LENGTH = 23.0
ACCENT_SHROUD_WIDTH = 21.0
ACCENT_SHROUD_THICKNESS = 1.0
ACCENT_SHROUD_FILLET = 1.2
ACCENT_SHROUD_FRAME = 1.6
ACCENT_SHROUD_BAR_WIDTH = 1.0
ACCENT_SHROUD_BAR_COUNT = 4
ACCENT_SHROUD_BAR_PITCH = 3.6
ACCENT_SHROUD_TAB_LENGTH = 4.0
ACCENT_SHROUD_TAB_WIDTH = 6.0

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

LID_TOP_SURFACE_Z = LID_LIP_DEPTH + LID_TOP_THICKNESS
LID_TOTAL_HEIGHT = LID_TOP_SURFACE_Z
LID_SEAT_Z = BASE_OUTER_HEIGHT - LID_LIP_DEPTH


def build_base() -> cq.Workplane:
    """Build the enclosure body with recessed service panels."""

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

    for recess in _make_base_recesses():
        model = model.cut(recess)

    model = model.cut(_make_usb_frame_recess())
    model = model.cut(_make_usb_opening())
    model = model.union(_union_solids(_make_support_pads()))
    model = model.union(_union_solids(_make_corner_locators()))
    return model


def build_lid_main() -> cq.Workplane:
    """Build the structural lid shell in assembled orientation."""

    _validate_dimensions()

    lip_outer = cq.Workplane("XY").box(
        LID_LIP_OUTER_LENGTH,
        LID_LIP_OUTER_WIDTH,
        LID_LIP_DEPTH,
        centered=(True, True, False),
    )
    if LID_LIP_FILLET > 0:
        lip_outer = lip_outer.edges("|Z").fillet(LID_LIP_FILLET)
    if LID_LEAD_IN_CHAMFER > 0:
        lip_outer = lip_outer.faces("<Z").edges().chamfer(LID_LEAD_IN_CHAMFER)

    lip_inner = cq.Workplane("XY").box(
        LID_LIP_INNER_LENGTH,
        LID_LIP_INNER_WIDTH,
        LID_LIP_DEPTH,
        centered=(True, True, False),
    )

    top = cq.Workplane("XY").workplane(offset=LID_LIP_DEPTH).box(
        OUTER_LENGTH,
        OUTER_WIDTH,
        LID_TOP_THICKNESS,
        centered=(True, True, False),
    )
    if LID_CORNER_FILLET > 0:
        top = top.edges("|Z").fillet(LID_CORNER_FILLET)

    lid = lip_outer.cut(lip_inner).union(top)

    for cutter in _make_lid_shell_cuts():
        lid = lid.cut(cutter)

    return lid


def build_lid_inserts() -> cq.Workplane:
    """Build flush top-surface inserts in assembled orientation."""

    return _build_lid_insert_bodies(LID_TOP_SURFACE_Z - INSERT_DEPTH)


def build_lid_accent() -> cq.Workplane:
    """Build the separate vent shroud in assembled orientation."""

    return build_lid_accent_printable().translate((VENT_BANK_CENTER_X, 0.0, LID_TOP_SURFACE_Z))


def build_lid() -> cq.Workplane:
    """Build the full lid envelope for fit checks and assembly previews."""

    return build_lid_main().union(build_lid_inserts()).union(build_lid_accent())


def build_lid_main_for_print() -> cq.Workplane:
    """Orient the main lid shell for printing with the flat top on the bed."""

    return _rotate_180_about_x(build_lid_main(), LID_TOTAL_HEIGHT)


def build_lid_inserts_for_print() -> cq.Workplane:
    """Orient the flush inserts to match the lid's print orientation."""

    return _rotate_180_about_x(build_lid_inserts(), LID_TOTAL_HEIGHT)


def build_lid_accent_printable() -> cq.Workplane:
    """Build the separate vent shroud as a side-by-side printable part."""

    outer = cq.Workplane("XY").box(
        ACCENT_SHROUD_LENGTH,
        ACCENT_SHROUD_WIDTH,
        ACCENT_SHROUD_THICKNESS,
        centered=(True, True, False),
    )
    if ACCENT_SHROUD_FILLET > 0:
        outer = outer.edges("|Z").fillet(ACCENT_SHROUD_FILLET)

    inner = cq.Workplane("XY").box(
        ACCENT_SHROUD_LENGTH - (2.0 * ACCENT_SHROUD_FRAME),
        ACCENT_SHROUD_WIDTH - (2.0 * ACCENT_SHROUD_FRAME),
        ACCENT_SHROUD_THICKNESS,
        centered=(True, True, False),
    )
    accent = outer.cut(inner)

    start_y = -((ACCENT_SHROUD_BAR_COUNT - 1) * ACCENT_SHROUD_BAR_PITCH) / 2.0
    for index in range(ACCENT_SHROUD_BAR_COUNT):
        accent = accent.union(
            cq.Workplane("XY")
            .center(0.0, start_y + (index * ACCENT_SHROUD_BAR_PITCH))
            .box(
                ACCENT_SHROUD_LENGTH - (2.0 * ACCENT_SHROUD_FRAME),
                ACCENT_SHROUD_BAR_WIDTH,
                ACCENT_SHROUD_THICKNESS,
                centered=(True, True, False),
            )
        )

    for x_sign in (-1.0, 1.0):
        accent = accent.union(
            cq.Workplane("XY")
            .center(x_sign * ((ACCENT_SHROUD_LENGTH / 2.0) + (ACCENT_SHROUD_TAB_LENGTH / 2.0) - ACCENT_SHROUD_FRAME), 0.0)
            .box(
                ACCENT_SHROUD_TAB_LENGTH,
                ACCENT_SHROUD_TAB_WIDTH,
                ACCENT_SHROUD_THICKNESS,
                centered=(True, True, False),
            )
        )

    return accent


def build_preview_assembly() -> cq.Compound:
    """Return a simple exploded assembly for inspection."""

    base = build_base()
    lid = build_lid().translate((0.0, 0.0, LID_SEAT_Z + ASSEMBLY_GAP))
    return cq.Compound.makeCompound([base.val(), lid.val()])


def build_lid_multicolor_print_assembly() -> cq.Compound:
    """Return the print-oriented lid shell and inserts in aligned positions."""

    return cq.Compound.makeCompound([build_lid_main_for_print().val(), build_lid_inserts_for_print().val()])


def build_lid_bambu_assembly() -> cq.Assembly:
    """Return a named two-part assembly for Bambu import."""

    assembly = cq.Assembly(name=f"{PART_NAME}_lid_bambu")
    assembly.add(build_lid_main_for_print(), name="lid_shell")
    assembly.add(build_lid_inserts_for_print(), name="lid_inserts")
    return assembly


def export_parts() -> None:
    """Export only the print-facing files needed for the current workflow."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base = build_base()
    lid_shell_print = build_lid_main_for_print()
    lid_inserts_print = build_lid_inserts_for_print()
    lid_accent_print = build_lid_accent_printable()
    lid_bambu_assembly = build_lid_bambu_assembly()

    exporters.export(base, str(OUTPUT_DIR / f"{PART_NAME}_base.stl"))
    exporters.export(base, str(OUTPUT_DIR / f"{PART_NAME}_base.step"))

    exporters.export(lid_shell_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_shell.stl"))
    exporters.export(lid_shell_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_shell.step"))

    exporters.export(lid_inserts_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_inserts.stl"))
    exporters.export(lid_inserts_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_inserts.step"))

    exporters.export(lid_accent_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_accent.stl"))
    exporters.export(lid_accent_print, str(OUTPUT_DIR / f"{PART_NAME}_lid_accent.step"))

    lid_bambu_assembly.save(str(OUTPUT_DIR / f"{PART_NAME}_lid_bambu_multicolor.step"))


def get_lid_seat_height() -> float:
    return LID_SEAT_Z


def _make_usb_opening() -> cq.Workplane:
    return (
        cq.Workplane("YZ")
        .workplane(offset=-(OUTER_LENGTH / 2.0))
        .center(0.0, USB_OPENING_CENTER_Z)
        .rect(USB_OPENING_WIDTH, USB_OPENING_HEIGHT)
        .extrude(USB_OPENING_DEPTH)
    )


def _make_usb_frame_recess() -> cq.Workplane:
    return (
        cq.Workplane("YZ")
        .workplane(offset=-(OUTER_LENGTH / 2.0))
        .center(0.0, USB_OPENING_CENTER_Z)
        .rect(USB_FRAME_WIDTH, USB_FRAME_HEIGHT)
        .extrude(SERVICE_PANEL_DEPTH)
    )


def _make_base_recesses() -> list[cq.Workplane]:
    return [
        _make_face_recess("front", FRONT_PANEL_WIDTH, SERVICE_PANEL_HEIGHT, SERVICE_PANEL_Z, 0.0),
        _make_face_recess("back", FRONT_PANEL_WIDTH, SERVICE_PANEL_HEIGHT, SERVICE_PANEL_Z, 0.0),
        _make_face_recess("right", SIDE_PANEL_WIDTH, SERVICE_PANEL_HEIGHT, SERVICE_PANEL_Z, 0.0),
    ]


def _make_lid_shell_cuts() -> list[cq.Workplane]:
    cutters: list[cq.Workplane] = []
    start_y = -((VENT_SLOT_COUNT - 1) * VENT_SLOT_PITCH) / 2.0

    for index in range(VENT_SLOT_COUNT):
        cutters.append(
            cq.Workplane("XY")
            .workplane(offset=LID_LIP_DEPTH + LID_TOP_THICKNESS)
            .center(VENT_BANK_CENTER_X, start_y + (index * VENT_SLOT_PITCH))
            .rect(VENT_SLOT_LENGTH, VENT_SLOT_WIDTH)
            .extrude(-LID_TOP_THICKNESS)
        )

    cutters.append(
        cq.Workplane("XZ")
        .workplane(offset=OUTER_WIDTH / 2.0)
        .center(0.0, LID_LIP_DEPTH + LID_PULL_NOTCH_OFFSET_Z)
        .rect(LID_PULL_NOTCH_WIDTH, LID_PULL_NOTCH_HEIGHT)
        .extrude(-LID_PULL_NOTCH_DEPTH)
    )

    cutters.append(build_lid_inserts())

    return cutters


def _build_lid_insert_bodies(z_base: float) -> cq.Workplane:
    badge = (
        cq.Workplane("XY")
        .workplane(offset=z_base)
        .center(INSERT_BADGE_OFFSET_X, INSERT_BADGE_OFFSET_Y)
        .box(
            INSERT_BADGE_LENGTH,
            INSERT_BADGE_WIDTH,
            INSERT_DEPTH,
            centered=(True, True, False),
        )
    )

    dial_outer = (
        cq.Workplane("XY")
        .workplane(offset=z_base)
        .center(INSERT_DIAL_RING_OFFSET_X, INSERT_DIAL_RING_OFFSET_Y)
        .circle(INSERT_DIAL_RING_OUTER_DIAMETER / 2.0)
        .extrude(INSERT_DEPTH)
    )
    dial_inner = (
        cq.Workplane("XY")
        .workplane(offset=z_base)
        .center(INSERT_DIAL_RING_OFFSET_X, INSERT_DIAL_RING_OFFSET_Y)
        .circle(INSERT_DIAL_RING_INNER_DIAMETER / 2.0)
        .extrude(INSERT_DEPTH)
    )
    dial_pointer = (
        cq.Workplane("XY")
        .workplane(offset=z_base)
        .center(INSERT_DIAL_RING_OFFSET_X + 1.1, 2.1)
        .box(
            INSERT_DIAL_POINTER_LENGTH,
            INSERT_DIAL_POINTER_WIDTH,
            INSERT_DEPTH,
            centered=(True, True, False),
        )
        .rotate((INSERT_DIAL_RING_OFFSET_X, 0.0, z_base), (INSERT_DIAL_RING_OFFSET_X, 0.0, z_base + 1.0), -25.0)
    )
    inserts = badge.union(dial_outer.cut(dial_inner)).union(dial_pointer)

    for x_sign in (-1.0, 1.0):
        for y_sign in (-1.0, 1.0):
            inserts = inserts.union(
                cq.Workplane("XY")
                .workplane(offset=z_base)
                .center(x_sign * INSERT_BOLT_INSET_X, y_sign * INSERT_BOLT_INSET_Y)
                .circle(INSERT_BOLT_DIAMETER / 2.0)
                .extrude(INSERT_DEPTH)
            )

    return inserts


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


def _make_face_recess(
    face: str,
    width: float,
    height: float,
    z_center: float,
    lateral_center: float,
) -> cq.Workplane:
    if face == "front":
        return (
            cq.Workplane("XZ")
            .workplane(offset=OUTER_WIDTH / 2.0)
            .center(lateral_center, z_center)
            .rect(width, height)
            .extrude(-SERVICE_PANEL_DEPTH)
        )
    if face == "back":
        return (
            cq.Workplane("XZ")
            .workplane(offset=-(OUTER_WIDTH / 2.0))
            .center(lateral_center, z_center)
            .rect(width, height)
            .extrude(SERVICE_PANEL_DEPTH)
        )
    if face == "right":
        return (
            cq.Workplane("YZ")
            .workplane(offset=OUTER_LENGTH / 2.0)
            .center(lateral_center, z_center)
            .rect(width, height)
            .extrude(-SERVICE_PANEL_DEPTH)
        )
    if face == "left":
        return (
            cq.Workplane("YZ")
            .workplane(offset=-(OUTER_LENGTH / 2.0))
            .center(lateral_center, z_center)
            .rect(width, height)
            .extrude(SERVICE_PANEL_DEPTH)
        )
    raise ValueError(f"Unsupported recess face: {face!r}")


def _rotate_180_about_x(model: cq.Workplane, height: float) -> cq.Workplane:
    return model.rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 180.0).translate((0.0, 0.0, height))


def _union_solids(solids: list[cq.Workplane]) -> cq.Workplane:
    iterator = iter(solids)
    result = next(iterator)
    for solid in iterator:
        result = result.union(solid)
    return result


def _validate_dimensions() -> None:
    if LID_LIP_INNER_LENGTH <= 0 or LID_LIP_INNER_WIDTH <= 0:
        raise ValueError("Lid lip dimensions are invalid; reduce thickness or increase enclosure size.")
    if USB_OPENING_BOTTOM_Z + USB_OPENING_HEIGHT >= BASE_OUTER_HEIGHT:
        raise ValueError("USB opening exceeds the enclosure wall height.")
    if INSERT_DEPTH >= LID_TOP_THICKNESS:
        raise ValueError("Insert depth must remain smaller than the lid top thickness.")
    if ACCENT_SHROUD_FRAME * 2.0 >= ACCENT_SHROUD_LENGTH or ACCENT_SHROUD_FRAME * 2.0 >= ACCENT_SHROUD_WIDTH:
        raise ValueError("Accent shroud frame is too thick for the selected shroud size.")


if "show_object" in globals():
    show_object(build_base(), name="retro_base")
    show_object(build_lid(), name="retro_lid")
    show_object(build_lid_main_for_print(), name="retro_lid_main_print")
    show_object(build_lid_inserts_for_print().translate((0.0, 0.0, 10.0)), name="retro_lid_inserts_print")
    show_object(build_lid_accent_printable().translate((0.0, 0.0, 12.0)), name="retro_lid_accent_print")


if __name__ == "__main__":
    export_parts()

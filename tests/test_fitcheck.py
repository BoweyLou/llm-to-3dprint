from types import SimpleNamespace

import pytest

from llm_to_3dprint.fitcheck import FitCheckError, resolve_enclosure_protocol


def test_resolve_enclosure_protocol_uses_explicit_lid_seat_z() -> None:
    module = SimpleNamespace(
        build_base=lambda: object(),
        build_lid=lambda: object(),
        LID_SEAT_Z=12.5,
    )

    protocol = resolve_enclosure_protocol(module)

    assert protocol.seat_z == 12.5


def test_resolve_enclosure_protocol_falls_back_to_base_height_minus_lip_depth() -> None:
    module = SimpleNamespace(
        build_base=lambda: object(),
        build_lid=lambda: object(),
        BASE_OUTER_HEIGHT=22.0,
        LID_LIP_DEPTH=4.2,
    )

    protocol = resolve_enclosure_protocol(module)

    assert protocol.seat_z == pytest.approx(17.8)


def test_resolve_enclosure_protocol_prefers_seat_height_getter() -> None:
    module = SimpleNamespace(
        build_base=lambda: object(),
        build_lid=lambda: object(),
        get_lid_seat_height=lambda: 9.75,
        BASE_OUTER_HEIGHT=100.0,
        LID_LIP_DEPTH=1.0,
    )

    protocol = resolve_enclosure_protocol(module)

    assert protocol.seat_z == 9.75


def test_resolve_enclosure_protocol_requires_builders() -> None:
    module = SimpleNamespace(LID_SEAT_Z=1.0)

    with pytest.raises(FitCheckError, match="build_base"):
        resolve_enclosure_protocol(module)


def test_resolve_enclosure_protocol_requires_seat_height_information() -> None:
    module = SimpleNamespace(
        build_base=lambda: object(),
        build_lid=lambda: object(),
    )

    with pytest.raises(FitCheckError, match="LID_SEAT_Z"):
        resolve_enclosure_protocol(module)

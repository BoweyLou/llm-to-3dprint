from llm_to_3dprint.brief import Cutout, preset_rectangular_enclosure
from llm_to_3dprint.renderers import render_script


def test_rendered_script_is_valid_python() -> None:
    script = render_script(preset_rectangular_enclosure())

    assert "import cadquery as cq" in script
    assert "def build_enclosure()" in script
    compile(script, "<generated enclosure>", "exec")


def test_rendered_script_uses_python_none_for_optional_fields() -> None:
    brief = preset_rectangular_enclosure()
    brief.cutouts.append(
        Cutout(
            name="side_cable",
            face="right",
            shape="circular",
            z=8.0,
            diameter=6.0,
            depth=4.0,
        )
    )
    brief.validate()

    script = render_script(brief)

    assert "null" not in script
    assert "'width': None" in script
    assert "'height': None" in script

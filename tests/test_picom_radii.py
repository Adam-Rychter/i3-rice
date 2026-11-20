from pathlib import Path

import pytest

from i3_rice_gui.picom_radii import find_radius, parse_radius_line, replace_radius_value


def test_sample_exposes_both_global_radii():
    text = (Path(__file__).parent / "fixtures/picom/picom.conf").read_text()
    corner = find_radius(text, "corner-radius")
    shadow = find_radius(text, "shadow-radius")
    assert (corner.value, shadow.value) == (16, 8)
    assert "window exclusions" in corner.context
    assert text[corner.start:corner.end] == "corner-radius = 16;"


def test_comments_strings_and_line_endings_are_preserved():
    text = (
        '# corner-radius = 100;\r\n'
        'shadow-exclude = ["corner-radius = 8;"]; // corner-radius = 4;\r\n'
        '/* corner-radius = 5; */\r\n'
        '  corner-radius =  16  ;  \r\n'
    )
    setting = find_radius(text, "corner-radius")
    assert setting.value == 16
    assert replace_radius_value(setting.line, 4, "corner-radius") == "  corner-radius =  4  ;  "
    assert text[setting.start:setting.end] == setting.line


@pytest.mark.parametrize("text", [
    "corner-radius = 2;\ncorner-radius = 3;\n",
    "corner-radius = 2; corner-radius = 3;\n",
    "corner-radius = 2;\n@include \"extra.conf\"\n",
    "corner-radius = 2;\nrules: ({ corner-radius = 4; });\n",
    "rules: ({ corner-radius = 4; });\n",
    "corner-radius = 2px;\n",
    "corner-radius = 2; # inline comment\n",
    "corner-radius = 2;\nother = \"unterminated\n",
    "corner-radius = 2;\n/* unterminated\n",
    "corner-radius = 2;\nrules = ([);",
])
def test_ambiguous_or_unsupported_radius_is_not_editable(text):
    with pytest.raises(ValueError):
        find_radius(text, "corner-radius")


def test_radius_ranges_and_independent_overrides():
    assert parse_radius_line("corner-radius = 0;", "corner-radius") == 0
    assert parse_radius_line("shadow-radius = 1", "shadow-radius") == 1
    for kind, line in (
        ("corner-radius", "corner-radius = 101;"),
        ("shadow-radius", "shadow-radius = 0;"),
    ):
        with pytest.raises(ValueError):
            parse_radius_line(line, kind)
    text = "corner-radius = 2;\nshadow-radius = 3;\nrules: ({ corner-radius = 4; });\n"
    assert find_radius(text, "shadow-radius").value == 3
    with pytest.raises(ValueError):
        find_radius(text, "corner-radius")

from pathlib import Path

import pytest

from i3_rice_gui.rofi_radius import find_radius, parse_radius_line, replace_radius_value


def test_sample_window_radius_ignores_other_widgets():
    text = (Path(__file__).parent / "fixtures/rofi/catppuccin-mocha.rasi").read_text()
    setting = find_radius(text)
    assert setting.value == 16
    assert "other theme files may override" in setting.context
    assert text[setting.start:setting.end] == "    border-radius: 16px;"


def test_masking_and_replacement_preserve_rasi_format():
    text = (
        "/* outer /* nested window { border-radius: 2px; } */ still comment */\r\n"
        "* { bg: #aabbcc; }\r\n"
        "window {\r\n"
        "  border-radius :  8px ;  \r\n"
        "  text: 'window { border-radius: 20px; }';\r\n"
        "}\r\n"
    )
    setting = find_radius(text)
    assert setting.value == 8
    assert replace_radius_value(setting.line, 10) == "  border-radius :  10px ;  "
    assert text[setting.start:setting.end] == setting.line


@pytest.mark.parametrize("text", [
    "window {\n border-radius: 8px;\n border-radius: 9px;\n}\n",
    "window {\n border-radius: 8px;\n}\nwindow {\n border-radius: 9px;\n}\n",
    "window {\n border-radius: 8px;\n}\n#window {\n border-radius: 9px;\n}\n",
    "window {\n border-radius: 8px;\n}\nwindow selected { text-color: red; }\n",
    '@import "other.rasi"\nwindow {\n border-radius: 8px;\n}\n',
    '@theme "other"\nwindow {\n border-radius: 8px;\n}\n',
    "* { radius: 8px; }\nwindow {\n border-radius: @{radius};\n}\n",
    "window {\n border-radius: 8%;\n}\n",
    "window {\n border-radius: 8px; /* comment */\n}\n",
    "window {\n border-radius: 101px;\n}\n",
    "window {\n border-radius: 8px;\n",
    "window {\n border-radius: 8px;\n}\n/* unclosed",
])
def test_ambiguous_or_unsupported_themes_are_not_editable(text):
    with pytest.raises(ValueError):
        find_radius(text)


def test_radius_snippet_requires_bounded_pixel_value():
    assert parse_radius_line("border-radius: 0px;") == 0
    assert parse_radius_line("border-radius: 100px;") == 100
    for line in ("border-radius: -1px;", "border-radius: 101px;", "border-radius: 2em;"):
        with pytest.raises(ValueError):
            parse_radius_line(line)

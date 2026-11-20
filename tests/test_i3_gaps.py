from pathlib import Path

import pytest

from i3_rice_gui.i3_appearance import find_setting, parse_setting_line, replace_setting_value


def test_demo_config_exposes_an_editable_gap():
    path = Path(__file__).parent / "fixtures/i3/config"
    assert find_setting(path.read_text(), "inner").value == 10
    assert find_setting(path.read_text(), "outer").value == 5
    assert find_setting(path.read_text(), "pixel_border").value == 2


def test_finds_literal_and_preserves_formatting():
    text = "# setup\r\n  gaps  inner  12  \r\nother line\r\n"
    setting = find_setting(text, "inner")
    assert setting.value == 12
    assert text[setting.start:setting.end] == setting.line
    assert replace_setting_value(setting.line, 8, "inner") == "  gaps  inner  8  "


@pytest.mark.parametrize("text", [
    "gaps inner $gap\n",
    "gaps inner 3\ngaps inner 4\n",
    "gaps inner 3\ninclude ~/.config/i3/extra\n",
    "mode resize {\n gaps inner 3\n}\n",
    "gaps inner 201\n",
    "gaps inner 10 # inline comments are not accepted by i3\n",
])
def test_ambiguous_or_unsupported_config_is_not_editable(text):
    with pytest.raises(ValueError):
        find_setting(text, "inner")


def test_invalid_manual_snippet_is_rejected():
    with pytest.raises(ValueError):
        parse_setting_line("gaps inner 4; exec something", "inner")


def test_outer_gap_accepts_negative_values_without_affecting_inner():
    text = "gaps inner 4\ngaps outer -10\n"
    assert find_setting(text, "outer").value == -10
    assert replace_setting_value("gaps outer -10", 15, "outer") == "gaps outer 15"
    assert find_setting(text, "inner").value == 4
    with pytest.raises(ValueError):
        parse_setting_line("gaps outer -201", "outer")
    with pytest.raises(ValueError):
        parse_setting_line("gaps inner -1", "inner")


def test_duplicate_outer_setting_does_not_disable_inner():
    text = "gaps inner 4\ngaps outer 1\ngaps outer 2\n"
    assert find_setting(text, "inner").value == 4
    with pytest.raises(ValueError):
        find_setting(text, "outer")


def test_pixel_border_preserves_format_and_limits():
    line = "  default_border  pixel  2  "
    assert find_setting(line + "\n", "pixel_border").value == 2
    assert replace_setting_value(line, 0, "pixel_border") == "  default_border  pixel  0  "
    with pytest.raises(ValueError):
        parse_setting_line("default_border pixel 21", "pixel_border")


@pytest.mark.parametrize("text", [
    "default_border normal 2\n",
    "default_border pixel\n",
    "default_border pixel $width\n",
    "default_border pixel 2\ndefault_border normal 3\n",
    "default_border pixel 2\ninclude extra\n",
    "mode resize {\n default_border pixel 2\n}\n",
])
def test_unsupported_borders_are_not_editable(text):
    with pytest.raises(ValueError):
        find_setting(text, "pixel_border")

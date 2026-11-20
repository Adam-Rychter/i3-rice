from pathlib import Path

import pytest

from i3_rice_gui.dunst_colors import find_color, parse_color_line, replace_color_value


def test_sample_frame_colors_are_independent():
    text = (Path(__file__).parent / "fixtures/dunst/dunstrc").read_text()
    normal = find_color(text, "urgency_normal")
    assert normal.value == "#89b4fa"
    assert "Only [urgency_normal]" in normal.context
    assert find_color(text, "urgency_critical").value == "#f38ba8"
    assert text[normal.start:normal.end] == normal.line


def test_color_replacement_preserves_format_and_line_endings():
    text = '[global]\r\n  frame_color  =  "#AaBbCc"  \r\n'
    setting = find_color(text, "global")
    assert setting.value == "#AaBbCc"
    assert replace_color_value(setting.line, "#123456") == '  frame_color  =  "#123456"  '
    assert text[setting.start:setting.end] == setting.line


@pytest.mark.parametrize("text", [
    '[global]\nframe_color = "#112233"\nframe_color = "#445566"\n',
    '[global]\nframe_color = "#112233"\n[global]\nframe_color = "#445566"\n',
    '[global]\nframe_color = "#abc"\n',
    '[global]\nframe_color = "#112233ff"\n',
    '[global]\nframe_color = "red"\n',
    '[global]\nframe_color = "#112233" # comment\n',
    '[global]\nframe_color = "#112233"\n@include "other"\n',
    '[global]\nframe_color = "#112233"\n[invalid\n',
])
def test_unsupported_colors_are_not_editable(text):
    with pytest.raises(ValueError):
        find_color(text, "global")


def test_invalid_color_snippet_and_replacement_are_rejected():
    with pytest.raises(ValueError):
        parse_color_line('frame_color = "#ab"')
    with pytest.raises(ValueError):
        replace_color_value('frame_color = "#112233"', "red")

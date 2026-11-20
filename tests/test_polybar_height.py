from pathlib import Path

import pytest

from i3_rice_gui.polybar_height import find_height, parse_height_line, replace_height_value


def test_sample_height_includes_affected_inheriting_sections():
    text = (Path(__file__).parent / "fixtures/polybar/config.ini").read_text()
    setting = find_height(text)
    assert setting.value == 56
    assert setting.context == "Affected sections: bar/main, bar/secondary."
    assert text[setting.start:setting.end] == "height = 56"


def test_height_edit_preserves_format_and_section_overrides():
    text = "[bar/main]\r\n  height  =  28  \r\n[bar/other]\r\ninherit = bar/main\r\nheight = 70\r\n"
    setting = find_height(text)
    assert setting.context == "Affected sections: bar/main."
    assert replace_height_value(setting.line, 40) == "  height  =  40  "
    assert text[setting.start:setting.end] == setting.line


@pytest.mark.parametrize("text", [
    "[bar/main]\nheight = 28\nheight = 40\n",
    "[bar/main]\nheight = 28\n[bar/main]\nheight = 40\n",
    "[bar/main]\nheight = 5%\n",
    "[bar/main]\nheight = ${size.height}\n",
    "[bar/main]\nheight = 28 ; comment\n",
    "[bar/main]\nheight = 201\n",
    "[bar/main]\nheight = 28\ninclude-file = other.ini\n",
    "[bar/main]\nheight = 28\ninclude-directory = extra\n",
    "[bar/main]\nheight = 28\n[bar/child]\ninherit = bar/main another\n",
    "[bar/main]\nheight = 28\n[bar/child]\ninherit = bar/main\ninherit = bar/main\n",
    "[bar/main]\nheight = 28\n[bar/child]\ninherit = bar/main\nheight =\n",
    "[bar/main]\nheight = 28\n[module/a]\nsize = ${root.height}\n",
    "[bar/main]\nheight = 28\n[module/a]\nsize = ${bar/main.height}\n",
    "[bar/main]\nheight = 28\n[unsupported header] ; comment\n",
])
def test_ambiguous_or_unsupported_configuration_is_not_editable(text):
    with pytest.raises(ValueError):
        find_height(text)


def test_height_snippet_requires_bounded_integer():
    assert parse_height_line("height = 1") == 1
    assert parse_height_line("height = 200") == 200
    for text in ("height = 0", "height = 201", "height = 30px", "height = 2%"):
        with pytest.raises(ValueError):
            parse_height_line(text)

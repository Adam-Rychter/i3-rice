import pytest

from i3_rice_gui.i3_gaps import find_inner_gap, parse_gap_line, replace_gap_value


def test_finds_literal_and_preserves_formatting():
    text = "# setup\r\n  gaps  inner  12  # padding\r\nother line\r\n"
    setting = find_inner_gap(text)
    assert setting.value == 12
    assert text[setting.start:setting.end] == setting.line
    assert replace_gap_value(setting.line, 8) == "  gaps  inner  8  # padding"


@pytest.mark.parametrize("text", [
    "gaps inner $gap\n",
    "gaps inner 3\ngaps inner 4\n",
    "gaps inner 3\ninclude ~/.config/i3/extra\n",
    "mode resize {\n gaps inner 3\n}\n",
    "gaps inner 201\n",
])
def test_ambiguous_or_unsupported_config_is_not_editable(text):
    with pytest.raises(ValueError):
        find_inner_gap(text)


def test_invalid_manual_snippet_is_rejected():
    with pytest.raises(ValueError):
        parse_gap_line("gaps inner 4; exec something")

import pytest

from i3_rice_gui.i3_variables import (
    find_variable, find_variables, has_includes, replace_variable_value, variable_references,
)


def test_variables_preserve_ranges_and_report_references():
    text = 'set $mod Mod4  # shared\nbindsym $mod+Return exec xterm\nset $ws1 "1:term"\n'

    variables = find_variables(text)

    assert [(variable.name, variable.value) for variable in variables] == [
        ("mod", "Mod4"), ("ws1", "1:term"),
    ]
    setting = find_variable(text, "mod")
    assert text[setting.start:setting.end] == "set $mod Mod4  # shared"
    assert len(variable_references(text, "mod")) == 1


def test_variable_replacement_preserves_comments_and_quote_style():
    assert replace_variable_value("set $mod Mod4  # shared", "Mod1") == (
        "set $mod Mod1  # shared"
    )
    assert replace_variable_value('set $ws1 "1:term"', "1:code") == (
        'set $ws1 "1:code"'
    )


def test_duplicate_and_invalid_values_are_rejected():
    with pytest.raises(ValueError, match="assigned more than once"):
        find_variables("set $mod Mod4\nset $mod Mod1\n")
    with pytest.raises(ValueError):
        replace_variable_value("set $mod Mod4", "value # unsafe")


def test_include_detection_ignores_comments():
    assert has_includes("# include other.conf\ninclude ~/.config/i3/keys.conf\n")
    assert not has_includes("# include other.conf\nset $mod Mod4\n")

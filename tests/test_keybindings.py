import pytest

from i3_rice_gui.keybindings import (
    binding_conflicts, find_keybinding, find_keybindings, replace_keybinding_command,
)


def test_keybindings_preserve_source_ranges_and_commands():
    text = "# keys\nbindsym $mod+Return exec xterm\n  bindsym Print exec maim -s | xclip\n"

    bindings = find_keybindings(text)

    assert [(item.trigger, item.command) for item in bindings] == [
        ("$mod+Return", "exec xterm"),
        ("Print", "exec maim -s | xclip"),
    ]
    assert text[bindings[0].start:bindings[0].end] == "bindsym $mod+Return exec xterm"


def test_duplicate_triggers_are_reported_as_conflicts():
    text = "bindsym $mod+q kill\nbindsym $mod+q exec xterm\n"

    assert binding_conflicts(find_keybindings(text)) == ("$mod+q",)
    with pytest.raises(ValueError, match="assigned more than once"):
        find_keybinding(text, "$mod+q")


def test_missing_trigger_is_reported():
    with pytest.raises(ValueError, match="not found"):
        find_keybinding("bindsym $mod+q kill\n", "$mod+w")


def test_command_replacement_preserves_trigger_and_rejects_multiline_values():
    assert replace_keybinding_command("  bindsym Print exec maim", "exec scrot") == (
        "  bindsym Print exec scrot"
    )
    with pytest.raises(ValueError, match="one line"):
        replace_keybinding_command("bindsym Print exec maim", "exec\nx")

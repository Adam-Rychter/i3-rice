import pytest

from i3_rice_gui.workspace_labels import (
    find_workspace, find_workspace_labels, parse_workspace_line, replace_workspace_label,
)


def test_workspace_labels_are_sorted_and_preserve_ranges():
    text = '# labels\nset $ws2 "2:code"  # editor\nset $ws1 "1:term"\n'

    labels = find_workspace_labels(text)

    assert [(label.number, label.name) for label in labels] == [
        (1, "1:term"), (2, "2:code"),
    ]
    setting = find_workspace(text, 2)
    assert text[setting.start:setting.end] == 'set $ws2 "2:code"  # editor'


def test_workspace_label_replacement_preserves_literal_syntax():
    line = 'set $ws3 "3:web"'

    assert parse_workspace_line(line) == (3, "3:web")
    assert replace_workspace_label(line, "3:browser") == 'set $ws3 "3:browser"'


@pytest.mark.parametrize(
    "text, message",
    [
        ('set $ws1 "one"\nset $ws1 "again"\n', "assigned more than once"),
        ("set $ws1 $dynamic\n", "quoted literal"),
        ("set $ws1 \"\"\n", "non-empty"),
    ],
)
def test_unsupported_workspace_assignments_are_rejected(text, message):
    if 'set $ws1 ""' in text:
        with pytest.raises(ValueError):
            replace_workspace_label(text.rstrip(), "")
    else:
        with pytest.raises(ValueError, match=message):
            find_workspace_labels(text)


def test_missing_workspace_is_reported():
    with pytest.raises(ValueError, match="not found"):
        find_workspace('set $ws1 "one"\n', 2)

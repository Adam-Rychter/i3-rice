import pytest

from i3_rice_gui.document import ConfigDocument, StaleEditError


def test_staged_edit_preserves_unrelated_content_and_does_not_write(tmp_path):
    path = tmp_path / "config"
    original = "# unchanged\r\ngaps inner 10  # café\r\ncustom directive\r\n"
    path.write_bytes(original.encode())
    document = ConfigDocument.open(path)
    start = document.draft.index("10")

    document.replace(start, start + 2, "10", "15")

    assert document.draft == original.replace("10", "15")
    assert document.is_dirty
    assert path.read_bytes() == original.encode()
    assert "-gaps inner 10" in document.diff()
    assert "+gaps inner 15" in document.diff()
    document.discard()
    assert document.draft == original
    assert not document.is_dirty


def test_stale_and_out_of_range_edits_do_not_modify_draft(tmp_path):
    path = tmp_path / "config"
    path.write_text("gaps inner 10\n")
    document = ConfigDocument.open(path)

    with pytest.raises(StaleEditError):
        document.replace(11, 13, "20", "30")
    with pytest.raises(ValueError, match="outside"):
        document.replace(-1, 2, "", "")
    assert document.draft == document.baseline
    assert not document.is_dirty


def test_external_change_and_deletion_are_detected_without_losing_draft(tmp_path):
    path = tmp_path / "config"
    path.write_text("before\n")
    document = ConfigDocument.open(path)
    document.replace(0, 6, "before", "draft")

    assert not document.changed_externally()
    path.write_text("outside\n")
    assert document.changed_externally()
    assert document.draft == "draft\n"
    path.write_bytes(b"\xff")
    assert document.changed_externally()
    path.write_bytes(b"a" * (1024 * 1024 + 1))
    assert document.changed_externally()
    path.unlink()
    assert document.changed_externally()
    assert document.draft == "draft\n"


def test_diff_shows_missing_final_newlines(tmp_path):
    path = tmp_path / "config"
    path.write_text("before")
    document = ConfigDocument.open(path)
    document.replace(0, 6, "before", "after")

    diff = document.diff()
    assert "-before\n\\ No newline at end of file\n" in diff
    assert "+after\n\\ No newline at end of file\n" in diff


def test_editor_refuses_unrepresentable_text_and_preserves_crlf(tmp_path):
    path = tmp_path / "config"
    path.write_bytes(b"first\r\nsecond\r\n")
    document = ConfigDocument.open(path)
    assert document.editor_text() == "first\nsecond\n"
    document.set_editor_text("first\nchanged\n")
    assert document.draft == "first\r\nchanged\r\n"
    document.draft = "first\r\nsecond\n"
    with pytest.raises(ValueError, match="line endings"):
        document.editor_text()
    document.draft = "first\u2029second"
    with pytest.raises(ValueError, match="cannot preserve"):
        document.editor_text()

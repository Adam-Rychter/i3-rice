import shutil
import time
import threading

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPlainTextEdit

from i3_rice_gui import app
from i3_rice_gui.discovery import discover
from i3_rice_gui.validation import ValidationResult, ValidationStatus


def test_window_shows_actual_config_as_an_in_memory_draft(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("# custom\nset $mod Mod4\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    window.show()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    assert window.status == desktop
    assert window.isVisible()
    assert window.navigation.count() == 10
    assert window.heading.text() == "i3"
    assert not window.editor.isReadOnly()
    assert window.editor.toPlainText() == "# custom\nset $mod Mod4\n"
    assert "cannot be saved or applied" in window.notice.text()
    window.navigation.setCurrentRow(2)
    assert window.heading.text() == "Polybar"
    assert "Not found" in window.editor.toPlainText()
    assert config.read_text() == "# custom\nset $mod Mod4\n"
    window.close()


def test_gap_draft_sync_conflicts_and_navigation(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "# before\r\ngaps inner 10\r\n# after\r\n"
    config.write_bytes(original.encode())
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    assert window.gap_slider.isEnabled()
    assert window.gap_slider.value() == 10
    window.gap_slider.setValue(20)
    assert window.snippet.text() == "gaps inner 20"
    assert window.documents[config].draft == original.replace("10", "20")
    assert config.read_bytes() == original.encode()
    assert window.review_button.isEnabled()
    reviews = []

    def inspect_dialog(dialog):
        diff = dialog.findChild(QPlainTextEdit, "draftDiff").toPlainText()
        messages = [label.text() for label in dialog.findChildren(QLabel)]
        reviews.append((diff, messages))
        return 0

    monkeypatch.setattr(app.QDialog, "exec", inspect_dialog)
    window.review_document()
    assert "-gaps inner 10" in reviews[-1][0]
    assert "+gaps inner 20" in reviews[-1][0]
    assert "This draft is not saved or applied." in reviews[-1][1]
    window.snippet.setText("gaps inner 35")
    window.snippet.textEdited.emit(window.snippet.text())
    assert window.gap_slider.value() == 35
    assert "gaps inner 35" in window.editor.toPlainText()
    window.snippet.setText("gaps inner ")
    window.snippet.textEdited.emit(window.snippet.text())
    assert not window.gap_slider.isEnabled()
    assert not window.review_button.isEnabled()
    assert window.editor.isReadOnly()
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert window.snippet.text() == "gaps inner "
    assert "invalid" in window.gap_label.text()

    config.write_text("external change\n")
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert "changed externally" in window.file_status.text()
    assert window.snippet.text() == "gaps inner "
    window.snippet.setText("gaps inner 35")
    window.snippet.textEdited.emit(window.snippet.text())
    assert not window.editor.isReadOnly()
    window.review_document()
    assert "File changed externally; this diff uses the original baseline." in reviews[-1][1]
    window.snippet.setText("gaps inner ")
    window.snippet.textEdited.emit(window.snippet.text())
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.reload_document()
    assert window.snippet.text() == "gaps inner "
    assert window.documents[config].is_dirty
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.reload_document()
    assert window.editor.toPlainText() == "external change\n"
    assert not window.gap_slider.isEnabled()
    window.close()


def test_full_file_edit_synchronizes_and_preserves_line_endings(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "# nonbreaking\xa0space\r\ngaps inner 10\r\n# keep\r\n"
    config.write_bytes(original.encode())
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    assert not window.editor.isReadOnly()
    window.editor.setPlainText("# nonbreaking\xa0space\ngaps inner 42\n# keep\n")
    assert window.gap_slider.value() == 42
    assert window.snippet.text() == "gaps inner 42"
    assert window.documents[config].draft == original.replace("10", "42")
    assert config.read_bytes() == original.encode()
    window.gap_slider.setValue(30)
    assert window.documents[config].draft == original.replace("10", "30")
    assert "\xa0" in window.documents[config].draft
    window.editor.setPlainText("gaps inner $unsupported\n")
    assert not window.gap_slider.isEnabled()
    assert not window.editor.isReadOnly()
    window.editor.setPlainText("gaps inner 9\n")
    assert window.gap_slider.value() == 9
    window.close()


def test_mixed_line_endings_disable_full_editor(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "gaps inner 10\r\n# mixed\n"
    config.write_bytes(original.encode())
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert window.editor.isReadOnly()
    assert "line endings" in window.editor_help.text()
    window.gap_slider.setValue(20)
    assert window.documents[config].draft == original.replace("10", "20")
    assert window.editor.isReadOnly()
    assert config.read_bytes() == original.encode()
    window.close()


def test_ambiguous_gap_control_is_disabled(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\ninclude extras.conf\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert not window.gap_slider.isEnabled()
    assert "Included files" in window.setting_help.text()
    window.close()


def test_external_change_reloads_when_no_draft_exists(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    config.write_text("gaps inner 12\n")
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert window.gap_slider.value() == 12
    assert window.editor.toPlainText() == "gaps inner 12\n"
    window.close()


def test_validation_results_are_invalidated_and_stale_results_are_rejected(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        app, "validate_i3",
        lambda text: ValidationResult(ValidationStatus.INVALID, "Bad configuration.", "line 1"),
    )
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.start_validation()
    deadline = time.monotonic() + 5
    while window.validation_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert "Invalid: Bad configuration." == window.validation_status.text()
    assert window.validation_details.isEnabled()
    window.gap_slider.setValue(6)
    assert window.validation_status.text() == "Draft not validated."
    assert not window.validation_details.isEnabled()

    started = threading.Event()
    release = threading.Event()

    def delayed_validate(text):
        started.set()
        assert release.wait(5)
        return ValidationResult(ValidationStatus.VALID, "Accepted.")

    monkeypatch.setattr(app, "validate_i3", delayed_validate)
    window.start_validation()
    assert started.wait(5)
    window.gap_slider.setValue(7)
    release.set()
    deadline = time.monotonic() + 5
    while window.validation_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert "validate again" in window.validation_status.text()
    assert window.validation_result is None
    assert window.validate_button.isEnabled()
    assert config.read_text() == "gaps inner 5\n"
    window.close()


@pytest.mark.skipif(shutil.which("i3") is None, reason="i3 is not installed")
def test_gui_validation_uses_real_i3_on_the_draft(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.start_validation()
    deadline = time.monotonic() + 5
    while window.validation_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert window.validation_result.status == ValidationStatus.VALID
    window.editor.setPlainText("gaps inner invalid\n")
    window.start_validation()
    deadline = time.monotonic() + 5
    while window.validation_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert window.validation_result.status == ValidationStatus.INVALID
    assert config.read_text() == "gaps inner 5\n"
    window.close()

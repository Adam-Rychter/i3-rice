import time

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from i3_rice_gui import app
from i3_rice_gui.discovery import discover


def test_window_shows_actual_config_without_allowing_edits(tmp_path, monkeypatch):
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
    assert window.editor.isReadOnly()
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
    original = "# before\r\ngaps inner 10  # space\r\n# after\r\n"
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
    assert window.snippet.text() == "gaps inner 20  # space"
    assert window.documents[config].draft == original.replace("10", "20")
    assert config.read_bytes() == original.encode()
    window.snippet.setText("gaps inner 35 # manual")
    window.snippet.textEdited.emit(window.snippet.text())
    assert window.gap_slider.value() == 35
    assert "gaps inner 35 # manual" in window.editor.toPlainText()
    window.snippet.setText("gaps inner ")
    window.snippet.textEdited.emit(window.snippet.text())
    assert not window.gap_slider.isEnabled()
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert window.snippet.text() == "gaps inner "
    assert "invalid" in window.gap_label.text()

    config.write_text("external change\n")
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert "changed externally" in window.file_status.text()
    assert window.snippet.text() == "gaps inner "
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.reload_document()
    assert window.snippet.text() == "gaps inner "
    assert window.documents[config].is_dirty
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.reload_document()
    assert window.editor.toPlainText() == "external change\n"
    assert not window.gap_slider.isEnabled()
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

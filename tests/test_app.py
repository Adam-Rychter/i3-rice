import time

from PySide6.QtWidgets import QApplication

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
    assert "not available yet" in window.notice.text()
    window.navigation.setCurrentRow(2)
    assert window.heading.text() == "Polybar"
    assert "Not found" in window.editor.toPlainText()
    assert config.read_text() == "# custom\nset $mod Mod4\n"
    window.close()

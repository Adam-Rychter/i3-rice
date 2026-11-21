import shutil
import time
import threading

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPlainTextEdit

from i3_rice_gui import app
from i3_rice_gui.backups import BackupStore
from i3_rice_gui.discovery import discover
from i3_rice_gui.document import ConfigDocument
from i3_rice_gui.install_catalog import PackageSpec, PackageState, PackageStatus
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
    assert "reviewed and applied" in window.notice.text()
    window.navigation.setCurrentRow(2)
    assert window.heading.text() == "Polybar"
    assert "Not found" in window.editor.toPlainText()
    assert config.read_text() == "# custom\nset $mod Mod4\n"
    window.close()


def test_apt_setup_dialog_shows_reviewable_plan():
    qt_app = QApplication.instance() or QApplication([])
    statuses = (
        PackageStatus(PackageSpec("i3", "i3", "i3 window manager"), PackageState.INSTALLED),
        PackageStatus(PackageSpec("polybar", "polybar", "Polybar"), PackageState.MISSING),
    )

    dialog = app.AptSetupDialog(statuses)

    assert "Install: polybar" in dialog.plan.toPlainText()
    assert "Already installed: i3" in dialog.plan.toPlainText()
    assert dialog.checkboxes["i3"].isChecked() is True
    assert dialog.checkboxes["polybar"].isChecked() is True
    dialog.close()


def test_workspace_label_control_updates_i3_draft(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = (
        'set $ws2 "2:code"  # keep comment\n'
        'set $ws1 "1:term"\n'
        'bindsym $mod+Return exec xterm\n'
    )
    config.write_text(original)
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.navigation.setCurrentRow(1)
    assert window.workspace_controls[1].editor.text() == "1:term"
    assert window.workspace_controls[2].editor.text() == "2:code"
    assert "$mod+Return  →  exec xterm" in window.keybinding_summary.text.toPlainText()
    window.keybinding_summary.edits["$mod+Return"].setText("exec kitty")
    window.keybinding_summary.edits["$mod+Return"].textEdited.emit("exec kitty")
    assert "bindsym $mod+Return exec kitty" in window.documents[config].draft
    window.workspace_controls[2].editor.setText("2:editor")
    window.workspace_controls[2].editor.textEdited.emit("2:editor")

    assert 'set $ws2 "2:editor"  # keep comment' in window.documents[config].draft
    assert config.read_text() == original
    window.close()


def test_shared_variable_control_updates_all_references(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "set $mod Mod4\nbindsym $mod+Return exec xterm\n"
    config.write_text(original)
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    editor = window.variable_summary.edits["mod"]
    editor.setText("Mod1")
    editor.textEdited.emit("Mod1")

    assert window.documents[config].draft == "set $mod Mod1\nbindsym $mod+Return exec xterm\n"
    assert window.variable_summary.edits["mod"].text() == "Mod1"
    assert config.read_text() == original
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

    assert window.appearance_controls["inner"].slider.isEnabled()
    assert window.appearance_controls["inner"].slider.value() == 10
    window.appearance_controls["inner"].slider.setValue(20)
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner 20"
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
    window.appearance_controls["inner"].snippet.setText("gaps inner 35")
    window.appearance_controls["inner"].snippet.textEdited.emit(window.appearance_controls["inner"].snippet.text())
    assert window.appearance_controls["inner"].slider.value() == 35
    assert "gaps inner 35" in window.editor.toPlainText()
    window.appearance_controls["inner"].snippet.setText("gaps inner ")
    window.appearance_controls["inner"].snippet.textEdited.emit(window.appearance_controls["inner"].snippet.text())
    assert not window.appearance_controls["inner"].slider.isEnabled()
    assert not window.review_button.isEnabled()
    assert window.editor.isReadOnly()
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner "
    assert "invalid" in window.appearance_controls["inner"].label.text()

    config.write_text("external change\n")
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert "changed externally" in window.file_status.text()
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner "
    window.appearance_controls["inner"].snippet.setText("gaps inner 35")
    window.appearance_controls["inner"].snippet.textEdited.emit(window.appearance_controls["inner"].snippet.text())
    assert not window.editor.isReadOnly()
    window.review_document()
    assert "File changed externally; this diff uses the original baseline." in reviews[-1][1]
    window.appearance_controls["inner"].snippet.setText("gaps inner ")
    window.appearance_controls["inner"].snippet.textEdited.emit(window.appearance_controls["inner"].snippet.text())
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.reload_document()
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner "
    assert window.documents[config].is_dirty
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.reload_document()
    assert window.editor.toPlainText() == "external change\n"
    assert not window.appearance_controls["inner"].slider.isEnabled()
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
    assert window.appearance_controls["inner"].slider.value() == 42
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner 42"
    assert window.documents[config].draft == original.replace("10", "42")
    assert config.read_bytes() == original.encode()
    window.appearance_controls["inner"].slider.setValue(30)
    assert window.documents[config].draft == original.replace("10", "30")
    assert "\xa0" in window.documents[config].draft
    window.editor.setPlainText("gaps inner $unsupported\n")
    assert not window.appearance_controls["inner"].slider.isEnabled()
    assert not window.editor.isReadOnly()
    window.editor.setPlainText("gaps inner 9\n")
    assert window.appearance_controls["inner"].slider.value() == 9
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
    window.appearance_controls["inner"].slider.setValue(20)
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
    assert not window.appearance_controls["inner"].slider.isEnabled()
    assert "Included files" in window.appearance_controls["inner"].help.text()
    window.close()


def test_independent_appearance_drafts_survive_navigation_and_conflict(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "gaps inner 5\ngaps outer 4\ndefault_border pixel 2\n"
    config.write_text(original)
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    inner, outer, border = (window.appearance_controls[k]
                            for k in ("inner", "outer", "pixel_border"))
    outer.slider.setValue(-10)
    border.slider.setValue(0)
    assert outer.snippet.text() == "gaps outer -10"
    assert border.snippet.text() == "default_border pixel 0"
    assert window.documents[config].draft == original.replace("outer 4", "outer -10").replace(
        "pixel 2", "pixel 0"
    )
    for control, text in ((outer, "gaps outer -"), (border, "default_border pixel ")):
        control.snippet.setText(text)
        control.snippet.textEdited.emit(text)
    assert not outer.slider.isEnabled() and not border.slider.isEnabled()
    assert inner.slider.isEnabled()
    assert not window.validate_button.isEnabled() and not window.review_button.isEnabled()
    assert window.editor.isReadOnly()
    inner.slider.setValue(8)
    assert window.snippets[config] == {
        "outer": "gaps outer -", "pixel_border": "default_border pixel "
    }

    config.write_text("external change\n")
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(0)
    assert "changed externally" in window.file_status.text()
    assert outer.snippet.text() == "gaps outer -"
    assert border.snippet.text() == "default_border pixel "
    outer.snippet.setText("gaps outer -12")
    outer.snippet.textEdited.emit(outer.snippet.text())
    assert outer.slider.value() == -12
    assert window.editor.isReadOnly()
    assert not window.validate_button.isEnabled()
    border.snippet.setText("default_border pixel 3")
    border.snippet.textEdited.emit(border.snippet.text())
    assert border.slider.value() == 3
    assert not window.editor.isReadOnly()
    assert window.validate_button.isEnabled() and window.review_button.isEnabled()
    assert window.documents[config].draft == (
        "gaps inner 8\ngaps outer -12\ndefault_border pixel 3\n"
    )
    assert config.read_text() == "external change\n"
    window.close()


def test_full_file_updates_only_supported_appearance_controls(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    original = "gaps inner 5\ngaps outer -10\ndefault_border pixel 2\n"
    config.write_text(original)
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    inner, outer, border = (window.appearance_controls[k]
                            for k in ("inner", "outer", "pixel_border"))
    window.editor.setPlainText("gaps inner 7\ngaps outer -22\ndefault_border normal 3\n")
    assert inner.slider.value() == 7 and outer.slider.value() == -22
    assert not border.slider.isEnabled() and not window.editor.isReadOnly()
    window.editor.setPlainText(
        "gaps inner 7\ngaps outer 4\ngaps outer 8\ndefault_border pixel 4\n"
    )
    assert inner.slider.isEnabled() and not outer.slider.isEnabled()
    assert border.slider.value() == 4
    window.editor.setPlainText(original + "include extra\n")
    assert all(not control.slider.isEnabled() for control in window.appearance_controls.values())
    assert config.read_text() == original
    window.close()


def test_polybar_height_draft_navigation_conflicts_and_full_file_edit(tmp_path, monkeypatch):
    config = tmp_path / ".config/polybar/config.ini"
    config.parent.mkdir(parents=True)
    original = "[bar/main]\r\nheight = 56\r\n[bar/secondary]\r\ninherit = bar/main\r\n"
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

    window.navigation.setCurrentRow(2)
    height = window.appearance_controls["bar_height"]
    assert height.slider.isEnabled() and height.slider.value() == 56
    assert not height.isHidden()
    assert window.appearance_controls["inner"].isHidden()
    assert "bar/main, bar/secondary" in height.help.text()
    assert not window.validate_button.isEnabled()
    height.slider.setValue(42)
    assert height.snippet.text() == "height = 42"
    assert window.documents[config].draft == original.replace("56", "42")
    height.snippet.setText("height = ")
    height.snippet.textEdited.emit(height.snippet.text())
    assert not height.slider.isEnabled() and not window.review_button.isEnabled()
    assert window.editor.isReadOnly()
    config.write_text("[bar/main]\nheight = 99\n")
    window.navigation.setCurrentRow(0)
    assert height.isHidden()
    assert not window.appearance_controls["inner"].isHidden()
    window.navigation.setCurrentRow(2)
    assert height.snippet.text() == "height = "
    assert "changed externally" in window.file_status.text()
    height.snippet.setText("height = 33")
    height.snippet.textEdited.emit(height.snippet.text())
    assert height.slider.value() == 33 and window.review_button.isEnabled()
    assert window.documents[config].draft == original.replace("56", "33")
    window.editor.setPlainText("[bar/main]\nheight = 8%\n")
    assert not height.slider.isEnabled() and not window.editor.isReadOnly()
    window.editor.setPlainText("[bar/main]\nheight = 25\n")
    assert height.slider.value() == 25
    assert config.read_text() == "[bar/main]\nheight = 99\n"
    window.close()


def test_picom_radius_controls_are_independent_and_draft_only(tmp_path, monkeypatch):
    config = tmp_path / ".config/picom/picom.conf"
    config.parent.mkdir(parents=True)
    original = 'shadow-radius = 8;\r\ncorner-radius = 16;\r\nshadow-exclude = ["dock"];\r\n'
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

    window.navigation.setCurrentRow(4)
    corner = window.appearance_controls["picom_corner-radius"]
    shadow = window.appearance_controls["picom_shadow-radius"]
    assert corner.slider.value() == 16 and shadow.slider.value() == 8
    assert "window exclusions" in corner.help.text()
    assert not window.validate_button.isEnabled()
    corner.slider.setValue(20)
    shadow.snippet.setText("shadow-radius = ")
    shadow.snippet.textEdited.emit(shadow.snippet.text())
    assert corner.slider.isEnabled() and not shadow.slider.isEnabled()
    assert window.editor.isReadOnly() and not window.review_button.isEnabled()
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(4)
    assert shadow.snippet.text() == "shadow-radius = "
    shadow.snippet.setText("shadow-radius = 12;")
    shadow.snippet.textEdited.emit(shadow.snippet.text())
    assert window.documents[config].draft == original.replace("16", "20").replace("8", "12")
    assert window.review_button.isEnabled() and not window.editor.isReadOnly()
    window.editor.setPlainText("shadow-radius = 9;\ncorner-radius = $dynamic;\n")
    assert shadow.slider.value() == 9 and not corner.slider.isEnabled()
    assert config.read_bytes() == original.encode()
    window.close()


def test_dunst_color_picker_and_snippets_remain_draft_only(tmp_path, monkeypatch):
    config = tmp_path / ".config/dunst/dunstrc"
    config.parent.mkdir(parents=True)
    original = (
        '[global]\r\nframe_color = "#89b4fa"\r\n'
        '[urgency_normal]\r\nframe_color = "#aabbcc"\r\n'
    )
    config.write_bytes(original.encode())
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(app.QColorDialog, "getColor", lambda *args: QColor("#123456"))
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.navigation.setCurrentRow(5)
    global_color = window.color_controls["dunst_global"]
    normal = window.color_controls["dunst_urgency_normal"]
    assert global_color.button.isEnabled() and normal.button.isEnabled()
    assert "Other rules or drop-in files" in global_color.help.text()
    global_color.button.click()
    assert global_color.snippet.text() == 'frame_color = "#123456"'
    assert normal.snippet.text() == 'frame_color = "#aabbcc"'
    normal.snippet.setText('frame_color = "#')
    normal.snippet.textEdited.emit(normal.snippet.text())
    assert not normal.button.isEnabled() and global_color.button.isEnabled()
    assert window.editor.isReadOnly() and not window.review_button.isEnabled()
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(5)
    assert normal.snippet.text() == 'frame_color = "#'
    normal.snippet.setText('frame_color = "#abcdef"')
    normal.snippet.textEdited.emit(normal.snippet.text())
    assert window.documents[config].draft == original.replace("#89b4fa", "#123456").replace(
        "#aabbcc", "#abcdef"
    )
    assert window.review_button.isEnabled() and not window.editor.isReadOnly()
    window.editor.setPlainText('[global]\nframe_color = "red"\n')
    assert not global_color.button.isEnabled() and not window.editor.isReadOnly()
    assert config.read_bytes() == original.encode()
    window.close()


def test_color_picker_discards_stale_choice_and_cancel(tmp_path, monkeypatch):
    config = tmp_path / ".config/dunst/dunstrc"
    config.parent.mkdir(parents=True)
    config.write_text('[global]\nframe_color = "#112233"\n')
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    window.navigation.setCurrentRow(5)
    color = window.color_controls["dunst_global"]
    monkeypatch.setattr(app.QColorDialog, "getColor", lambda *args: QColor())
    color.button.click()
    assert not window.documents[config].is_dirty

    def change_draft(*args):
        window.editor.setPlainText('[global]\nframe_color = "#445566"\n')
        return QColor("#abcdef")

    monkeypatch.setattr(app.QColorDialog, "getColor", change_draft)
    color.button.click()
    assert window.documents[config].draft == '[global]\nframe_color = "#445566"\n'
    assert "choose the color again" in window.file_status.text()
    assert config.read_text() == '[global]\nframe_color = "#112233"\n'
    window.close()


def test_rofi_theme_radius_draft_and_navigation(tmp_path, monkeypatch):
    root = tmp_path / ".config/rofi"
    root.mkdir(parents=True)
    config = root / "config.rasi"
    config.write_text('@import "catppuccin-mocha.rasi"\n')
    theme = root / "catppuccin-mocha.rasi"
    original = "window {\r\n    border-radius: 16px;\r\n}\r\n"
    theme.write_bytes(original.encode())
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.navigation.setCurrentRow(3)
    radius = window.appearance_controls["rofi_window_radius"]
    assert not radius.slider.isEnabled()
    assert "Imports" in radius.help.text()
    window.config_select.setCurrentIndex(1)
    assert radius.slider.isEnabled() and radius.slider.value() == 16
    assert "other theme files may override" in radius.help.text()
    radius.slider.setValue(20)
    assert window.documents[theme].draft == original.replace("16", "20")
    radius.snippet.setText("border-radius: ")
    radius.snippet.textEdited.emit(radius.snippet.text())
    assert not radius.slider.isEnabled() and window.editor.isReadOnly()
    window.navigation.setCurrentRow(0)
    window.navigation.setCurrentRow(3)
    window.config_select.setCurrentIndex(1)
    assert radius.snippet.text() == "border-radius: "
    radius.snippet.setText("border-radius: 30px;")
    radius.snippet.textEdited.emit(radius.snippet.text())
    assert radius.slider.value() == 30 and window.review_button.isEnabled()
    window.editor.setPlainText("window {\n    border-radius: 3em;\n}\n")
    assert not radius.slider.isEnabled() and not window.editor.isReadOnly()
    assert theme.read_bytes() == original.encode()
    assert config.read_text() == '@import "catppuccin-mocha.rasi"\n'
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
    assert window.appearance_controls["inner"].slider.value() == 12
    assert window.editor.toPlainText() == "gaps inner 12\n"
    window.close()


def test_monitoring_reloads_clean_files_and_preserves_drafts_on_atomic_replace(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert predicate()

    wait_for(lambda: window.status is not None)
    assert str(config) in window.file_watcher.files()
    config.write_text("gaps inner 10\n")
    wait_for(lambda: window.appearance_controls["inner"].slider.value() == 10)
    assert not window.documents[config].is_dirty

    window.appearance_controls["inner"].slider.setValue(20)
    replacement = config.with_name("replacement")
    replacement.write_text("gaps inner 30\n")
    replacement.replace(config)
    wait_for(lambda: "changed externally" in window.file_status.text())
    assert window.documents[config].draft == "gaps inner 20\n"
    assert config.read_text() == "gaps inner 30\n"
    wait_for(lambda: str(config) in window.file_watcher.files())

    revision = window.validation_revision
    config.write_text("gaps inner 40\n")
    wait_for(lambda: window.validation_revision > revision)
    assert window.documents[config].draft == "gaps inner 20\n"
    assert config.read_text() == "gaps inner 40\n"
    window.close()


def test_monitoring_preserves_clean_baseline_when_file_is_deleted(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert predicate()

    wait_for(lambda: window.status is not None)
    config.unlink()
    wait_for(lambda: "unable to reload" in window.file_status.text())
    assert window.documents[config].draft == "gaps inner 5\n"
    assert "File missing" in window.watch_status.text()
    config.write_text("gaps inner 11\n")
    wait_for(lambda: window.appearance_controls["inner"].slider.value() == 11)
    assert window.documents[config].draft == "gaps inner 11\n"
    window.close()


def test_monitoring_failure_is_visible(tmp_path, monkeypatch):
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
    monkeypatch.setattr(window.file_watcher, "addPath", lambda path: False)
    window.watch_file(config)
    assert "monitoring unavailable" in window.watch_status.text()
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
    window.appearance_controls["inner"].slider.setValue(6)
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
    window.appearance_controls["inner"].slider.setValue(7)
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


def test_backup_button_saves_disk_baseline_without_saving_draft(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    store = BackupStore(tmp_path / "backups")
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    window.appearance_controls["inner"].slider.setValue(20)
    window.start_backup()
    deadline = time.monotonic() + 5
    while window.backup_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert "created" in window.backup_status.text()
    record = store.list(config)[0]
    assert store.read(record) == b"gaps inner 5\n"
    assert window.documents[config].draft == "gaps inner 20\n"
    assert config.read_text() == "gaps inner 5\n"

    config.write_text("external change\n")
    window.start_backup()
    deadline = time.monotonic() + 5
    while window.backup_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert "changed externally" in window.backup_status.text()
    assert len(store.list(config)) == 1
    assert config.read_text() == "external change\n"
    window.close()


def test_review_backup_loads_a_draft_without_changing_disk(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    config.write_text("gaps inner 12\n")
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    previews = []

    def accept_browser(browser):
        previews.append(browser.diff.toPlainText())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(app.BackupBrowser, "exec", accept_browser)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert "-gaps inner 12" in previews[0]
    assert "+gaps inner 5" in previews[0]
    assert window.appearance_controls["inner"].slider.value() == 5
    assert window.documents[config].draft == "gaps inner 5\n"
    assert config.read_text() == "gaps inner 12\n"
    assert "disk file was not changed" in window.backup_status.text()
    window.close()


def test_backup_equal_to_baseline_stays_staged_during_external_conflict(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(app.BackupBrowser, "exec", lambda self: QDialog.DialogCode.Accepted)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert predicate()

    wait_for(lambda: window.status is not None)
    window.appearance_controls["inner"].slider.setValue(20)
    config.write_text("gaps inner 30\n")
    wait_for(lambda: "changed externally" in window.file_status.text())
    window.start_browsing_backups()
    wait_for(lambda: window.browse_task is None)
    assert window.documents[config].draft == window.documents[config].baseline
    assert config in window.staged_backups
    assert window.has_pending_changes(config)
    revision = window.validation_revision
    config.write_text("gaps inner 40\n")
    wait_for(lambda: window.validation_revision > revision)
    assert window.documents[config].draft == "gaps inner 5\n"
    assert config.read_text() == "gaps inner 40\n"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.reload_document()
    assert config in window.staged_backups
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.reload_document()
    assert config not in window.staged_backups
    assert window.appearance_controls["inner"].slider.value() == 40
    window.close()


def test_backup_review_rejects_changes_during_dialog(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)

    def change_draft(browser):
        window.editor.setPlainText("gaps inner 9\n")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(app.BackupBrowser, "exec", change_draft)
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert window.documents[config].draft == "gaps inner 9\n"
    assert "review backups again" in window.backup_status.text()
    assert config.read_text() == "gaps inner 5\n"
    window.close()


def test_backup_review_rejects_invalid_snippet_changes_during_dialog(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\ngaps outer 4\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    outer = window.appearance_controls["outer"]
    outer.snippet.setText("gaps outer -")
    outer.snippet.textEdited.emit(outer.snippet.text())

    def change_snippet(browser):
        outer.snippet.setText("gaps outer --")
        outer.snippet.textEdited.emit(outer.snippet.text())
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(app.BackupBrowser, "exec", change_snippet)
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert outer.snippet.text() == "gaps outer --"
    assert "review backups again" in window.backup_status.text()
    assert config not in window.staged_backups
    window.close()


def test_declining_backup_load_keeps_invalid_snippet(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(app.BackupBrowser, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    window.appearance_controls["inner"].snippet.setText("gaps inner ")
    window.appearance_controls["inner"].snippet.textEdited.emit(window.appearance_controls["inner"].snippet.text())
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert window.appearance_controls["inner"].snippet.text() == "gaps inner "
    assert config in window.snippets
    assert config not in window.staged_backups
    assert config.read_text() == "gaps inner 5\n"
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.close()


def test_missing_config_backup_load_stays_in_memory_and_detects_new_file(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_bytes(b"gaps inner 5\r\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    config.unlink()
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(app.BackupBrowser, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()

    def wait_for(predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert predicate()

    wait_for(lambda: window.status is not None)
    assert window.browse_button.isEnabled()
    assert not window.backup_button.isEnabled()
    window.update_validation_controls()
    assert not window.validate_button.isEnabled()
    window.start_browsing_backups()
    wait_for(lambda: window.browse_task is None)
    assert not config.exists()
    assert window.documents[config].draft == "gaps inner 5\r\n"
    assert not window.documents[config].baseline_exists
    assert window.appearance_controls["inner"].slider.value() == 5
    assert config in window.staged_backups
    window.editor.setPlainText("gaps inner 6\n")
    assert window.documents[config].draft == "gaps inner 6\r\n"

    config.write_text("gaps inner 9\n")
    wait_for(lambda: "changed externally" in window.file_status.text())
    assert window.documents[config].draft == "gaps inner 6\r\n"
    assert config.read_text() == "gaps inner 9\n"
    window.reload_document()
    assert window.documents[config].baseline_exists
    assert window.appearance_controls["inner"].slider.value() == 9
    window.close()


def test_missing_config_draft_can_be_discarded_without_creating_file(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    config.unlink()
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(app.BackupBrowser, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert config in window.staged_backups
    window.reload_document()
    assert config not in window.documents
    assert config not in window.staged_backups
    assert not config.exists()
    assert window.browse_button.isEnabled()
    window.close()


def test_missing_config_appearing_during_confirmation_is_not_overwritten(tmp_path, monkeypatch):
    config = tmp_path / ".config/i3/config"
    config.parent.mkdir(parents=True)
    config.write_text("gaps inner 5\n")
    store = BackupStore(tmp_path / "backups")
    store.create(ConfigDocument.open(config))
    config.unlink()
    desktop = discover(tmp_path, {"PATH": "", "DISPLAY": ":1"})
    monkeypatch.setattr(app, "discover", lambda: desktop)
    monkeypatch.setattr(app, "BackupStore", lambda: store)
    monkeypatch.setattr(app.BackupBrowser, "exec", lambda self: QDialog.DialogCode.Accepted)

    def file_appears(*args):
        config.write_text("gaps inner 99\n")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", file_appears)
    qt_app = QApplication.instance() or QApplication([])
    window = app.MainWindow()
    deadline = time.monotonic() + 5
    while window.status is None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    window.start_browsing_backups()
    deadline = time.monotonic() + 5
    while window.browse_task is not None and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert config.read_text() == "gaps inner 99\n"
    assert config not in window.documents
    assert "file appeared" in window.backup_status.text().lower()
    window.close()

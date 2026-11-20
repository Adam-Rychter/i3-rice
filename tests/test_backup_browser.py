from PySide6.QtWidgets import QApplication, QLabel

from i3_rice_gui.backup_browser import BackupBrowser
from i3_rice_gui.backups import BackupStore
from i3_rice_gui.document import ConfigDocument


def test_backup_selection_updates_comparison(tmp_path):
    source = tmp_path / "config"
    store = BackupStore(tmp_path / "backups")
    for text in ("first\n", "second\n"):
        source.write_text(text)
        store.create(ConfigDocument.open(source))
    qt_app = QApplication.instance() or QApplication([])
    browser = BackupBrowser(source, "current\n", store.versions(source), True)
    assert "-current" in browser.diff.toPlainText()
    assert "+second" in browser.diff.toPlainText()
    assert any("invalid snippet" in label.text() for label in browser.findChildren(QLabel))
    browser.selection.setCurrentIndex(1)
    assert "+first" in browser.diff.toPlainText()
    assert browser.selected_version().text == "first\n"
    browser.close()
    qt_app.processEvents()

"""Prototype shell with in-memory configuration drafts."""

from pathlib import Path
import sys

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSlider, QSplitter,
    QVBoxLayout, QWidget,
)

from .discovery import DesktopStatus, discover
from .document import ConfigDocument
from .i3_gaps import MAX_GAP, find_inner_gap, parse_gap_line, replace_gap_value


STYLE = """
QWidget { background: #1e1e2e; color: #cdd6f4; font-size: 13px; }
QFrame#sidebar { background: #181825; border-right: 1px solid #313244; }
QFrame#card { background: #242438; border: 1px solid #393950; border-radius: 12px; }
QLabel#brand { color: #cdd6f4; font-size: 20px; font-weight: 700; }
QLabel#eyebrow { color: #89b4fa; font-size: 11px; font-weight: 700; }
QLabel#heading { font-size: 25px; font-weight: 700; }
QLabel#section { font-size: 16px; font-weight: 700; }
QLabel#muted { color: #a6adc8; }
QLabel#notice { color: #f9e2af; background: #343044; border-radius: 7px; padding: 10px; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 10px 12px; border-radius: 7px; color: #a6adc8; }
QListWidget::item:selected { background: #45475a; color: #cdd6f4; }
QListWidget::item:hover:!selected { background: #313244; }
QPushButton { background: #45475a; border: none; border-radius: 7px; padding: 8px 14px; }
QPushButton:hover { background: #585b70; }
QPushButton:disabled { color: #6c7086; background: #313244; }
QComboBox { background: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 6px; }
QPlainTextEdit { background: #181825; border: 1px solid #45475a; border-radius: 7px;
                 selection-background-color: #585b70; }
QSplitter::handle { background: #1e1e2e; width: 10px; }
"""


class ScanSignals(QObject):
    complete = Signal(object)
    error = Signal(str)


class Scan(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = ScanSignals()

    def run(self) -> None:
        try:
            result = discover()
        except (OSError, ValueError) as exc:
            self.signals.error.emit(f"Discovery failed: {exc}")
        else:
            self.signals.complete.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.status: DesktopStatus | None = None
        self.scanner: Scan | None = None
        self.documents: dict[Path, ConfigDocument] = {}
        self.snippets: dict[Path, str] = {}
        self.current_path: Path | None = None
        self.setWindowTitle("i3 Rice Studio")
        self.resize(1180, 760)
        self.setMinimumSize(820, 540)
        self.setStyleSheet(STYLE)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 20)
        brand = QLabel("i3  /  RICE STUDIO")
        brand.setObjectName("brand")
        side.addWidget(brand)
        subtitle = QLabel("DESKTOP CONFIGURATOR")
        subtitle.setObjectName("eyebrow")
        side.addWidget(subtitle)
        side.addSpacing(25)
        label = QLabel("COMPONENTS")
        label.setObjectName("muted")
        side.addWidget(label)
        self.navigation = QListWidget()
        self.navigation.currentRowChanged.connect(self.show_component)
        side.addWidget(self.navigation, 1)
        self.refresh = QPushButton("Refresh discovery")
        self.refresh.clicked.connect(self.start_scan)
        side.addWidget(self.refresh)
        layout.addWidget(sidebar)

        main = QWidget()
        content = QVBoxLayout(main)
        content.setContentsMargins(30, 26, 30, 26)
        content.setSpacing(14)
        self.session = QLabel("Scanning desktop…")
        self.session.setObjectName("eyebrow")
        self.session.setTextFormat(Qt.TextFormat.PlainText)
        content.addWidget(self.session)
        self.heading = QLabel("Your desktop, in detail")
        self.heading.setObjectName("heading")
        content.addWidget(self.heading)
        self.description = QLabel("Discover your current setup without changing it.")
        self.description.setObjectName("muted")
        content.addWidget(self.description)
        self.notice = QLabel(
            "Draft-only prototype · Changes stay in memory and cannot be saved or applied."
        )
        self.notice.setWordWrap(True)
        self.notice.setObjectName("notice")
        content.addWidget(self.notice)

        splitter = QSplitter()
        self.details = self.make_card()
        detail_layout = QVBoxLayout(self.details)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_title = QLabel("Component status")
        detail_title.setObjectName("section")
        detail_layout.addWidget(detail_title)
        self.component_status = QLabel("Select a component.")
        self.component_status.setWordWrap(True)
        self.component_status.setTextFormat(Qt.TextFormat.PlainText)
        detail_layout.addWidget(self.component_status)
        detail_layout.addSpacing(16)
        settings_title = QLabel("Settings")
        settings_title.setObjectName("section")
        detail_layout.addWidget(settings_title)
        self.setting_help = QLabel("Select an i3 configuration to edit its inner gap.")
        self.setting_help.setObjectName("muted")
        self.setting_help.setWordWrap(True)
        detail_layout.addWidget(self.setting_help)
        self.gap_slider = QSlider(Qt.Orientation.Horizontal)
        self.gap_slider.setRange(0, MAX_GAP)
        self.gap_slider.setEnabled(False)
        self.gap_slider.valueChanged.connect(self.change_gap)
        detail_layout.addWidget(self.gap_slider)
        self.gap_label = QLabel("Inner gap: unavailable")
        detail_layout.addWidget(self.gap_label)
        self.snippet = QLineEdit()
        self.snippet.setMaxLength(1024 * 1024)
        self.snippet.setPlaceholderText("Relevant configuration line")
        self.snippet.setEnabled(False)
        self.snippet.textEdited.connect(self.edit_snippet)
        detail_layout.addWidget(self.snippet)
        detail_layout.addStretch()
        splitter.addWidget(self.details)

        editor_card = self.make_card()
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Configuration")
        title.setObjectName("section")
        editor_layout.addWidget(title)
        editor_help = QLabel("Full-file draft · read-only")
        editor_help.setObjectName("muted")
        editor_layout.addWidget(editor_help)
        self.config_select = QComboBox()
        self.config_select.currentIndexChanged.connect(self.show_config)
        editor_layout.addWidget(self.config_select)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("monospace", 10))
        self.editor.setPlaceholderText("Select an existing configuration file.")
        editor_layout.addWidget(self.editor, 1)
        self.file_status = QLabel("No configuration selected.")
        self.file_status.setWordWrap(True)
        self.file_status.setObjectName("muted")
        editor_layout.addWidget(self.file_status)
        self.reload_button = QPushButton("Reload file / discard draft")
        self.reload_button.setEnabled(False)
        self.reload_button.clicked.connect(self.reload_document)
        editor_layout.addWidget(self.reload_button)
        splitter.addWidget(editor_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        content.addWidget(splitter, 1)
        layout.addWidget(main, 1)
        self.start_scan()

    @staticmethod
    def make_card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def start_scan(self) -> None:
        self.refresh.setEnabled(False)
        self.session.setText("SCANNING DESKTOP…")
        self.scanner = Scan()
        self.scanner.signals.complete.connect(self.finish_scan)
        self.scanner.signals.error.connect(self.scan_failed)
        QThreadPool.globalInstance().start(self.scanner)

    def scan_failed(self, message: str) -> None:
        self.refresh.setEnabled(True)
        self.session.setText("DISCOVERY FAILED")
        self.notice.setText(message)

    def finish_scan(self, result: DesktopStatus) -> None:
        selected = self.navigation.currentRow()
        self.status = result
        self.session.setText(f"{result.session.upper()}  ·  {result.desktop.upper()}")
        self.notice.setText(
            "Draft-only prototype · Changes stay in memory and cannot be saved or applied."
        )
        self.navigation.blockSignals(True)
        self.navigation.clear()
        self.navigation.addItems([item.component.title for item in result.components])
        self.navigation.blockSignals(False)
        self.refresh.setEnabled(True)
        self.navigation.setCurrentRow(selected if 0 <= selected < len(result.components) else 0)
        self.show_component(self.navigation.currentRow())

    def show_component(self, index: int) -> None:
        if self.status is None or not 0 <= index < len(self.status.components):
            return
        item = self.status.components[index]
        self.heading.setText(item.component.title)
        self.description.setText(item.component.description)
        lines = [
            f"{name}: {path if path else 'Not found in PATH'}"
            for name, path in item.executables
        ]
        lines.append("")
        lines.append("Executable detection does not identify its package or running state.")
        lines.extend(f"\n{path}\n{status}" for path, status in item.configs)
        self.component_status.setText("\n".join(lines))
        self.config_select.blockSignals(True)
        self.config_select.clear()
        for path, status in item.configs:
            self.config_select.addItem(f"{path}  —  {status}", (path, status))
        self.config_select.blockSignals(False)
        self.show_config()

    def show_config(self) -> None:
        data = self.config_select.currentData()
        self.editor.clear()
        self.current_path = None
        self.reload_button.setEnabled(False)
        self.clear_gap("Select an i3 configuration to edit its inner gap.")
        if not data:
            return
        path, status = data
        if status != "Found" and path not in self.documents:
            self.editor.setPlainText(f"Configuration unavailable: {status}")
            self.file_status.setText(f"Configuration unavailable: {status}")
            return
        reload_error = None
        try:
            if path not in self.documents:
                self.documents[path] = ConfigDocument.open(path)
            document = self.documents[path]
            changed = document.changed_externally()
            if changed and not document.is_dirty and path not in self.snippets:
                try:
                    replacement = ConfigDocument.open(path)
                except (OSError, ValueError) as exc:
                    reload_error = str(exc)
                else:
                    self.documents[path] = document = replacement
                    changed = False
        except (OSError, ValueError) as exc:
            self.editor.setPlainText(f"Unable to read configuration: {exc}")
            self.file_status.setText(f"Unable to inspect configuration: {exc}")
            return
        self.current_path = path
        self.reload_button.setEnabled(True)
        self.editor.setPlainText(document.draft)
        self.update_file_status(changed)
        if reload_error:
            self.file_status.setText(f"External change detected; unable to reload: {reload_error}")
        if self.status and self.status.components[self.navigation.currentRow()].component.key == "i3":
            self.update_gap()

    def clear_gap(self, message: str) -> None:
        self.gap_slider.setEnabled(False)
        self.gap_label.setText("Inner gap: unavailable")
        self.snippet.blockSignals(True)
        self.snippet.clear()
        self.snippet.blockSignals(False)
        self.snippet.setEnabled(False)
        self.setting_help.setText(message)

    def update_file_status(self, changed: bool | None = None) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        try:
            changed = document.changed_externally() if changed is None else changed
        except OSError as exc:
            self.file_status.setText(f"Unable to check external changes: {exc}")
            return
        dirty = document.is_dirty or self.current_path in self.snippets
        if changed:
            self.file_status.setText("File changed externally. Draft retained; reload to discard it.")
        elif dirty:
            self.file_status.setText("Unsaved in-memory draft. The file on disk is unchanged.")
        else:
            self.file_status.setText("Original file. No in-memory changes.")

    def update_gap(self) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        try:
            setting = find_inner_gap(document.draft)
        except ValueError as exc:
            self.clear_gap(str(exc))
            return
        snippet = self.snippets.get(self.current_path, setting.line)
        self.snippet.blockSignals(True)
        self.snippet.setText(snippet)
        self.snippet.blockSignals(False)
        self.snippet.setEnabled(True)
        try:
            value = parse_gap_line(snippet)
        except ValueError as exc:
            self.gap_slider.setEnabled(False)
            self.gap_label.setText("Inner gap: invalid draft")
            self.setting_help.setText(str(exc))
            return
        self.gap_slider.blockSignals(True)
        self.gap_slider.setValue(value)
        self.gap_slider.blockSignals(False)
        self.gap_slider.setEnabled(True)
        self.gap_label.setText(f"Inner gap: {value}px")
        self.setting_help.setText("Edit the line or move the slider. Changes are draft only.")

    def edit_snippet(self, text: str) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        self.snippets[path] = text
        try:
            parse_gap_line(text)
            setting = find_inner_gap(document.draft)
            document.replace(setting.start, setting.end, setting.line, text)
        except ValueError as exc:
            self.gap_slider.setEnabled(False)
            self.gap_label.setText("Inner gap: invalid draft")
            self.setting_help.setText(str(exc))
        else:
            self.snippets.pop(path)
            self.editor.setPlainText(document.draft)
            self.update_gap()
        self.update_file_status()

    def change_gap(self, value: int) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        try:
            setting = find_inner_gap(document.draft)
            replacement = replace_gap_value(setting.line, value)
            document.replace(setting.start, setting.end, setting.line, replacement)
        except ValueError as exc:
            self.clear_gap(str(exc))
            return
        self.editor.setPlainText(document.draft)
        self.update_gap()
        self.update_file_status()

    def reload_document(self) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        if document.is_dirty or path in self.snippets:
            answer = QMessageBox.question(
                self, "Discard draft?",
                "Reloading discards this in-memory draft. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            replacement = ConfigDocument.open(path)
        except (OSError, ValueError) as exc:
            self.file_status.setText(f"Unable to reload configuration: {exc}")
            return
        self.documents[path] = replacement
        self.snippets.pop(path, None)
        self.show_config()

    def closeEvent(self, event) -> None:
        if self.snippets or any(document.is_dirty for document in self.documents.values()):
            answer = QMessageBox.question(
                self, "Discard drafts?",
                "Closing discards all in-memory drafts. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("i3 Rice Studio")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

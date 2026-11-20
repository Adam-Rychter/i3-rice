"""Prototype shell with in-memory configuration drafts."""

from pathlib import Path
import sys

from PySide6.QtCore import QFileSystemWatcher, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from .backups import BACKUP_LIMIT, BackupError, BackupResult, BackupStore, default_backup_root
from .discovery import DesktopStatus, discover
from .document import ConfigDocument
from .i3_gaps import MAX_GAP, find_inner_gap, parse_gap_line, replace_gap_value
from .validation import ValidationResult, ValidationStatus, validate_i3


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


class ValidationSignals(QObject):
    complete = Signal(object)


class ValidationTask(QRunnable):
    def __init__(self, path: Path, text: str, revision: int) -> None:
        super().__init__()
        self.path = path
        self.text = text
        self.revision = revision
        self.signals = ValidationSignals()

    def run(self) -> None:
        self.signals.complete.emit(validate_i3(self.text))


class BackupSignals(QObject):
    complete = Signal(object)
    error = Signal(str)


class BackupTask(QRunnable):
    def __init__(self, document: ConfigDocument) -> None:
        super().__init__()
        self.document = document
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            result = BackupStore().create(self.document)
        except (BackupError, OSError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.status: DesktopStatus | None = None
        self.scanner: Scan | None = None
        self.validation_task: ValidationTask | None = None
        self.validation_result: ValidationResult | None = None
        self.validation_revision = 0
        self.backup_task: BackupTask | None = None
        self.documents: dict[Path, ConfigDocument] = {}
        self.snippets: dict[Path, str] = {}
        self.current_path: Path | None = None
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self.schedule_file_check)
        self.file_watcher.directoryChanged.connect(self.schedule_file_check)
        self.file_check_timer = QTimer(self)
        self.file_check_timer.setSingleShot(True)
        self.file_check_timer.setInterval(150)
        self.file_check_timer.timeout.connect(self.check_external_change)
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
            "Draft-only prototype · Edits stay in memory and cannot be saved or applied."
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
        self.editor_help = QLabel("Full-file draft")
        self.editor_help.setObjectName("muted")
        self.editor_help.setWordWrap(True)
        editor_layout.addWidget(self.editor_help)
        self.config_select = QComboBox()
        self.config_select.currentIndexChanged.connect(self.show_config)
        editor_layout.addWidget(self.config_select)
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setFont(QFont("monospace", 10))
        self.editor.setPlaceholderText("Select an existing configuration file.")
        self.editor.textChanged.connect(self.edit_full_file)
        editor_layout.addWidget(self.editor, 1)
        self.file_status = QLabel("No configuration selected.")
        self.file_status.setWordWrap(True)
        self.file_status.setObjectName("muted")
        editor_layout.addWidget(self.file_status)
        self.watch_status = QLabel("")
        self.watch_status.setWordWrap(True)
        self.watch_status.setObjectName("muted")
        editor_layout.addWidget(self.watch_status)
        self.backup_status = QLabel("Backups contain the disk file, not unsaved drafts.")
        self.backup_status.setWordWrap(True)
        self.backup_status.setTextFormat(Qt.TextFormat.PlainText)
        self.backup_status.setObjectName("muted")
        editor_layout.addWidget(self.backup_status)
        self.backup_button = QPushButton("Back up disk file")
        self.backup_button.setEnabled(False)
        self.backup_button.clicked.connect(self.start_backup)
        editor_layout.addWidget(self.backup_button)
        self.validation_status = QLabel("Draft not validated.")
        self.validation_status.setWordWrap(True)
        self.validation_status.setTextFormat(Qt.TextFormat.PlainText)
        self.validation_status.setObjectName("muted")
        editor_layout.addWidget(self.validation_status)
        validation_actions = QHBoxLayout()
        self.validate_button = QPushButton("Validate i3 draft")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self.start_validation)
        validation_actions.addWidget(self.validate_button)
        self.validation_details = QPushButton("Validation details")
        self.validation_details.setEnabled(False)
        self.validation_details.clicked.connect(self.show_validation_details)
        validation_actions.addWidget(self.validation_details)
        editor_layout.addLayout(validation_actions)
        self.review_button = QPushButton("Review draft changes")
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.review_document)
        editor_layout.addWidget(self.review_button)
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
            "Draft-only prototype · Edits stay in memory and cannot be saved or applied."
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
        self.current_path = None
        self.invalidate_validation()
        self.watch_file(None)
        self.backup_button.setEnabled(False)
        self.set_editor_content("")
        self.editor.setReadOnly(True)
        self.editor_help.setText("Full-file draft")
        self.reload_button.setEnabled(False)
        self.review_button.setEnabled(False)
        self.clear_gap("Select an i3 configuration to edit its inner gap.")
        if not data:
            return
        path, status = data
        if status != "Found" and path not in self.documents:
            self.set_editor_content(f"Configuration unavailable: {status}")
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
            self.set_editor_content(f"Unable to read configuration: {exc}")
            self.file_status.setText(f"Unable to inspect configuration: {exc}")
            return
        self.current_path = path
        self.reload_button.setEnabled(True)
        self.backup_button.setEnabled(self.backup_task is None)
        self.watch_file(path)
        self.show_draft()
        self.update_file_status(changed)
        if reload_error:
            self.file_status.setText(f"External change detected; unable to reload: {reload_error}")
        if self.status and self.status.components[self.navigation.currentRow()].component.key == "i3":
            self.update_gap()
        self.update_validation_controls()

    def watch_file(self, path: Path | None) -> None:
        self.file_check_timer.stop()
        watched = self.file_watcher.files() + self.file_watcher.directories()
        if watched:
            self.file_watcher.removePaths(watched)
        self.watch_status.setText("")
        if path is None:
            return
        directory = str(path.parent)
        failed = []
        if not self.file_watcher.addPath(directory):
            failed.append("directory")
        if path.exists() and not self.file_watcher.addPath(str(path)):
            failed.append("file")
        if failed:
            self.watch_status.setText(
                f"Automatic monitoring unavailable for {', '.join(failed)}; use refresh."
            )
        elif not path.exists():
            self.watch_status.setText("File missing; monitoring its directory for changes.")
        else:
            self.watch_status.setText("Monitoring for external changes.")
        self.file_check_timer.start()

    def schedule_file_check(self, _path: str) -> None:
        self.file_check_timer.start()

    def check_external_change(self) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        try:
            changed = document.changed_externally()
        except OSError as exc:
            self.file_status.setText(f"Unable to check external changes: {exc}")
            return
        if changed:
            self.invalidate_validation()
            if document.is_dirty or path in self.snippets:
                self.update_file_status(True)
            else:
                try:
                    replacement = ConfigDocument.open(path)
                except (OSError, ValueError) as exc:
                    self.file_status.setText(
                        f"External change detected; unable to reload: {exc}"
                    )
                else:
                    self.documents[path] = replacement
                    self.show_config()
                    return
        if path.exists():
            if str(path) not in self.file_watcher.files():
                if not self.file_watcher.addPath(str(path)):
                    self.watch_status.setText("Automatic file monitoring unavailable; use refresh.")
                elif str(path.parent) in self.file_watcher.directories():
                    self.watch_status.setText("Monitoring for external changes.")
        elif str(path.parent) in self.file_watcher.directories():
            self.watch_status.setText("File missing; monitoring its directory for changes.")

    def set_editor_content(self, text: str) -> None:
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)

    def show_draft(self) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        try:
            text = document.editor_text()
        except ValueError as exc:
            self.set_editor_content(document.draft)
            self.editor.setReadOnly(True)
            self.editor_help.setText(str(exc))
            return
        self.set_editor_content(text)
        if self.editor.document().toRawText().replace("\u2029", "\n") != text:
            self.editor.setReadOnly(True)
            self.editor_help.setText("This file cannot be represented safely in the editor.")
            return
        if self.current_path in self.snippets:
            self.editor.setReadOnly(True)
            self.editor_help.setText("Correct the invalid snippet before editing the full file.")
            return
        self.editor.setReadOnly(False)
        self.editor_help.setText("Full-file draft · changes stay in memory")

    def edit_full_file(self) -> None:
        if self.current_path is None or self.editor.isReadOnly():
            return
        document = self.documents[self.current_path]
        document.set_editor_text(self.editor.document().toRawText().replace("\u2029", "\n"))
        self.invalidate_validation()
        if self.status and self.status.components[self.navigation.currentRow()].component.key == "i3":
            self.update_gap()
        self.update_file_status()

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
        self.review_button.setEnabled(
            document.is_dirty and self.current_path not in self.snippets
        )
        try:
            changed = document.changed_externally() if changed is None else changed
        except OSError as exc:
            self.file_status.setText(f"Unable to check external changes: {exc}")
            return
        dirty = document.is_dirty or self.current_path in self.snippets
        if changed:
            self.file_status.setText("File changed externally. Draft retained; reload to discard it.")
        elif dirty:
            if self.current_path in self.snippets:
                self.file_status.setText(
                    "Invalid snippet is retained in memory; correct it before reviewing."
                )
            else:
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
        self.invalidate_validation()
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
        self.update_validation_controls()
        self.show_draft()
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
        self.invalidate_validation()
        self.show_draft()
        self.update_gap()
        self.update_file_status()

    def is_i3_selected(self) -> bool:
        index = self.navigation.currentRow()
        return bool(
            self.status is not None
            and 0 <= index < len(self.status.components)
            and self.status.components[index].component.key == "i3"
        )

    def update_validation_controls(self) -> None:
        self.validate_button.setEnabled(
            self.current_path is not None
            and self.is_i3_selected()
            and self.current_path not in self.snippets
            and self.validation_task is None
        )
        self.validation_details.setEnabled(
            self.validation_result is not None and bool(self.validation_result.details)
        )

    def invalidate_validation(self) -> None:
        self.validation_revision += 1
        self.validation_result = None
        self.validation_status.setText("Draft not validated.")
        self.update_validation_controls()

    def start_validation(self) -> None:
        if not self.validate_button.isEnabled() or self.current_path is None:
            return
        document = self.documents[self.current_path]
        self.validation_task = ValidationTask(
            self.current_path, document.draft, self.validation_revision
        )
        self.validation_task.signals.complete.connect(self.finish_validation)
        self.validation_result = None
        self.validation_status.setText("Validating draft…")
        self.update_validation_controls()
        QThreadPool.globalInstance().start(self.validation_task)

    def finish_validation(self, result: ValidationResult) -> None:
        task = self.validation_task
        self.validation_task = None
        if (task is not None and task.path == self.current_path
                and task.revision == self.validation_revision
                and task.path in self.documents
                and self.documents[task.path].draft == task.text
                and task.path not in self.snippets and self.is_i3_selected()):
            self.validation_result = result
            prefix = {
                ValidationStatus.VALID: "Valid",
                ValidationStatus.INVALID: "Invalid",
                ValidationStatus.UNAVAILABLE: "Unavailable",
            }[result.status]
            self.validation_status.setText(f"{prefix}: {result.summary}")
        else:
            self.validation_result = None
            self.validation_status.setText("Draft changed or selection moved; validate again.")
        self.update_validation_controls()

    def show_validation_details(self) -> None:
        if self.validation_result is None or not self.validation_result.details:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Validation details")
        dialog.resize(780, 560)
        layout = QVBoxLayout(dialog)
        details = QPlainTextEdit()
        details.setObjectName("validationOutput")
        details.setReadOnly(True)
        details.setPlainText(self.validation_result.details)
        layout.addWidget(details)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def start_backup(self) -> None:
        if self.current_path is None or self.backup_task is not None:
            return
        path = self.current_path
        answer = QMessageBox.question(
            self, "Back up disk file?",
            f"Back up {path} to {default_backup_root()}?\n\n"
            f"Unsaved drafts are not included. Only the {BACKUP_LIMIT} most recent "
            "backups per file are retained.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.backup_task = BackupTask(self.documents[path])
        self.backup_task.signals.complete.connect(self.finish_backup)
        self.backup_task.signals.error.connect(self.backup_failed)
        self.backup_status.setText(f"Backing up {path}…")
        self.backup_button.setEnabled(False)
        QThreadPool.globalInstance().start(self.backup_task)

    def finish_backup(self, result: BackupResult) -> None:
        self.backup_task = None
        self.backup_button.setEnabled(self.current_path is not None)
        self.backup_status.setText(
            f"Backup {result.record.identifier} created for {result.record.source}. "
            f"Older backups removed: {len(result.pruned)}."
        )

    def backup_failed(self, message: str) -> None:
        self.backup_task = None
        self.backup_button.setEnabled(self.current_path is not None)
        self.backup_status.setText(f"Backup failed: {message}")

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

    def review_document(self) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        if not document.is_dirty or path in self.snippets:
            return
        try:
            changed = document.changed_externally()
        except OSError as exc:
            status = f"Unable to check external changes: {exc}"
        else:
            status = ("File changed externally; this diff uses the original baseline."
                      if changed else "This draft is not saved or applied.")
        dialog = QDialog(self)
        dialog.setWindowTitle("Review draft changes")
        dialog.resize(780, 560)
        layout = QVBoxLayout(dialog)
        summary = QLabel(status)
        summary.setWordWrap(True)
        summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(summary)
        diff = QPlainTextEdit()
        diff.setObjectName("draftDiff")
        diff.setReadOnly(True)
        diff.setFont(QFont("monospace", 10))
        diff.setPlainText(document.diff())
        layout.addWidget(diff)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def closeEvent(self, event) -> None:
        if self.backup_task is not None:
            self.backup_status.setText("Wait for the backup to finish before closing.")
            event.ignore()
            return
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

"""Review a backup against the current in-memory draft."""

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from .backups import BackupVersion
from .document import compare_text


class BackupBrowser(QDialog):
    def __init__(
        self, path: Path, draft: str, versions: list[BackupVersion],
        has_invalid_snippet: bool, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path
        self.draft = draft
        self.versions = versions
        self.setWindowTitle("Review backups")
        self.resize(780, 560)
        layout = QVBoxLayout(self)
        message = "Compare the current draft with a backup. Loading never writes to disk."
        if has_invalid_snippet:
            message += " The invalid snippet is not included in the comparison."
        description = QLabel(message)
        description.setWordWrap(True)
        description.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(description)
        self.selection = QComboBox()
        self.selection.setObjectName("backupVersions")
        for version in versions:
            try:
                date = datetime.fromtimestamp(
                    version.record.created_ns / 1_000_000_000, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (OverflowError, OSError, ValueError):
                date = f"Timestamp: {version.record.created_ns} ns"
            self.selection.addItem(f"{date}  ·  {version.record.identifier[:12]}")
        self.selection.currentIndexChanged.connect(self.update_diff)
        layout.addWidget(self.selection)
        self.diff = QPlainTextEdit()
        self.diff.setObjectName("backupDiff")
        self.diff.setReadOnly(True)
        self.diff.setFont(QFont("monospace", 10))
        layout.addWidget(self.diff)
        buttons = QDialogButtonBox()
        buttons.addButton("Load as draft", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_diff()

    def selected_version(self) -> BackupVersion:
        return self.versions[self.selection.currentIndex()]

    def update_diff(self) -> None:
        if self.selection.currentIndex() < 0:
            self.diff.clear()
            return
        version = self.selected_version()
        diff = compare_text(
            self.draft, version.text, f"{self.path} (current draft)",
            f"{self.path} (backup {version.record.identifier})",
        )
        self.diff.setPlainText(diff or "No textual differences.")

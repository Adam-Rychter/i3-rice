"""Prototype shell with in-memory configuration drafts."""

from functools import partial
from pathlib import Path
import sys

from PySide6.QtCore import QFileSystemWatcher, QObject, QRunnable, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSlider, QSplitter, QVBoxLayout, QWidget, QCheckBox,
)

from .backup_browser import BackupBrowser
from .backups import (
    BACKUP_LIMIT, BackupError, BackupResult, BackupStore, BackupVersion, default_backup_root,
)
from .discovery import DesktopStatus, config_status, discover
from .document import ConfigDocument
from .dunst_colors import ColorSection, find_color, parse_color_line, replace_color_value
from .i3_appearance import (
    SettingKind, find_setting, parse_setting_line, replace_setting_value,
    setting_definition,
)
from .picom_radii import (
    MAX_RADIUS, RadiusKind, find_radius, minimum_radius, parse_radius_line,
    replace_radius_value,
)
from .polybar_height import (
    MAX_HEIGHT, MIN_HEIGHT, find_height, parse_height_line, replace_height_value,
)
from .rofi_radius import (
    MAX_RADIUS as MAX_ROFI_RADIUS, find_radius as find_rofi_radius,
    parse_radius_line as parse_rofi_radius_line, replace_radius_value as replace_rofi_radius_value,
)
from .settings import ColorSetting, NumericSetting
from .validation import ValidationResult, ValidationStatus, validate_i3
from .persistence import ApplyError, ApplyResult, apply_document, restore_backup
from .workspace_labels import find_workspace, find_workspace_labels, replace_workspace_label
from .keybindings import binding_conflicts, find_keybindings
from .i3_variables import find_variables, variable_references
from .install_catalog import (
    AptPlan, PackageState, PackageStatus, build_apt_plan, detect_apt_packages,
)
from .apt_executor import (
    AptExecutionError, AptExecutionResult, execute_apt_plan,
)


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
QScrollArea { border: none; background: transparent; }
"""


def numeric_settings() -> dict[str, NumericSetting]:
    settings: dict[str, NumericSetting] = {}
    kinds: tuple[SettingKind, ...] = ("inner", "outer", "pixel_border")
    for kind in kinds:
        definition = setting_definition(kind)
        settings[kind] = NumericSetting(
            "i3", definition.label, definition.minimum, definition.maximum,
            partial(find_setting, kind=kind), partial(parse_setting_line, kind=kind),
            partial(replace_setting_value, kind=kind),
        )
    settings["bar_height"] = NumericSetting(
        "polybar", "Main bar height", MIN_HEIGHT, MAX_HEIGHT,
        find_height, parse_height_line, replace_height_value,
    )
    settings["rofi_window_radius"] = NumericSetting(
        "rofi", "Window radius", 0, MAX_ROFI_RADIUS,
        find_rofi_radius, parse_rofi_radius_line, replace_rofi_radius_value,
    )
    radii: tuple[RadiusKind, ...] = ("corner-radius", "shadow-radius")
    for radius in radii:
        settings[f"picom_{radius}"] = NumericSetting(
            "picom", radius.replace("-", " ").capitalize(), minimum_radius(radius), MAX_RADIUS,
            partial(find_radius, kind=radius), partial(parse_radius_line, kind=radius),
            partial(replace_radius_value, kind=radius),
        )
    return settings


def color_settings() -> dict[str, ColorSetting]:
    sections: tuple[ColorSection, ...] = (
        "global", "urgency_low", "urgency_normal", "urgency_critical",
    )
    return {
        f"dunst_{section}": ColorSetting(
            "dunst", f"Frame color [{section}]", partial(find_color, section=section),
            parse_color_line, replace_color_value,
        )
        for section in sections
    }


class AppearanceControl(QWidget):
    def __init__(self, definition: NumericSetting) -> None:
        super().__init__()
        self.definition = definition
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(f"{self.definition.label}: unavailable")
        layout.addWidget(self.label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName(self.definition.label)
        self.slider.setRange(self.definition.minimum, self.definition.maximum)
        self.slider.setToolTip(
            f"Range: {self.definition.minimum} to {self.definition.maximum} px"
        )
        self.slider.setEnabled(False)
        layout.addWidget(self.slider)
        self.snippet = QLineEdit()
        self.snippet.setMaxLength(1024 * 1024)
        self.snippet.setAccessibleName(f"{self.definition.label} configuration")
        self.snippet.setPlaceholderText("Relevant configuration line")
        self.snippet.setEnabled(False)
        layout.addWidget(self.snippet)
        self.help = QLabel("Select a configuration.")
        self.help.setObjectName("muted")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def clear(self, message: str) -> None:
        self.disable_value()
        self.label.setText(f"{self.definition.label}: unavailable")
        self.snippet.blockSignals(True)
        self.snippet.clear()
        self.snippet.blockSignals(False)
        self.snippet.setEnabled(False)
        self.help.setText(message)

    def disable_value(self) -> None:
        self.slider.setEnabled(False)

    def show_value(self, value: int | str, context: str) -> None:
        if not isinstance(value, int):
            raise TypeError("Numeric control requires an integer")
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.slider.setEnabled(True)
        self.label.setText(f"{self.definition.label}: {value}px")
        self.help.setText(
            f"Range: {self.definition.minimum} to {self.definition.maximum}px. "
            f"Edit the line or move the slider; changes are draft only. {context}"
        )


class ColorControl(QWidget):
    def __init__(self, definition: ColorSetting) -> None:
        super().__init__()
        self.definition = definition
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(f"{definition.label}: unavailable")
        layout.addWidget(self.label)
        self.button = QPushButton("Choose color")
        self.button.setAccessibleName(definition.label)
        self.button.setEnabled(False)
        layout.addWidget(self.button)
        self.snippet = QLineEdit()
        self.snippet.setMaxLength(1024 * 1024)
        self.snippet.setAccessibleName(f"{definition.label} configuration")
        self.snippet.setPlaceholderText("Relevant configuration line")
        self.snippet.setEnabled(False)
        layout.addWidget(self.snippet)
        self.help = QLabel("Select a configuration.")
        self.help.setObjectName("muted")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def disable_value(self) -> None:
        self.button.setEnabled(False)
        self.button.setStyleSheet("")

    def clear(self, message: str) -> None:
        self.disable_value()
        self.label.setText(f"{self.definition.label}: unavailable")
        self.snippet.blockSignals(True)
        self.snippet.clear()
        self.snippet.blockSignals(False)
        self.snippet.setEnabled(False)
        self.help.setText(message)

    def show_value(self, value: int | str, context: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Color control requires a string")
        self.label.setText(f"{self.definition.label}: {value}")
        self.button.setStyleSheet(f"QPushButton {{ border: 3px solid {value}; }}")
        self.button.setEnabled(True)
        self.help.setText(f"Edit the line or choose a color; changes are draft only. {context}")


class WorkspaceControl(QWidget):
    def __init__(self, number: int) -> None:
        super().__init__()
        self.number = number
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(f"Workspace {number}: unavailable")
        layout.addWidget(self.label)
        self.editor = QLineEdit()
        self.editor.setAccessibleName(f"Workspace {number} label")
        self.editor.setPlaceholderText("Literal workspace label")
        self.editor.setEnabled(False)
        layout.addWidget(self.editor)
        self.help = QLabel("Select an i3 configuration.")
        self.help.setObjectName("muted")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def clear(self, message: str) -> None:
        self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.blockSignals(False)
        self.editor.setEnabled(False)
        self.label.setText(f"Workspace {self.number}: unavailable")
        self.help.setText(message)

    def show_value(self, value: str) -> None:
        self.editor.blockSignals(True)
        self.editor.setText(value)
        self.editor.blockSignals(False)
        self.editor.setEnabled(True)
        self.label.setText(f"Workspace {self.number}: {value}")
        self.help.setText("Edit the literal label; changes are draft only.")


class KeybindingSummary(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Keybindings")
        title.setObjectName("section")
        layout.addWidget(title)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(180)
        self.text.setPlaceholderText("No literal bindsym entries found.")
        layout.addWidget(self.text)
        self.help = QLabel("Keybinding commands are shown read-only until conflict-safe editing is implemented.")
        self.help.setObjectName("muted")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def clear(self, message: str) -> None:
        self.text.clear()
        self.help.setText(message)

    def show_bindings(self, text: str, conflicts: tuple[str, ...]) -> None:
        self.text.setPlainText(text or "No literal bindsym entries found.")
        if conflicts:
            self.help.setText("Conflict: duplicate trigger(s): " + ", ".join(conflicts))
        else:
            self.help.setText(
                "Keybinding commands are shown read-only until conflict-safe editing is implemented."
            )


class VariableSummary(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Shared variables")
        title.setObjectName("section")
        layout.addWidget(title)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumHeight(150)
        self.text.setPlaceholderText("No literal i3 variables found.")
        layout.addWidget(self.text)
        self.help = QLabel(
            "References are shown read-only until variable-level editing and affected-setting choices are implemented."
        )
        self.help.setObjectName("muted")
        self.help.setWordWrap(True)
        layout.addWidget(self.help)

    def clear(self, message: str) -> None:
        self.text.clear()
        self.help.setText(message)

    def show_variables(self, text: str) -> None:
        self.text.setPlainText(text or "No literal i3 variables found.")
        self.help.setText(
            "References are shown read-only until variable-level editing and affected-setting choices are implemented."
        )


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


class ApplyTask(QRunnable):
    def __init__(self, document: ConfigDocument) -> None:
        super().__init__()
        self.document = document
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            result = apply_document(self.document)
        except (ApplyError, OSError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(result)


class RestoreTask(QRunnable):
    def __init__(self, document: ConfigDocument, version: BackupVersion) -> None:
        super().__init__()
        self.document = document
        self.version = version
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            result = restore_backup(self.document, self.version)
        except (ApplyError, OSError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(result)


class AptScanTask(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            result = detect_apt_packages()
        except (OSError, ValueError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(result)


class AptInstallTask(QRunnable):
    def __init__(self, plan: AptPlan) -> None:
        super().__init__()
        self.plan = plan
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            result = execute_apt_plan(self.plan)
        except (AptExecutionError, OSError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(result)


class BrowseBackupsTask(QRunnable):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            versions = BackupStore().versions(self.path)
        except (BackupError, OSError) as exc:
            self.signals.error.emit(str(exc))
        else:
            self.signals.complete.emit(versions)


class AptSetupDialog(QDialog):
    def __init__(self, statuses: tuple[PackageStatus, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.statuses = statuses
        self.checkboxes: dict[str, QCheckBox] = {}
        self.install_requested = False
        self.setWindowTitle("Review apt setup")
        self.resize(620, 560)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Select components to include in a proposed apt plan. No package "
            "operations are executed from this review."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        for status in statuses:
            checkbox = QCheckBox(
                f"{status.spec.description}  [{status.spec.package}] — {status.state.value}"
            )
            checkbox.setChecked(True)
            checkbox.setEnabled(status.state is not PackageState.INSTALLED)
            checkbox.setToolTip(status.detail)
            checkbox.stateChanged.connect(self.update_plan)
            self.checkboxes[status.spec.component] = checkbox
            layout.addWidget(checkbox)
        self.plan = QPlainTextEdit()
        self.plan.setObjectName("aptPlan")
        self.plan.setReadOnly(True)
        layout.addWidget(self.plan, 1)
        self.status = QLabel(
            "Installation requires a second confirmation and uses the bounded pkexec executor."
        )
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        install = buttons.addButton(
            "Install selected packages", QDialogButtonBox.ButtonRole.AcceptRole
        )
        install.clicked.connect(self.request_install)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_plan()

    def request_install(self) -> None:
        self.install_requested = True
        self.accept()

    def selected_plan(self) -> AptPlan:
        selected = [
            component for component, checkbox in self.checkboxes.items() if checkbox.isChecked()
        ]
        return build_apt_plan(selected, self.statuses)

    def update_plan(self) -> None:
        plan = self.selected_plan()
        lines = ["Proposed apt operation:"]
        lines.append(
            "Install: " + (", ".join(plan.packages) if plan.packages else "none")
        )
        lines.append(
            "Already installed: "
            + (", ".join(plan.already_installed) if plan.already_installed else "none")
        )
        if plan.unknown_packages:
            lines.append("Unknown status: " + ", ".join(plan.unknown_packages))
        if plan.unsupported_components:
            lines.append("Unsupported: " + ", ".join(plan.unsupported_components))
        self.plan.setPlainText("\n".join(lines))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.status: DesktopStatus | None = None
        self.scanner: Scan | None = None
        self.validation_task: ValidationTask | None = None
        self.validation_result: ValidationResult | None = None
        self.validation_revision = 0
        self.backup_task: BackupTask | None = None
        self.apply_task: ApplyTask | None = None
        self.restore_task: RestoreTask | None = None
        self.browse_task: BrowseBackupsTask | None = None
        self.apt_task: AptScanTask | None = None
        self.apt_install_task: AptInstallTask | None = None
        self.documents: dict[Path, ConfigDocument] = {}
        self.snippets: dict[Path, dict[str, str]] = {}
        self.staged_backups: set[Path] = set()
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
        self.setup_button = QPushButton("Review apt setup")
        self.setup_button.clicked.connect(self.start_apt_review)
        side.addWidget(self.setup_button)
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
            "Draft changes stay in memory until explicitly reviewed and applied."
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
        self.no_controls = QLabel("No guided controls are available for this component yet.")
        self.no_controls.setObjectName("muted")
        self.no_controls.setWordWrap(True)
        detail_layout.addWidget(self.no_controls)
        self.appearance_controls: dict[str, AppearanceControl] = {}
        for kind, definition in numeric_settings().items():
            control = AppearanceControl(definition)
            control.slider.valueChanged.connect(
                lambda value, name=kind: self.change_setting(name, value)
            )
            control.snippet.textEdited.connect(
                lambda text, name=kind: self.edit_snippet(name, text)
            )
            self.appearance_controls[kind] = control
            detail_layout.addWidget(control)
        self.color_controls: dict[str, ColorControl] = {}
        for kind, definition in color_settings().items():
            control = ColorControl(definition)
            control.button.clicked.connect(lambda _checked=False, name=kind: self.choose_color(name))
            control.snippet.textEdited.connect(
                lambda text, name=kind: self.edit_snippet(name, text)
            )
            self.color_controls[kind] = control
            detail_layout.addWidget(control)
        self.setting_controls: dict[str, AppearanceControl | ColorControl] = {
            **self.appearance_controls, **self.color_controls,
        }
        self.workspace_controls: dict[int, WorkspaceControl] = {}
        for number in range(1, 6):
            control = WorkspaceControl(number)
            control.editor.textEdited.connect(
                lambda text, workspace=number: self.edit_workspace(workspace, text)
            )
            self.workspace_controls[number] = control
            detail_layout.addWidget(control)
        self.keybinding_summary = KeybindingSummary()
        detail_layout.addWidget(self.keybinding_summary)
        self.variable_summary = VariableSummary()
        detail_layout.addWidget(self.variable_summary)
        detail_layout.addStretch()
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.details)
        splitter.addWidget(detail_scroll)

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
        self.browse_button = QPushButton("Review backups")
        self.browse_button.setEnabled(False)
        self.browse_button.clicked.connect(self.start_browsing_backups)
        editor_layout.addWidget(self.browse_button)
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
        self.apply_button = QPushButton("Apply draft to disk")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.start_apply)
        editor_layout.addWidget(self.apply_button)
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

    def start_apt_review(self) -> None:
        if self.apt_task is not None:
            return
        self.apt_task = AptScanTask()
        self.apt_task.signals.complete.connect(self.finish_apt_review)
        self.apt_task.signals.error.connect(self.apt_review_failed)
        self.setup_button.setEnabled(False)
        self.notice.setText("Checking curated apt package status…")
        QThreadPool.globalInstance().start(self.apt_task)

    def finish_apt_review(self, statuses: tuple[PackageStatus, ...]) -> None:
        self.apt_task = None
        self.setup_button.setEnabled(True)
        if not statuses:
            self.apt_review_failed("The apt catalog is empty.")
            return
        self.notice.setText("Apt package status loaded; review the proposed setup plan.")
        dialog = AptSetupDialog(statuses, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.install_requested:
            self.start_apt_install(dialog.selected_plan())

    def apt_review_failed(self, message: str) -> None:
        self.apt_task = None
        self.setup_button.setEnabled(True)
        self.notice.setText(f"Apt package review failed: {message}")

    def start_apt_install(self, plan: AptPlan) -> None:
        if self.apt_install_task is not None:
            return
        if not plan.packages:
            self.notice.setText("The selected apt plan has no missing packages.")
            return
        packages = ", ".join(plan.packages)
        answer = QMessageBox.question(
            self, "Install apt packages?",
            f"Install these packages using pkexec?\n\n{packages}\n\n"
            "No administrator password is handled by the application.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.apt_install_task = AptInstallTask(plan)
        self.apt_install_task.signals.complete.connect(self.finish_apt_install)
        self.apt_install_task.signals.error.connect(self.apt_install_failed)
        self.setup_button.setEnabled(False)
        self.notice.setText("Installing selected apt packages…")
        QThreadPool.globalInstance().start(self.apt_install_task)

    def finish_apt_install(self, result: AptExecutionResult) -> None:
        self.apt_install_task = None
        self.setup_button.setEnabled(True)
        succeeded = [item.package for item in result.operations
                     if item.state.value == "succeeded"]
        failed = [item.package for item in result.operations
                  if item.state.value == "failed"]
        skipped = [item.package for item in result.operations
                   if item.state.value == "skipped"]
        summary = (
            f"Installation complete. Succeeded: {len(succeeded)}; "
            f"failed: {len(failed)}; skipped: {len(skipped)}."
        )
        self.notice.setText(summary)
        if failed or skipped:
            QMessageBox.warning(self, "Apt installation result", summary)

    def apt_install_failed(self, message: str) -> None:
        self.apt_install_task = None
        self.setup_button.setEnabled(True)
        self.notice.setText(f"Apt installation failed: {message}")

    def finish_scan(self, result: DesktopStatus) -> None:
        selected = self.navigation.currentRow()
        self.status = result
        self.session.setText(f"{result.session.upper()}  ·  {result.desktop.upper()}")
        self.notice.setText(
            "Draft changes stay in memory until explicitly reviewed and applied."
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
        self.apply_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.set_editor_content("")
        self.editor.setReadOnly(True)
        self.editor_help.setText("Full-file draft")
        self.reload_button.setEnabled(False)
        self.review_button.setEnabled(False)
        selected = self.selected_component()
        self.no_controls.setVisible(
            not (
                any(control.definition.component == selected
                    for control in self.setting_controls.values())
                or selected == "workspaces"
            )
        )
        for control in self.setting_controls.values():
            control.clear("Select a configuration.")
            control.setVisible(control.definition.component == selected)
        for control in self.workspace_controls.values():
            control.clear("Select a configuration.")
            control.setVisible(selected == "workspaces")
        self.keybinding_summary.setVisible(selected == "workspaces")
        self.keybinding_summary.clear("Select an i3 configuration.")
        self.variable_summary.setVisible(selected in {"i3", "workspaces"})
        self.variable_summary.clear("Select an i3 configuration.")
        if not data:
            return
        path, _ = data
        status = config_status(path)
        self.config_select.setItemData(self.config_select.currentIndex(), (path, status))
        self.config_select.setItemText(self.config_select.currentIndex(), f"{path}  —  {status}")
        if status != "Found" and path not in self.documents:
            self.set_editor_content(f"Configuration unavailable: {status}")
            self.file_status.setText(f"Configuration unavailable: {status}")
            if status == "Not found":
                self.current_path = path
                self.browse_button.setEnabled(self.browse_task is None)
                self.watch_file(path)
            return
        reload_error = None
        try:
            if path not in self.documents:
                self.documents[path] = ConfigDocument.open(path)
            document = self.documents[path]
            changed = document.changed_externally()
            if changed and not self.has_pending_changes(path):
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
        self.backup_button.setEnabled(document.baseline_exists and self.backup_task is None)
        self.browse_button.setEnabled(self.browse_task is None)
        self.watch_file(path)
        self.show_draft()
        self.update_file_status(changed)
        if reload_error:
            self.file_status.setText(f"External change detected; unable to reload: {reload_error}")
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
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
        if path not in self.documents:
            if config_status(path) != "Not found":
                self.show_config()
            return
        document = self.documents[path]
        try:
            changed = document.changed_externally()
        except OSError as exc:
            self.file_status.setText(f"Unable to check external changes: {exc}")
            return
        if changed:
            self.invalidate_validation()
            if self.has_pending_changes(path):
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
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
        self.update_file_status()

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
        dirty = self.has_pending_changes(self.current_path)
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
        self.update_apply_control(changed)

    def update_apply_control(self, changed: bool | None = None) -> None:
        if self.current_path is None or self.current_path not in self.documents:
            self.apply_button.setEnabled(False)
            return
        document = self.documents[self.current_path]
        if changed is None:
            try:
                changed = document.changed_externally()
            except OSError:
                changed = True
        self.apply_button.setEnabled(
            document.is_dirty and not changed and self.current_path not in self.snippets
            and self.apply_task is None
        )

    def update_appearance(self) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        for kind, control in self.setting_controls.items():
            if control.definition.component != self.selected_component():
                continue
            try:
                setting = control.definition.find(document.draft)
            except ValueError as exc:
                pending = self.snippets.get(self.current_path, {})
                if kind in pending:
                    control.snippet.blockSignals(True)
                    control.snippet.setText(pending[kind])
                    control.snippet.blockSignals(False)
                    control.snippet.setEnabled(True)
                    control.disable_value()
                    control.label.setText(f"{control.definition.label}: invalid draft")
                    control.help.setText(str(exc))
                else:
                    control.clear(str(exc))
                continue
            snippet = self.snippets.get(self.current_path, {}).get(kind, setting.line)
            control.snippet.blockSignals(True)
            control.snippet.setText(snippet)
            control.snippet.blockSignals(False)
            control.snippet.setEnabled(True)
            try:
                value = control.definition.parse(snippet)
            except ValueError as exc:
                control.disable_value()
                control.label.setText(f"{control.definition.label}: invalid draft")
                control.help.setText(str(exc))
                continue
            control.show_value(value, setting.context)

    def update_workspace_controls(self) -> None:
        if self.current_path is None or self.selected_component() != "workspaces":
            return
        document = self.documents[self.current_path]
        try:
            labels = {label.number: label for label in find_workspace_labels(document.draft)}
        except ValueError as exc:
            for control in self.workspace_controls.values():
                control.clear(str(exc))
            return
        for number, control in self.workspace_controls.items():
            label = labels.get(number)
            if label is None:
                control.clear(f"Workspace ${number} is not defined.")
            else:
                control.show_value(label.name)

    def update_keybinding_summary(self) -> None:
        if self.current_path is None or self.selected_component() != "workspaces":
            return
        document = self.documents[self.current_path]
        bindings = find_keybindings(document.draft)
        lines = [f"{binding.trigger}  →  {binding.command}" for binding in bindings]
        self.keybinding_summary.show_bindings("\n".join(lines), binding_conflicts(bindings))

    def update_variable_summary(self) -> None:
        if self.current_path is None or self.selected_component() not in {"i3", "workspaces"}:
            return
        document = self.documents[self.current_path]
        try:
            variables = find_variables(document.draft)
        except ValueError as exc:
            self.variable_summary.clear(str(exc))
            return
        lines = [
            f"${variable.name} = {variable.value}  ({len(variable_references(document.draft, variable.name))} references)"
            for variable in variables
        ]
        self.variable_summary.show_variables("\n".join(lines))

    def edit_workspace(self, number: int, text: str) -> None:
        if self.current_path is None or self.selected_component() != "workspaces":
            return
        document = self.documents[self.current_path]
        try:
            setting = find_workspace(document.draft, number)
            replacement = replace_workspace_label(setting.line, text)
            document.replace(setting.start, setting.end, setting.line, replacement)
        except ValueError as exc:
            self.workspace_controls[number].help.setText(str(exc))
            self.update_file_status()
            return
        self.invalidate_validation()
        self.show_draft()
        self.update_workspace_controls()
        self.update_file_status()

    def edit_snippet(self, kind: str, text: str) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        self.snippets.setdefault(path, {})[kind] = text
        self.invalidate_validation()
        definition = self.setting_controls[kind].definition
        try:
            definition.parse(text)
            setting = definition.find(document.draft)
            document.replace(setting.start, setting.end, setting.line, text)
        except ValueError as exc:
            error = str(exc)
        else:
            error = None
            del self.snippets[path][kind]
            if not self.snippets[path]:
                self.snippets.pop(path)
        self.update_validation_controls()
        self.show_draft()
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
        if error is not None:
            self.setting_controls[kind].help.setText(error)
        self.update_file_status()

    def change_setting(self, kind: str, value: int) -> None:
        if self.current_path is None:
            return
        document = self.documents[self.current_path]
        definition = self.appearance_controls[kind].definition
        try:
            setting = definition.find(document.draft)
            replacement = definition.replace(setting.line, value)
            document.replace(setting.start, setting.end, setting.line, replacement)
        except ValueError as exc:
            self.appearance_controls[kind].clear(str(exc))
            return
        self.invalidate_validation()
        self.show_draft()
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
        self.update_file_status()

    def choose_color(self, kind: str) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        document = self.documents[path]
        control = self.color_controls[kind]
        if not control.button.isEnabled():
            return
        try:
            setting = control.definition.find(document.draft)
        except ValueError as exc:
            control.clear(str(exc))
            return
        draft = document.draft
        pending = dict(self.snippets.get(path, {}))
        revision = self.validation_revision
        chosen = QColorDialog.getColor(QColor(setting.value), self, control.definition.label)
        if not chosen.isValid():
            return
        if (self.current_path != path or self.documents.get(path) is not document
                or document.draft != draft or self.snippets.get(path, {}) != pending
                or self.validation_revision != revision
                or self.selected_component() != control.definition.component):
            self.file_status.setText("The file or draft changed; choose the color again.")
            return
        try:
            replacement = control.definition.replace(setting.line, chosen.name())
            document.replace(setting.start, setting.end, setting.line, replacement)
        except ValueError as exc:
            control.help.setText(str(exc))
            return
        self.invalidate_validation()
        self.show_draft()
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
        self.update_file_status()

    def selected_component(self) -> str | None:
        index = self.navigation.currentRow()
        if self.status is None or not 0 <= index < len(self.status.components):
            return None
        return self.status.components[index].component.key

    def is_i3_selected(self) -> bool:
        return self.selected_component() == "i3"

    def update_validation_controls(self) -> None:
        self.validate_button.setEnabled(
            self.current_path in self.documents
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
        if (self.current_path is None or self.backup_task is not None
                or self.current_path not in self.documents
                or not self.documents[self.current_path].baseline_exists):
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

    def start_apply(self) -> None:
        if (self.current_path is None or self.current_path not in self.documents
                or self.apply_task is not None):
            return
        path = self.current_path
        document = self.documents[path]
        if not document.is_dirty or path in self.snippets:
            return
        try:
            changed = document.changed_externally()
        except OSError as exc:
            self.file_status.setText(f"Unable to check external changes: {exc}")
            self.update_apply_control(True)
            return
        if changed:
            self.file_status.setText("File changed externally. Reload before applying.")
            self.update_apply_control(True)
            return
        if self.is_i3_selected():
            if self.validation_result is None:
                self.file_status.setText("Validate the i3 draft before applying.")
                return
            if self.validation_result.status == ValidationStatus.INVALID:
                self.file_status.setText("The i3 draft is invalid; fix validation errors before applying.")
                return
        validation_note = ""
        if (self.is_i3_selected() and self.validation_result is not None
                and self.validation_result.status == ValidationStatus.UNAVAILABLE):
            validation_note = (
                "\n\nThe i3 validator is unavailable for this draft. "
                "Applying it requires explicit confirmation."
            )
        answer = QMessageBox.question(
            self, "Apply draft to disk?",
            f"This will back up {path} and replace its contents with the reviewed draft."
            f"{validation_note}",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.current_path != path or self.documents.get(path) is not document:
            self.file_status.setText("Selection changed; review the draft again.")
            return
        self.apply_task = ApplyTask(document)
        self.apply_task.signals.complete.connect(self.finish_apply)
        self.apply_task.signals.error.connect(self.apply_failed)
        self.apply_button.setEnabled(False)
        self.file_status.setText(f"Applying {path}…")
        QThreadPool.globalInstance().start(self.apply_task)

    def finish_apply(self, result: ApplyResult) -> None:
        task = self.apply_task
        self.apply_task = None
        if task is None or self.documents.get(result.path) is not task.document:
            self.file_status.setText("Apply completed, but the selected document changed.")
            return
        self.staged_backups.discard(result.path)
        self.invalidate_validation()
        self.show_config()
        backup_text = " A backup was created." if result.backup is not None else ""
        self.file_status.setText(f"Applied {result.path} successfully.{backup_text}")

    def apply_failed(self, message: str) -> None:
        self.apply_task = None
        self.update_apply_control()
        self.file_status.setText(f"Apply failed: {message}")

    def finish_backup(self, result: BackupResult) -> None:
        self.backup_task = None
        self.update_backup_controls()
        self.backup_status.setText(
            f"Backup {result.record.identifier} created for {result.record.source}. "
            f"Older backups removed: {len(result.pruned)}."
        )

    def backup_failed(self, message: str) -> None:
        self.backup_task = None
        self.update_backup_controls()
        self.backup_status.setText(f"Backup failed: {message}")

    def update_backup_controls(self) -> None:
        self.backup_button.setEnabled(
            self.current_path in self.documents
            and self.documents[self.current_path].baseline_exists
            and self.backup_task is None
        )

    def start_browsing_backups(self) -> None:
        if self.current_path is None or self.browse_task is not None:
            return
        self.browse_task = BrowseBackupsTask(self.current_path)
        self.browse_task.signals.complete.connect(self.finish_browsing_backups)
        self.browse_task.signals.error.connect(self.browse_backups_failed)
        self.backup_status.setText(f"Loading backups for {self.current_path}…")
        self.browse_button.setEnabled(False)
        QThreadPool.globalInstance().start(self.browse_task)

    def finish_browsing_backups(self, versions: list[BackupVersion]) -> None:
        task = self.browse_task
        self.browse_task = None
        self.browse_button.setEnabled(self.current_path is not None)
        if task is None or task.path != self.current_path:
            self.backup_status.setText("Selection changed; open backups again.")
            return
        path = task.path
        if not versions:
            self.backup_status.setText(f"No backups found for {path}.")
            return
        original_document = self.documents.get(path)
        if original_document is None:
            try:
                document = ConfigDocument.for_missing(path)
            except OSError as exc:
                self.backup_status.setText(f"Unable to review missing configuration: {exc}")
                return
        else:
            document = original_document
        draft = document.draft
        snippet = dict(self.snippets.get(path, {}))
        staged = path in self.staged_backups
        browser = BackupBrowser(path, draft, versions, bool(snippet), self)
        self.backup_status.setText(f"Loaded {len(versions)} backups for {path}.")
        if browser.exec() != QDialog.DialogCode.Accepted:
            return
        if (self.current_path != path or self.documents.get(path) is not original_document
                or document.draft != draft or self.snippets.get(path, {}) != snippet
                or (path in self.staged_backups) != staged):
            self.backup_status.setText("The file or draft changed; review backups again.")
            return
        try:
            conflict = document.changed_externally()
        except OSError as exc:
            self.backup_status.setText(f"Unable to check external changes: {exc}")
            return
        selected = browser.selected_version()
        if browser.restore_requested:
            message = (
                f"Restore backup {selected.record.identifier[:12]} to {path}?\n\n"
                "The current disk file will be backed up first. Any in-memory draft "
                "will be discarded, and the change will be written to disk."
            )
            title = "Restore backup to disk?"
        else:
            message = "Load this backup into an in-memory draft? No files will be overwritten."
            if original_document is not None and self.has_pending_changes(path):
                message += "\n\nThis replaces the pending draft and any invalid snippet."
            title = "Load backup as draft?"
        if conflict:
            message += "\n\nThe disk file changed externally; the conflict remains unresolved."
        if QMessageBox.question(self, title, message) != QMessageBox.StandardButton.Yes:
            return
        # A modal confirmation can process file-watcher events before returning.
        if (self.current_path != path or self.documents.get(path) is not original_document
                or document.draft != draft or self.snippets.get(path, {}) != snippet
                or (path in self.staged_backups) != staged):
            self.backup_status.setText("The file or draft changed; review backups again.")
            return
        if original_document is None:
            try:
                if document.changed_externally():
                    self.backup_status.setText("The file appeared; review backups again.")
                    return
            except OSError as exc:
                self.backup_status.setText(f"Unable to check external changes: {exc}")
                return
            self.documents[path] = document
        if browser.restore_requested:
            if (self.current_path != path or self.documents.get(path) is not document
                    or document.draft != draft or self.snippets.get(path, {}) != snippet
                    or (path in self.staged_backups) != staged):
                self.backup_status.setText("The file or draft changed; review backups again.")
                return
            self.restore_task = RestoreTask(document, selected)
            self.restore_task.signals.complete.connect(self.finish_restore)
            self.restore_task.signals.error.connect(self.restore_failed)
            self.backup_status.setText(f"Restoring backup to {path}…")
            self.browse_button.setEnabled(False)
            QThreadPool.globalInstance().start(self.restore_task)
            return
        document.load_draft(selected.text)
        self.snippets.pop(path, None)
        self.staged_backups.add(path)
        self.invalidate_validation()
        self.show_draft()
        self.update_appearance()
        self.update_workspace_controls()
        self.update_keybinding_summary()
        self.update_variable_summary()
        self.update_file_status()
        self.backup_status.setText("Backup loaded as a draft. The disk file was not changed.")

    def browse_backups_failed(self, message: str) -> None:
        self.browse_task = None
        self.browse_button.setEnabled(self.current_path is not None)
        self.backup_status.setText(f"Unable to load backups: {message}")

    def finish_restore(self, result: ApplyResult) -> None:
        task = self.restore_task
        self.restore_task = None
        self.browse_button.setEnabled(self.current_path is not None)
        if task is None or self.documents.get(result.path) is not task.document:
            self.backup_status.setText("Restore completed, but the selected document changed.")
            return
        self.snippets.pop(result.path, None)
        self.staged_backups.discard(result.path)
        self.invalidate_validation()
        self.show_config()
        self.backup_status.setText(
            f"Restored {result.path} successfully. A backup of the previous file was created."
        )

    def restore_failed(self, message: str) -> None:
        self.restore_task = None
        self.browse_button.setEnabled(self.current_path is not None)
        self.backup_status.setText(f"Restore failed: {message}")

    def reload_document(self) -> None:
        if self.current_path is None:
            return
        path = self.current_path
        if self.has_pending_changes(path):
            answer = QMessageBox.question(
                self, "Discard draft?",
                "Reloading discards this in-memory draft. Continue?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            replacement = ConfigDocument.open(path)
        except FileNotFoundError:
            try:
                ConfigDocument.for_missing(path)
            except OSError as exc:
                self.file_status.setText(f"Unable to reload configuration: {exc}")
                return
            self.documents.pop(path)
            self.snippets.pop(path, None)
            self.staged_backups.discard(path)
            self.show_config()
            return
        except (OSError, ValueError) as exc:
            self.file_status.setText(f"Unable to reload configuration: {exc}")
            return
        self.documents[path] = replacement
        self.snippets.pop(path, None)
        self.staged_backups.discard(path)
        self.show_config()

    def has_pending_changes(self, path: Path) -> bool:
        return (self.documents[path].is_dirty or path in self.snippets
                or path in self.staged_backups)

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
        if (self.backup_task is not None or self.browse_task is not None
                or self.apply_task is not None or self.restore_task is not None
                or self.apt_task is not None or self.apt_install_task is not None):
            self.backup_status.setText("Wait for the configuration operation to finish before closing.")
            event.ignore()
            return
        if any(self.has_pending_changes(path) for path in self.documents):
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

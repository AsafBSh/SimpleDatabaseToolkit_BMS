"""Main Simple Database Toolkit window and page routing."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.domain import OperationResult, OperationStatus
from simple_database_toolkit.build_profile import BML_EDITOR_ENABLED
from simple_database_toolkit.domain.backups import default_backup_root
from simple_database_toolkit.ui.branding import APPLICATION_TITLE, PRODUCT_NAME
from simple_database_toolkit.ui.command_palette import CommandPalette
from simple_database_toolkit.ui.components import PathPicker, TaskStatus
from simple_database_toolkit.ui.navigation import NavigationPanel
from simple_database_toolkit.ui.pages import (
    BmlPage,
    DashboardPage,
    FolderCreatorPage,
    LinksPage,
    OffsetPage,
    ParkingPage,
    ParentsPage,
    ReplacePage,
    RunwayPage,
    TutorialPage,
)
from simple_database_toolkit.ui.theme import (
    THEME_LABELS,
    ThemeName,
    apply_theme,
    normalize_theme,
)
from simple_database_toolkit.version import __version__


def normalize_recent_paths(
    value: object,
    *,
    maximum: int = 5,
) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = [str(item) for item in value]
    else:
        candidates = []
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = candidate.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= maximum:
            break
    return tuple(result)


def recommended_window_size(
    available_size: QSize,
    *,
    margin: int = 32,
) -> QSize:
    usable_width = max(1, available_size.width() - margin)
    usable_height = max(1, available_size.height() - margin)
    return QSize(
        min(1400, usable_width),
        min(900, usable_height),
    )


TaskPage = QWidget


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self._pages: dict[str, QWidget] = {}
        self._active_task_page: TaskPage | None = None
        self._bml_page: QWidget | None = None
        self._shortcuts: list[QShortcut] = []
        self._backup_enabled = self.settings.value(
            "backup/enabled", True, type=bool
        )
        self._backup_root = Path(str(self.settings.value(
            "backup/root", str(default_backup_root())
        )))
        self._backup_checkboxes: list[QCheckBox] = []

        self.setWindowTitle(APPLICATION_TITLE)
        screen = QApplication.primaryScreen()
        available_size = (
            screen.availableGeometry().size()
            if screen is not None
            else QSize(1440, 900)
        )
        preferred_size = recommended_window_size(available_size)
        self.setMinimumSize(
            min(1000, preferred_size.width()),
            min(680, preferred_size.height()),
        )
        self.resize(preferred_size)

        self._build_ui()
        self._register_pages()
        self._configure_shortcuts()
        self._wire_path_history()
        self._restore_window_state()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("ApplicationRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        context_bar = QFrame()
        context_bar.setObjectName("ContextBar")
        context_bar.setFixedHeight(48)
        context_layout = QHBoxLayout(context_bar)
        context_layout.setContentsMargins(14, 0, 14, 0)
        context_layout.setSpacing(14)

        product_label = QLabel(PRODUCT_NAME.upper())
        product_label.setObjectName("ModuleCode")
        profile_label = QLabel("PROFILE: DEFAULT")
        profile_label.setObjectName("MutedText")
        self.target_label = QLabel("TARGET: NOT SELECTED")
        self.target_label.setObjectName("MutedText")
        build_label = QLabel(f"BUILD: {__version__}")
        build_label.setObjectName("MutedText")

        theme_label = QLabel("THEME")
        theme_label.setObjectName("ModuleCode")
        self.theme_combo = QComboBox()
        self.theme_combo.setFixedWidth(116)
        for theme, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, theme.value)
        selected_theme = normalize_theme(
            self.settings.value("appearance/theme", ThemeName.WHITE.value)
        )
        selected_index = self.theme_combo.findData(selected_theme.value)
        self.theme_combo.setCurrentIndex(max(0, selected_index))
        self.theme_combo.currentIndexChanged.connect(self._change_theme)

        context_layout.addWidget(product_label)
        context_layout.addSpacing(16)
        context_layout.addWidget(profile_label)
        context_layout.addSpacing(16)
        context_layout.addWidget(self.target_label)
        context_layout.addStretch(1)
        context_layout.addWidget(theme_label)
        context_layout.addWidget(self.theme_combo)
        context_layout.addWidget(build_label)

        body = QWidget()
        body.setObjectName("WindowBody")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.navigation = NavigationPanel()
        self.navigation.refresh_icons(selected_theme)
        self.navigation.page_selected.connect(self.show_page)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("PageStack")
        self.page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )
        body_layout.addWidget(self.navigation)
        body_layout.addWidget(self.page_stack, 1)

        self.task_status = TaskStatus()
        self.task_status.cancel_requested.connect(self._cancel_active_task)

        root_layout.addWidget(context_bar)
        root_layout.addWidget(body, 1)
        root_layout.addWidget(self.task_status)
        self.setCentralWidget(root)

    def _register_pages(self) -> None:
        self.dashboard_page = DashboardPage()
        self.dashboard_page.page_requested.connect(self.show_page)
        self.dashboard_page.clear_recent_requested.connect(
            self._clear_recent_paths
        )
        self.dashboard_page.backup_settings_requested.connect(
            self._show_backup_settings
        )
        self._add_backup_settings()
        self._add_page("overview", self.dashboard_page)

        replace_page = ReplacePage()
        self._add_page("replace", replace_page)
        self._add_backup_controls(replace_page)
        self._connect_task_page(replace_page)

        offset_page = OffsetPage()
        self._add_page("offset", offset_page)
        self._add_backup_controls(offset_page)
        self._connect_task_page(offset_page)

        folder_page = FolderCreatorPage()
        self._add_page("folder", folder_page)
        self._connect_task_page(folder_page)

        parents_page = ParentsPage()
        self._add_page("parents", parents_page)
        self._add_backup_controls(parents_page)
        self._connect_task_page(parents_page)

        links_page = LinksPage()
        self._add_page("links", links_page)
        self._add_backup_controls(links_page)
        self._connect_task_page(links_page)

        if BML_EDITOR_ENABLED:
            assert BmlPage is not None
            self._bml_page = BmlPage()
            self._add_page("bml", self._bml_page)
            self._connect_task_page(self._bml_page)

        parking_page = ParkingPage()
        self._add_page("parking", parking_page)
        self._add_backup_controls(parking_page)
        self._connect_task_page(parking_page)

        runway_page = RunwayPage()
        self._add_page("runway", runway_page)
        self._add_backup_controls(runway_page)
        self._connect_task_page(runway_page)

        self.tutorial_page = TutorialPage()
        self.tutorial_page.navigate_requested.connect(self.show_page)
        self._add_page("tutorial", self.tutorial_page)

        self.command_palette = CommandPalette(self)
        self.command_palette.page_requested.connect(self.show_page)

    def _configure_shortcuts(self) -> None:
        page_shortcuts = (
            ("Ctrl+1", "overview"),
            ("Ctrl+2", "replace"),
            ("Ctrl+3", "offset"),
            ("Ctrl+4", "runway"),
            ("Ctrl+5", "parking"),
            ("Ctrl+6", "folder"),
            ("Ctrl+7", "parents"),
            ("Ctrl+8", "links"),
            ("Ctrl+9", "bml"),
        )
        for sequence, page_id in page_shortcuts:
            if page_id not in self._pages:
                continue
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(
                lambda destination=page_id: self.show_page(destination)
            )
            self._shortcuts.append(shortcut)

        command_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        command_shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )
        command_shortcut.activated.connect(
            self.command_palette.show_palette
        )
        self._shortcuts.append(command_shortcut)

        help_shortcut = QShortcut(
            QKeySequence.StandardKey.HelpContents,
            self,
        )
        help_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        help_shortcut.activated.connect(self._show_help)
        self._shortcuts.append(help_shortcut)

    def _show_help(self) -> None:
        self.show_page("tutorial")
        self.tutorial_page.focus_search()

    def _wire_path_history(self) -> None:
        for page_id, scroll_area in self._pages.items():
            if page_id in {"overview", "tutorial"}:
                continue
            page = scroll_area.widget()
            if page is None:
                continue
            for picker in page.findChildren(PathPicker):
                picker.path_changed.connect(self._record_recent_path)
        self._refresh_recent_paths()

    def _recent_paths(self) -> tuple[str, ...]:
        return normalize_recent_paths(
            self.settings.value("recent/target_paths", [])
        )

    def _record_recent_path(self, value: str) -> None:
        value = value.strip()
        if not value or not Path(value).exists():
            return
        paths = normalize_recent_paths(
            [value, *self._recent_paths()]
        )
        self.settings.setValue("recent/target_paths", list(paths))
        self._refresh_recent_paths()

    def _clear_recent_paths(self) -> None:
        self.settings.remove("recent/target_paths")
        self._refresh_recent_paths()

    def _refresh_recent_paths(self) -> None:
        paths = self._recent_paths()
        self.dashboard_page.set_recent_paths(paths)
        if paths:
            selected = Path(paths[0])
            self.target_label.setText(f"TARGET: {selected.name.upper()}")
            self.target_label.setToolTip(paths[0])
        else:
            self.target_label.setText("TARGET: NOT SELECTED")
            self.target_label.setToolTip("")

    def _add_page(self, page_id: str, page: QWidget) -> None:
        scroll_area = QScrollArea()
        scroll_area.setObjectName("PageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )
        scroll_area.setMinimumSize(0, 0)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        page.setMinimumWidth(0)
        page.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        scroll_area.setWidget(page)

        self._pages[page_id] = scroll_area
        self.page_stack.addWidget(scroll_area)

    def _connect_task_page(self, page: TaskPage) -> None:
        controller = page.task_controller
        controller.start_guard = lambda: self._active_task_page is None
        controller.backup_root = self._backup_root
        if page is not self._bml_page:
            controller.backup_enabled = self._backup_enabled
        controller.started.connect(
            lambda label, active_page=page:
            self._on_task_started(active_page, label)
        )
        controller.progress.connect(self.task_status.update_progress)
        controller.completed.connect(self._on_task_completed)
        controller.cancelled.connect(
            lambda: self.task_status.complete("Task cancelled")
        )
        controller.failed.connect(
            lambda message, _details: self.task_status.fail(message)
        )
        controller.finished.connect(
            lambda active_page=page: self._on_task_finished(active_page)
        )

    def _add_backup_controls(self, page: TaskPage) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)
        checkbox = QCheckBox("Back up edited files")
        checkbox.setChecked(self._backup_enabled)
        checkbox.toggled.connect(self._set_backup_enabled)
        self._backup_checkboxes.append(checkbox)
        open_button = QPushButton("OPEN BACKUP FOLDER")
        open_button.hide()
        open_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(open_button.property("backup_path"))
            )
        )
        page.task_controller.completed.connect(
            lambda result: self._update_backup_button(open_button, result)
        )
        layout.addWidget(checkbox)
        layout.addStretch(1)
        layout.addWidget(open_button)
        setup_panel = page.layout().itemAt(1).widget()
        assert isinstance(setup_panel, QFrame)
        setup_panel.layout().addLayout(layout)

    def _update_backup_button(self, button: QPushButton, result: OperationResult) -> None:
        path = result.metrics.get("backup_path")
        if path:
            button.show()
            button.setProperty("backup_path", str(path))
            button.setToolTip(str(path))

    def _add_backup_settings(self) -> None:
        self._backup_dialog = QDialog(self)
        self._backup_dialog.setWindowTitle("Backup settings")
        self._backup_dialog.resize(680, 170)
        layout = QVBoxLayout(self._backup_dialog)
        note = QLabel(
            "Standard write tools use one shared backup setting. BML asks "
            "for a separate choice at each save. Keep backups outside the "
            "folder being edited."
        )
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        row = QHBoxLayout()
        self.backup_root_edit = QLineEdit(str(self._backup_root))
        self.backup_root_edit.setAccessibleName("Backup folder")
        self.backup_root_edit.setToolTip(str(self._backup_root))
        self.backup_root_edit.editingFinished.connect(self._set_backup_root)
        self.backup_browse_button = QPushButton("BROWSE")
        self.backup_browse_button.clicked.connect(self._browse_backup_root)
        row.addWidget(self.backup_root_edit, 1)
        row.addWidget(self.backup_browse_button)
        layout.addWidget(note)
        layout.addLayout(row)
        close_button = QPushButton("CLOSE")
        close_button.clicked.connect(self._backup_dialog.close)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _show_backup_settings(self) -> None:
        self.backup_root_edit.setText(str(self._backup_root))
        self.backup_root_edit.setCursorPosition(0)
        self._backup_dialog.show()
        self.backup_browse_button.setFocus()
        self._backup_dialog.raise_()
        self._backup_dialog.activateWindow()

    def _set_backup_enabled(self, enabled: bool) -> None:
        self._backup_enabled = enabled
        self.settings.setValue("backup/enabled", enabled)
        for checkbox in self._backup_checkboxes:
            if checkbox.isChecked() != enabled:
                checkbox.blockSignals(True)
                checkbox.setChecked(enabled)
                checkbox.blockSignals(False)
        for page in self._task_pages():
            if page is not self._bml_page:
                page.task_controller.backup_enabled = enabled

    def _set_backup_root(self) -> None:
        value = self.backup_root_edit.text().strip()
        if not value:
            self.backup_root_edit.setText(str(self._backup_root))
            return
        self._backup_root = Path(value).expanduser()
        self.settings.setValue("backup/root", str(self._backup_root))
        self.backup_root_edit.setToolTip(str(self._backup_root))
        for page in self._task_pages():
            page.task_controller.backup_root = self._backup_root

    def _browse_backup_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Select backup folder", str(self._backup_root)
        )
        if selected:
            self.backup_root_edit.setText(selected)
            self._set_backup_root()

    def _task_pages(self) -> list[TaskPage]:
        return [page.widget() for page_id, page in self._pages.items()
                if page_id not in {"overview", "tutorial"}]

    def show_page(self, page_id: str) -> None:
        page = self._pages.get(page_id)
        if page is None:
            return
        self.page_stack.setCurrentWidget(page)
        self.navigation.select_page(page_id)

    def _change_theme(self) -> None:
        application = QApplication.instance()
        if not isinstance(application, QApplication):
            return
        selected = normalize_theme(self.theme_combo.currentData())
        apply_theme(application, selected)
        self.navigation.refresh_icons(selected)
        self.settings.setValue("appearance/theme", selected.value)

    def _on_task_started(
        self,
        page: TaskPage,
        label: str,
    ) -> None:
        self._active_task_page = page
        self.task_status.start(label)

    def _on_task_completed(self, result: OperationResult) -> None:
        if result.status is OperationStatus.FAILED:
            self.task_status.fail(result.summary)
        elif result.status is OperationStatus.CANCELLED:
            self.task_status.complete(
                "Task cancelled; completed file changes remain"
                if result.changed_files else "Task cancelled"
            )
        else:
            self.task_status.complete(result.summary)

    def _on_task_finished(self, page: TaskPage) -> None:
        if self._active_task_page is page:
            self._active_task_page = None

    def _cancel_active_task(self) -> None:
        if self._active_task_page is not None:
            self.task_status.state_label.setText("CANCELLING")
            self.task_status.message_label.setText(
                "Waiting for a safe cancellation point..."
            )
            self._active_task_page.cancel_task()

    def _restore_window_state(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._ensure_useful_window_size(geometry is None)

        self.show_page("overview")

    def _ensure_useful_window_size(self, center_window: bool) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        preferred = recommended_window_size(available.size())
        target_width = min(
            available.width(),
            max(self.width(), preferred.width()),
        )
        target_height = min(
            available.height(),
            max(self.height(), preferred.height()),
        )
        self.resize(target_width, target_height)
        if center_window:
            frame = self.frameGeometry()
            frame.moveCenter(available.center())
            self.move(frame.topLeft())
        else:
            maximum_x = available.right() - target_width + 1
            maximum_y = available.bottom() - target_height + 1
            self.move(
                min(max(self.x(), available.left()), maximum_x),
                min(max(self.y(), available.top()), maximum_y),
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._active_task_page is not None:
            response = QMessageBox.question(
                self,
                "Task is running",
                "Cancel the active task before closing?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response == QMessageBox.StandardButton.Yes:
                self._cancel_active_task()
            event.ignore()
            return

        self.settings.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)

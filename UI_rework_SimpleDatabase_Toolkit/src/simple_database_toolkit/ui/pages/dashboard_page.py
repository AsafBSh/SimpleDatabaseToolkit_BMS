"""Simple Database Toolkit Home dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.ui.branding import (
    PRODUCT_NAME,
    find_media_asset,
)
from simple_database_toolkit.ui.components import MetricPanel, PageHeader
from simple_database_toolkit.build_profile import BML_EDITOR_ENABLED


class ScaledArtwork(QLabel):
    def __init__(
        self,
        pixmap: QPixmap,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = pixmap
        self.setObjectName("HomeArtwork")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(220, 170)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setPixmap(
            self._source.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class DashboardPage(QWidget):
    page_requested = Signal(str)
    clear_recent_requested = Signal()
    backup_settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "SYSTEM / OVERVIEW",
                PRODUCT_NAME,
                "Falcon BMS database tools in one modern workspace.",
            )
        )

        hero = QHBoxLayout()
        hero.setSpacing(10)

        artwork_panel = QFrame()
        artwork_panel.setObjectName("HeroPanel")
        artwork_layout = QVBoxLayout(artwork_panel)
        artwork_layout.setContentsMargins(12, 12, 12, 12)

        artwork_path = find_media_asset("Main.png")
        if artwork_path is not None:
            artwork_layout.addWidget(ScaledArtwork(QPixmap(str(artwork_path))))
        else:
            artwork_missing = QLabel("Home artwork is unavailable.")
            artwork_missing.setObjectName("MutedText")
            artwork_missing.setAlignment(Qt.AlignmentFlag.AlignCenter)
            artwork_layout.addWidget(artwork_missing)

        welcome_panel = QFrame()
        welcome_panel.setObjectName("Panel")
        welcome_panel.setFixedWidth(350)
        welcome_layout = QVBoxLayout(welcome_panel)
        welcome_layout.setContentsMargins(12, 11, 12, 12)
        welcome_layout.setSpacing(8)

        title = QLabel("APPLICATION HEALTH")
        title.setObjectName("PanelTitle")

        status = QLabel(
            "All operational tools are available. File operations run through "
            "validated service and background-task boundaries."
        )
        status.setWordWrap(True)

        tool_count = 8 if BML_EDITOR_ENABLED else 7
        operational_metric = MetricPanel("Operational tools", f"{tool_count} / {tool_count}")
        engine_metric = MetricPanel("Engine state", "READY")
        update_metric = MetricPanel("Updater", "PLANNED")
        help_metric = MetricPanel("Local help", "READY")
        health_grid = QGridLayout()
        health_grid.setSpacing(7)
        health_grid.addWidget(operational_metric, 0, 0)
        health_grid.addWidget(engine_metric, 0, 1)
        health_grid.addWidget(update_metric, 1, 0)
        health_grid.addWidget(help_metric, 1, 1)

        actions_title = QLabel("QUICK ACTIONS")
        actions_title.setObjectName("PanelTitle")
        actions_grid = QGridLayout()
        actions_grid.setSpacing(7)
        quick_actions = (
            ("REPLACE FEATURES", "replace"),
            ("OFFSET FIXER", "offset"),
            ("RUNWAY FIXER", "runway"),
            ("PARKING FIXER", "parking"),
        )
        for index, (label, page_id) in enumerate(quick_actions):
            button = QPushButton(label)
            if index == 0:
                button.setProperty("primary", True)
            button.clicked.connect(
                lambda _checked=False, destination=page_id:
                self.page_requested.emit(destination)
            )
            actions_grid.addWidget(button, index // 2, index % 2)

        welcome_layout.addWidget(title)
        welcome_layout.addWidget(status)
        welcome_layout.addLayout(health_grid)
        welcome_layout.addWidget(actions_title)
        welcome_layout.addLayout(actions_grid)

        hero.addWidget(artwork_panel, 1)
        hero.addWidget(welcome_panel)
        layout.addLayout(hero)

        lower_row = QHBoxLayout()
        lower_row.setSpacing(10)

        recent_panel = QFrame()
        recent_panel.setObjectName("Panel")
        recent_layout = QVBoxLayout(recent_panel)
        recent_layout.setContentsMargins(10, 9, 10, 10)
        recent_layout.setSpacing(7)
        recent_header = QHBoxLayout()
        recent_title = QLabel("RECENT TARGET PATHS")
        recent_title.setObjectName("PanelTitle")
        self.copy_recent_button = QPushButton("COPY SELECTED")
        self.clear_recent_button = QPushButton("CLEAR HISTORY")
        recent_header.addWidget(recent_title)
        recent_header.addStretch(1)
        recent_header.addWidget(self.copy_recent_button)
        recent_header.addWidget(self.clear_recent_button)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentPaths")
        self.recent_list.setMinimumHeight(105)
        self.recent_list.setAccessibleName("Recent target paths")
        recent_layout.addLayout(recent_header)
        recent_layout.addWidget(self.recent_list)

        shortcuts_panel = QFrame()
        shortcuts_panel.setObjectName("Panel")
        shortcuts_panel.setFixedWidth(300)
        shortcuts_layout = QVBoxLayout(shortcuts_panel)
        shortcuts_layout.setContentsMargins(11, 10, 11, 11)
        shortcuts_layout.setSpacing(7)
        shortcuts_title = QLabel("KEYBOARD ACCESS")
        shortcuts_title.setObjectName("PanelTitle")
        shortcut_text = QLabel(
            "Ctrl+K  Command search\n"
            "Ctrl+1…9  Open modules\n"
            "F1  Searchable tutorial\n"
            "Ctrl+F  Search inside Help"
        )
        shortcut_text.setObjectName("MutedText")
        shortcut_text.setWordWrap(True)
        update_note = QLabel(
            "UPDATE STATE\nGitHub Releases integration is not configured yet."
        )
        update_note.setObjectName("MutedText")
        update_note.setWordWrap(True)
        shortcuts_layout.addWidget(shortcuts_title)
        shortcuts_layout.addWidget(shortcut_text)
        self.backup_settings_button = QPushButton("BACKUP SETTINGS")
        self.backup_settings_button.clicked.connect(
            self.backup_settings_requested.emit
        )
        shortcuts_layout.addWidget(self.backup_settings_button)
        shortcuts_layout.addStretch(1)
        shortcuts_layout.addWidget(update_note)

        lower_row.addWidget(recent_panel, 1)
        lower_row.addWidget(shortcuts_panel)
        layout.addLayout(lower_row)
        layout.addStretch(1)

        self.copy_recent_button.clicked.connect(self._copy_recent_path)
        self.clear_recent_button.clicked.connect(
            self.clear_recent_requested.emit
        )
        self.set_recent_paths(())

    def set_recent_paths(self, paths: tuple[str, ...] | list[str]) -> None:
        self.recent_list.clear()
        for path in paths:
            self.recent_list.addItem(path)
        if self.recent_list.count() == 0:
            self.recent_list.addItem("No recently selected targets.")
            self.recent_list.item(0).setFlags(Qt.ItemFlag.NoItemFlags)
            self.copy_recent_button.setEnabled(False)
            self.clear_recent_button.setEnabled(False)
        else:
            self.recent_list.setCurrentRow(0)
            self.copy_recent_button.setEnabled(True)
            self.clear_recent_button.setEnabled(True)

    def _copy_recent_path(self) -> None:
        item = self.recent_list.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.clipboard().setText(item.text())

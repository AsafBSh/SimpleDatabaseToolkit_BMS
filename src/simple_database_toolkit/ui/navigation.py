"""Grouped navigation for Simple Database Toolkit."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.ui.branding import (
    PRODUCT_NAME,
    PRODUCT_SUBTITLE,
)
from simple_database_toolkit.ui.theme import PALETTES, ThemeName
from simple_database_toolkit.build_profile import page_enabled


NAVIGATION_GROUPS = [
    (
        "HOME",
        [
            (
                "overview",
                "Overview",
                QStyle.StandardPixmap.SP_DirHomeIcon,
            )
        ],
    ),
    (
        "FEATURES",
        [
            (
                "replace",
                "Replace Features",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            ),
            (
                "offset",
                "Offset Fixer",
                QStyle.StandardPixmap.SP_BrowserReload,
            ),
        ],
    ),
    (
        "AIRBASE",
        [
            (
                "runway",
                "Runway Fixer",
                QStyle.StandardPixmap.SP_ArrowForward,
            ),
            (
                "parking",
                "Parking Fixer",
                QStyle.StandardPixmap.SP_DriveHDIcon,
            ),
        ],
    ),
    (
        "DATABASE",
        [
            (
                "folder",
                "Folder Creator",
                QStyle.StandardPixmap.SP_DirIcon,
            ),
            (
                "parents",
                "Reformat Parents",
                QStyle.StandardPixmap.SP_FileDialogListView,
            ),
            (
                "links",
                "Links Generator",
                QStyle.StandardPixmap.SP_FileLinkIcon,
            ),
        ],
    ),
    (
        "MODELS",
        [("bml", "BML Editor", QStyle.StandardPixmap.SP_FileIcon)],
    ),
    (
        "HELP",
        [
            (
                "tutorial",
                "Tutorial",
                QStyle.StandardPixmap.SP_DialogHelpButton,
            )
        ],
    ),
]


class NavigationPanel(QFrame):
    page_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavigationPanel")
        self.setFixedWidth(238)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 13, 9, 12)
        layout.setSpacing(1)

        app_name = QLabel(PRODUCT_NAME)
        app_name.setObjectName("AppName")
        app_name.setWordWrap(False)

        subtitle = QLabel(PRODUCT_SUBTITLE)
        subtitle.setObjectName("ModuleCode")

        layout.addWidget(app_name)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        self._buttons: dict[str, QPushButton] = {}
        self._icon_types: dict[str, QStyle.StandardPixmap] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        for group_name, pages in NAVIGATION_GROUPS:
            pages = [page for page in pages if page_enabled(page[0])]
            if not pages:
                continue
            group_label = QLabel(group_name)
            group_label.setObjectName("NavigationGroup")
            layout.addWidget(group_label)

            for page_id, title, icon_type in pages:
                button = QPushButton(title)
                button.setCheckable(True)
                button.setProperty("nav", True)
                button.setIconSize(QSize(14, 14))
                button.clicked.connect(
                    lambda _checked=False, selected=page_id:
                    self.page_selected.emit(selected)
                )
                self._button_group.addButton(button)
                self._buttons[page_id] = button
                self._icon_types[page_id] = icon_type
                layout.addWidget(button)

        layout.addStretch(1)

        self.select_page("overview")

    def refresh_icons(self, theme: ThemeName) -> None:
        palette = PALETTES[theme]
        for page_id, icon_type in self._icon_types.items():
            source = self.style().standardIcon(icon_type).pixmap(14, 14)
            icon = QIcon()
            icon.addPixmap(
                self._tint_icon(source, QColor(palette["MUTED"])),
                QIcon.Mode.Normal,
                QIcon.State.Off,
            )
            icon.addPixmap(
                self._tint_icon(source, QColor(palette["TEXT"])),
                QIcon.Mode.Active,
                QIcon.State.Off,
            )
            selected = self._tint_icon(
                source,
                QColor(palette["ON_ACCENT"]),
            )
            icon.addPixmap(
                selected,
                QIcon.Mode.Normal,
                QIcon.State.On,
            )
            icon.addPixmap(
                selected,
                QIcon.Mode.Active,
                QIcon.State.On,
            )
            self._buttons[page_id].setIcon(icon)

    @staticmethod
    def _tint_icon(source: QPixmap, color: QColor) -> QPixmap:
        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return tinted

    def select_page(self, page_id: str) -> None:
        button = self._buttons.get(page_id)
        if button is not None:
            button.setChecked(True)

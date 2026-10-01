"""Non-destructive command search for page navigation."""

from __future__ import annotations

from dataclasses import dataclass

from simple_database_toolkit.build_profile import page_enabled

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class CommandEntry:
    page_id: str
    category: str
    title: str
    shortcut: str
    keywords: str = ""

    @property
    def search_text(self) -> str:
        return (
            f"{self.title} {self.category} {self.page_id} {self.keywords}"
        ).casefold()


COMMAND_ENTRIES: tuple[CommandEntry, ...] = (
    CommandEntry("overview", "Home", "Overview", "Ctrl+1", "dashboard health"),
    CommandEntry(
        "replace",
        "Features",
        "Replace Features",
        "Ctrl+2",
        "FED FeatureCtIdx",
    ),
    CommandEntry(
        "offset",
        "Features",
        "Offset Fixer",
        "Ctrl+3",
        "FED position rotation heading",
    ),
    CommandEntry(
        "runway",
        "Airbase",
        "Runway Dimension Fixer",
        "Ctrl+4",
        "PHD PDX crossing paths",
    ),
    CommandEntry(
        "parking",
        "Airbase",
        "Parking Fixer",
        "Ctrl+5",
        "hangar relocation preview",
    ),
    CommandEntry(
        "folder",
        "Database",
        "Folder Creator",
        "Ctrl+6",
        "model folders Parent.dat",
    ),
    CommandEntry(
        "parents",
        "Database",
        "Reformat Parents",
        "Ctrl+7",
        "Parent.dat BML references",
    ),
    CommandEntry(
        "links",
        "Database",
        "Links Generator",
        "Ctrl+8",
        "CSV LUT neighbor",
    ),
    CommandEntry(
        "bml",
        "Models",
        "BML Editor",
        "Ctrl+9",
        "texture skinset material",
    ),
    CommandEntry("tutorial", "Help", "Tutorial", "F1", "documentation search"),
)


class CommandPalette(QDialog):
    page_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Go to module")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        title = QLabel("COMMAND SEARCH")
        title.setObjectName("PanelTitle")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Type a module, action, or file format…"
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setAccessibleName("Command search")
        self.result_list = QListWidget()
        self.result_list.setObjectName("CommandResults")
        self.result_list.setUniformItemSizes(True)
        self.result_list.setAccessibleName("Command results")
        hint = QLabel(
            "Enter opens the selected module • Esc closes • navigation only"
        )
        hint.setObjectName("MutedText")
        layout.addWidget(title)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.result_list)
        layout.addWidget(hint)

        self.search_edit.textChanged.connect(self._filter)
        self.search_edit.returnPressed.connect(self._activate_current)
        self.result_list.itemActivated.connect(self._activate_item)
        self._filter("")

    def show_palette(self) -> None:
        self.search_edit.clear()
        self._filter("")
        self.open()
        self.raise_()
        self.activateWindow()
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _filter(self, query: str) -> None:
        normalized = " ".join(query.casefold().split())
        entries = [
            entry
            for entry in COMMAND_ENTRIES
            if page_enabled(entry.page_id) and (not normalized or normalized in entry.search_text)
        ]
        self.result_list.clear()
        for entry in entries:
            item = QListWidgetItem(
                f"{entry.category.upper()}  /  {entry.title}"
                f"                                      {entry.shortcut}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.page_id)
            item.setToolTip(f"Open {entry.title} ({entry.shortcut})")
            self.result_list.addItem(item)
        if entries:
            self.result_list.setCurrentRow(0)

    def _activate_current(self) -> None:
        self._activate_item(self.result_list.currentItem())

    def _activate_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        page_id = str(item.data(Qt.ItemDataRole.UserRole))
        if page_id:
            self.page_requested.emit(page_id)
            self.accept()

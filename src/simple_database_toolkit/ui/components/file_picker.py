"""Reusable directory picker with a read-only path field."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PathSelectionMode(str, Enum):
    DIRECTORY = "directory"
    XML_FILE = "xml_file"
    DAT_FILE = "dat_file"
    CSV_FILE = "csv_file"
    JSON_FILE = "json_file"
    SAVE_CSV_FILE = "save_csv_file"


class PathPicker(QWidget):
    path_changed = Signal(str)

    def __init__(
        self,
        label: str = "Target directory",
        dialog_title: str = "Select directory",
        mode: PathSelectionMode = PathSelectionMode.DIRECTORY,
        parent: QWidget | None = None,
        *,
        placeholder_text: str | None = None,
        help_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.dialog_title = dialog_title
        self.mode = mode
        self._placeholder_text = placeholder_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self._label_widget = QLabel(label)
        self._label_widget.setObjectName("MutedText")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText(self._placeholder_for_mode())

        self.browse_button = QPushButton("SELECT TARGET")
        self.browse_button.clicked.connect(self._browse)

        self._help_widget = QLabel(help_text or "")
        self._help_widget.setObjectName("MutedText")
        self._help_widget.setWordWrap(True)
        self._help_widget.setVisible(bool(help_text))

        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)

        layout.addWidget(self._label_widget)
        layout.addLayout(row)
        layout.addWidget(self._help_widget)

    @property
    def path(self) -> Path | None:
        value = self.path_edit.text().strip()
        return Path(value) if value else None

    def set_path(self, path: str | Path) -> None:
        value = str(path)
        self.path_edit.setText(value)
        self.path_changed.emit(value)

    def clear(self) -> None:
        self.path_edit.clear()
        self.path_changed.emit("")

    def set_mode(
        self,
        mode: PathSelectionMode,
        *,
        label: str | None = None,
        dialog_title: str | None = None,
        placeholder_text: str | None = None,
        help_text: str | None = None,
    ) -> None:
        self.mode = mode
        if label is not None:
            self._label_widget.setText(label)
        if dialog_title is not None:
            self.dialog_title = dialog_title
        self._placeholder_text = placeholder_text
        self._help_widget.setText(help_text or "")
        self._help_widget.setVisible(bool(help_text))
        self.path_edit.setPlaceholderText(self._placeholder_for_mode())
        self.clear()

    def _placeholder_for_mode(self) -> str:
        if self._placeholder_text:
            return self._placeholder_text
        if self.mode is PathSelectionMode.XML_FILE:
            return "No XML file selected"
        if self.mode is PathSelectionMode.DAT_FILE:
            return "No Parent.dat selected"
        if self.mode is PathSelectionMode.CSV_FILE:
            return "No CSV file selected"
        if self.mode is PathSelectionMode.JSON_FILE:
            return "No LUT JSON selected (optional)"
        if self.mode is PathSelectionMode.SAVE_CSV_FILE:
            return "No output CSV selected"
        return "No directory selected"

    def _browse(self) -> None:
        if self.mode is PathSelectionMode.XML_FILE:
            selected, _selected_filter = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                self.path_edit.text(),
                "XML files (*.xml);;All files (*)",
            )
        elif self.mode is PathSelectionMode.DAT_FILE:
            selected, _selected_filter = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                self.path_edit.text(),
                "Parent.dat files (Parent.dat parent.dat);;"
                "DAT files (*.dat);;All files (*)",
            )
        elif self.mode is PathSelectionMode.CSV_FILE:
            selected, _selected_filter = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                self.path_edit.text(),
                "CSV files (*.csv);;All files (*)",
            )
        elif self.mode is PathSelectionMode.JSON_FILE:
            selected, _selected_filter = QFileDialog.getOpenFileName(
                self,
                self.dialog_title,
                self.path_edit.text(),
                "JSON files (*.json);;All files (*)",
            )
        elif self.mode is PathSelectionMode.SAVE_CSV_FILE:
            selected, _selected_filter = QFileDialog.getSaveFileName(
                self,
                self.dialog_title,
                self.path_edit.text(),
                "CSV files (*.csv);;All files (*)",
            )
            if selected and Path(selected).suffix.casefold() != ".csv":
                selected = f"{selected}.csv"
        else:
            selected = QFileDialog.getExistingDirectory(
                self,
                self.dialog_title,
                self.path_edit.text(),
            )
        if selected:
            self.set_path(selected)


class DirectoryPicker(PathPicker):
    def __init__(
        self,
        label: str = "Target directory",
        dialog_title: str = "Select directory",
        parent: QWidget | None = None,
        *,
        placeholder_text: str | None = None,
        help_text: str | None = None,
    ) -> None:
        super().__init__(
            label=label,
            dialog_title=dialog_title,
            mode=PathSelectionMode.DIRECTORY,
            parent=parent,
            placeholder_text=placeholder_text,
            help_text=help_text,
        )

"""Structured diagnostic table used by all operational pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.domain import DiagnosticEvent, DiagnosticSeverity


SEVERITY_COLORS = {
    DiagnosticSeverity.INFO: QColor("#8b949e"),
    DiagnosticSeverity.SUCCESS: QColor("#3fb950"),
    DiagnosticSeverity.WARNING: QColor("#d29922"),
    DiagnosticSeverity.ERROR: QColor("#f85149"),
}


class DiagnosticLog(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._errors_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            ["TIME", "LEVEL", "MODULE", "TARGET", "MESSAGE"]
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.tree.setUniformRowHeights(True)

        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(3, 180)

        layout.addWidget(self.tree)

    def clear(self) -> None:
        self.tree.clear()

    def set_errors_only(self, enabled: bool) -> None:
        self._errors_only = enabled
        visible_severities = {
            DiagnosticSeverity.WARNING.value,
            DiagnosticSeverity.ERROR.value,
        }
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            severity = item.data(1, Qt.ItemDataRole.UserRole)
            item.setHidden(enabled and severity not in visible_severities)

    def append_event(self, event: DiagnosticEvent) -> None:
        timestamp = event.timestamp.astimezone().strftime("%H:%M:%S.%f")[:-3]
        item = QTreeWidgetItem(
            [
                timestamp,
                event.severity.value.upper(),
                event.module.upper(),
                event.target,
                event.message,
            ]
        )
        color = SEVERITY_COLORS[event.severity]
        item.setData(
            1,
            Qt.ItemDataRole.UserRole,
            event.severity.value,
        )
        item.setForeground(1, color)
        item.setForeground(4, color)
        self.tree.addTopLevelItem(item)
        item.setHidden(
            self._errors_only
            and event.severity
            not in {
                DiagnosticSeverity.WARNING,
                DiagnosticSeverity.ERROR,
            }
        )
        if not item.isHidden():
            self.tree.scrollToItem(item)

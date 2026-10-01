"""Compact Technical Console metric display."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MetricPanel(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "0",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricPanel")
        self.setMinimumHeight(62)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(0)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setMinimumHeight(29)

        label_widget = QLabel(label.upper())
        label_widget.setObjectName("MetricLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setMinimumHeight(17)

        layout.addWidget(self.value_label)
        layout.addWidget(label_widget)

    def set_value(self, value: object) -> None:
        self.value_label.setText(str(value))

"""Persistent task state displayed at the bottom of the main window."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from simple_database_toolkit.domain import ProgressUpdate


class TaskStatus(QFrame):
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 7, 14, 7)
        layout.setSpacing(10)

        self.state_label = QLabel("READY")
        self.state_label.setObjectName("ModuleCode")
        self.state_label.setMinimumWidth(90)

        self.message_label = QLabel("No active task")
        self.message_label.setObjectName("MutedText")

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(170)

        self.cancel_button = QPushButton("CANCEL")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_requested)

        layout.addWidget(self.state_label)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_button)

    def start(self, label: str) -> None:
        self.state_label.setText("RUNNING")
        self.message_label.setText(label)
        self.progress_bar.setRange(0, 0)
        self.cancel_button.setEnabled(True)

    def update_progress(self, update: ProgressUpdate) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(update.percent)
        self.message_label.setText(update.message or "Processing")

    def complete(self, message: str) -> None:
        self.state_label.setText("COMPLETE")
        self.message_label.setText(message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.cancel_button.setEnabled(False)

    def fail(self, message: str) -> None:
        self.state_label.setText("FAILED")
        self.message_label.setText(message)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(False)

    def reset(self) -> None:
        self.state_label.setText("READY")
        self.message_label.setText("No active task")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.cancel_button.setEnabled(False)

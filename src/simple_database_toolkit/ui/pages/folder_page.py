"""Technical Console implementation of the Folder Creator tool."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
    OperationResult,
    OperationStatus,
)
from simple_database_toolkit.services import FolderCreateRequest, create_folders
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    DirectoryPicker,
    MetricPanel,
    PageHeader,
)
from simple_database_toolkit.workers import TaskController


class FolderCreatorPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_controller = TaskController(self)

        self._build_ui()
        self._connect_signals()
        self._update_requested_count()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "DATABASE / FOLDER CREATOR",
                "Folder Creator",
                "Create a validated range of numbered model folders with "
                "optional Parent.dat files.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(11)

        panel_title = QLabel("OPERATION PARAMETERS")
        panel_title.setObjectName("PanelTitle")
        setup_layout.addWidget(panel_title)

        range_layout = QGridLayout()
        range_layout.setHorizontalSpacing(10)
        range_layout.setVerticalSpacing(5)

        start_label = QLabel("Start number")
        start_label.setObjectName("MutedText")
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 999_999)
        self.start_spin.setValue(1)

        end_label = QLabel("End number")
        end_label.setObjectName("MutedText")
        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 999_999)
        self.end_spin.setValue(10)

        self.parent_checkbox = QCheckBox("Create Parent.dat in every folder")
        self.parent_checkbox.setChecked(False)

        range_layout.addWidget(start_label, 0, 0)
        range_layout.addWidget(end_label, 0, 1)
        range_layout.addWidget(self.start_spin, 1, 0)
        range_layout.addWidget(self.end_spin, 1, 1)
        range_layout.addWidget(self.parent_checkbox, 1, 2)
        range_layout.setColumnStretch(0, 1)
        range_layout.setColumnStretch(1, 1)
        range_layout.setColumnStretch(2, 2)

        setup_layout.addLayout(range_layout)

        self.directory_picker = DirectoryPicker(
            "Parent folder for the numbered directories",
            "Select parent folder for numbered directories",
            placeholder_text=(
                "Select the existing folder that will receive 1, 2, 3, ..."
            ),
            help_text=(
                "The tool creates numbered child folders directly inside this "
                "folder. It does not search or modify an existing theater."
            ),
        )
        setup_layout.addWidget(self.directory_picker)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.create_button = QPushButton("EXECUTE CREATE")
        self.create_button.setProperty("primary", True)

        self.clear_button = QPushButton("CLEAR OUTPUT")

        self.request_summary = QLabel()
        self.request_summary.setObjectName("MutedText")
        self.request_summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        action_row.addWidget(self.create_button)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        action_row.addWidget(self.request_summary)
        setup_layout.addLayout(action_row)

        layout.addWidget(setup_panel)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)

        log_panel = QFrame()
        log_panel.setObjectName("Panel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(10, 9, 10, 10)
        log_layout.setSpacing(7)

        log_title = QLabel("DIAGNOSTIC OUTPUT")
        log_title.setObjectName("PanelTitle")
        self.diagnostic_log = DiagnosticLog()
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.diagnostic_log, 1)

        metrics_panel = QFrame()
        metrics_panel.setObjectName("Panel")
        metrics_panel.setFixedWidth(280)
        metrics_layout = QVBoxLayout(metrics_panel)
        metrics_layout.setContentsMargins(10, 9, 10, 10)
        metrics_layout.setSpacing(7)

        metrics_title = QLabel("SESSION METRICS")
        metrics_title.setObjectName("PanelTitle")
        self.requested_metric = MetricPanel("Requested", "0")
        self.created_metric = MetricPanel("Created", "0")
        self.parent_metric = MetricPanel("Parent files", "0")
        self.result_label = QLabel("No operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(7)
        metric_grid.addWidget(self.requested_metric, 0, 0)
        metric_grid.addWidget(self.created_metric, 0, 1)
        metric_grid.addWidget(self.parent_metric, 1, 0, 1, 2)

        metrics_layout.addWidget(metrics_title)
        metrics_layout.addLayout(metric_grid)
        metrics_layout.addWidget(self.result_label)
        metrics_layout.addStretch(1)

        output_row.addWidget(log_panel, 1)
        output_row.addWidget(metrics_panel)
        layout.addLayout(output_row, 1)

    def _connect_signals(self) -> None:
        self.start_spin.valueChanged.connect(self._update_requested_count)
        self.end_spin.valueChanged.connect(self._update_requested_count)
        self.parent_checkbox.toggled.connect(self._update_requested_count)
        self.create_button.clicked.connect(self._start_creation)
        self.clear_button.clicked.connect(self._clear_output)

        self.task_controller.started.connect(self._on_started)
        self.task_controller.diagnostic.connect(
            self.diagnostic_log.append_event
        )
        self.task_controller.completed.connect(self._on_completed)
        self.task_controller.cancelled.connect(self._on_cancelled)
        self.task_controller.failed.connect(self._on_failed)
        self.task_controller.finished.connect(self._on_finished)

    def _update_requested_count(self) -> None:
        count = max(0, self.end_spin.value() - self.start_spin.value() + 1)
        suffix = " + Parent.dat" if self.parent_checkbox.isChecked() else ""
        self.request_summary.setText(f"REQUESTED: {count} FOLDERS{suffix}")
        self.requested_metric.set_value(count)

    def _start_creation(self) -> None:
        directory = self.directory_picker.path
        if directory is None:
            QMessageBox.warning(
                self,
                "Target required",
                "Select a target directory before starting.",
            )
            return

        request = FolderCreateRequest(
            directory=Path(directory),
            start=self.start_spin.value(),
            end=self.end_spin.value(),
            include_parent_dat=self.parent_checkbox.isChecked(),
        )

        confirmation = QMessageBox.question(
            self,
            "Confirm folder creation",
            f"Create {request.count} numbered folder(s) in:\n"
            f"{request.directory}\n\n"
            f"Range: {request.start} through {request.end}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        self._clear_output()
        started = self.task_controller.start(
            "Creating numbered folders",
            lambda context: create_folders(request, context),
        )
        if not started:
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _clear_output(self) -> None:
        self.diagnostic_log.clear()
        self.created_metric.set_value(0)
        self.parent_metric.set_value(0)
        self.result_label.setText("No operation has run.")

    def _on_started(self, _label: str) -> None:
        self.create_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        self.created_metric.set_value(result.metrics.get("created", 0))
        self.parent_metric.set_value(result.metrics.get("parent_files", 0))
        self.result_label.setText(result.summary)

        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText("CANCELLED: no new folders retained")

    def _on_cancelled(self) -> None:
        self.result_label.setText("CANCELLED: no new folders retained")

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Folder Creator",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self.create_button.setEnabled(True)
        self.clear_button.setEnabled(True)

    def cancel_task(self) -> None:
        self.task_controller.cancel()

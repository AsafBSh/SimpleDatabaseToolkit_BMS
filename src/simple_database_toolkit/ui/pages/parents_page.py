"""PySide6 implementation of Reformat Parents."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
    OperationResult,
    OperationStatus,
)
from simple_database_toolkit.services import (
    ParentMode,
    ParentRequest,
    check_parent_bml_files,
    check_parent_fields,
    reformat_parents,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.workers import TaskController, TaskOperation


class ParentsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_controller = TaskController(self)
        self._current_action = ""

        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "DATABASE / PARENTS",
                "Reformat Parents",
                "Validate and normalize Parent.dat fields and their BML "
                "model references.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(10)

        setup_title = QLabel("TARGET AND OPTIONS")
        setup_title.setObjectName("PanelTitle")
        setup_layout.addWidget(setup_title)

        options = QGridLayout()
        options.setHorizontalSpacing(12)
        options.setVerticalSpacing(5)

        mode_label = QLabel("Target mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            "Single file — select Parent.dat",
            ParentMode.SINGLE,
        )
        self.mode_combo.addItem(
            "Folder tree — recursive Parent.dat search",
            ParentMode.BATCH,
        )

        conversion_label = QLabel("Reformat option")
        conversion_label.setObjectName("MutedText")
        self.lod_checkbox = QCheckBox(
            "Convert AddLOD model names from .lod to .bml"
        )

        options.addWidget(mode_label, 0, 0)
        options.addWidget(conversion_label, 0, 1)
        options.addWidget(self.mode_combo, 1, 0)
        options.addWidget(self.lod_checkbox, 1, 1)
        options.setColumnStretch(0, 1)
        options.setColumnStretch(1, 3)
        setup_layout.addLayout(options)

        self.target_picker = PathPicker()
        setup_layout.addWidget(self.target_picker)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.reformat_button = QPushButton("REFORMAT PARENTS")
        self.reformat_button.setProperty("primary", True)
        self.fields_button = QPushButton("CHECK FIELDS")
        self.bml_button = QPushButton("CHECK BML FILES")
        self.clear_button = QPushButton("CLEAR OUTPUT")
        self.request_summary = QLabel()
        self.request_summary.setObjectName("MutedText")
        self.request_summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        action_row.addWidget(self.reformat_button)
        action_row.addWidget(self.fields_button)
        action_row.addWidget(self.bml_button)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        setup_layout.addLayout(action_row)
        setup_layout.addWidget(self.request_summary)
        layout.addWidget(setup_panel)

        output = QHBoxLayout()
        output.setSpacing(10)

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
        self.files_metric = MetricPanel("Files", "0")
        self.clean_metric = MetricPanel("Clean", "0")
        self.changed_metric = MetricPanel("Changed", "0")
        self.issues_metric = MetricPanel("Issues", "0")
        self.result_label = QLabel("No operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(7)
        metric_grid.addWidget(self.files_metric, 0, 0)
        metric_grid.addWidget(self.clean_metric, 0, 1)
        metric_grid.addWidget(self.changed_metric, 1, 0)
        metric_grid.addWidget(self.issues_metric, 1, 1)

        metrics_layout.addWidget(metrics_title)
        metrics_layout.addLayout(metric_grid)
        metrics_layout.addWidget(self.result_label)
        metrics_layout.addStretch(1)

        output.addWidget(log_panel, 1)
        output.addWidget(metrics_panel)
        layout.addLayout(output, 1)

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.lod_checkbox.toggled.connect(self._update_summary)
        self.reformat_button.clicked.connect(self._start_reformat)
        self.fields_button.clicked.connect(self._start_field_check)
        self.bml_button.clicked.connect(self._start_bml_check)
        self.clear_button.clicked.connect(self._clear_output)

        self.task_controller.started.connect(self._on_started)
        self.task_controller.diagnostic.connect(
            self.diagnostic_log.append_event
        )
        self.task_controller.completed.connect(self._on_completed)
        self.task_controller.cancelled.connect(self._on_cancelled)
        self.task_controller.failed.connect(self._on_failed)
        self.task_controller.finished.connect(self._on_finished)

    def _selected_mode(self) -> ParentMode:
        mode = self.mode_combo.currentData()
        try:
            return ParentMode(mode)
        except (TypeError, ValueError):
            return ParentMode.SINGLE

    def _on_mode_changed(self) -> None:
        if self._selected_mode() is ParentMode.BATCH:
            self.target_picker.set_mode(
                PathSelectionMode.DIRECTORY,
                label="Root folder to search recursively",
                dialog_title="Select root folder to search for Parent.dat",
                placeholder_text=(
                    "Select a root folder; every nested Parent.dat is searched"
                ),
                help_text=(
                    "The selected folder and all subfolders are searched "
                    "recursively. Select a folder, not a Parent.dat file."
                ),
            )
        else:
            self.target_picker.set_mode(
                PathSelectionMode.DAT_FILE,
                label="Exact Parent.dat file",
                dialog_title="Select the Parent.dat file to process",
                placeholder_text="Select one exact Parent.dat file",
                help_text=(
                    "Only this Parent.dat is checked or reformatted; sibling "
                    "and nested folders are not searched."
                ),
            )
        self._update_summary()

    def _update_summary(self) -> None:
        mode = (
            "FOLDER TREE"
            if self._selected_mode() is ParentMode.BATCH
            else "SINGLE FILE"
        )
        conversion = (
            "LOD → BML" if self.lod_checkbox.isChecked() else "KEEP NAMES"
        )
        self.request_summary.setText(f"{mode} / {conversion}")

    def _request(self) -> ParentRequest | None:
        target = self.target_picker.path
        if target is None:
            QMessageBox.warning(
                self,
                "Target required",
                (
                    "Select the exact Parent.dat file for Single file mode, "
                    "or a root folder for the recursive Folder tree mode."
                ),
            )
            return None
        return ParentRequest(
            target=Path(target),
            mode=self._selected_mode(),
            convert_lod_to_bml=self.lod_checkbox.isChecked(),
        )

    def _start_reformat(self) -> None:
        request = self._request()
        if request is None:
            return
        scope = (
            "every Parent.dat below the selected folder"
            if request.mode is ParentMode.BATCH
            else "the selected Parent.dat"
        )
        response = QMessageBox.question(
            self,
            "Confirm Parent.dat reformat",
            f"Rebuild and normalize {scope}?\n\n{request.target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self._begin(
            "reformat",
            "Reformatting Parent.dat files",
            lambda context: reformat_parents(request, context),
        )

    def _start_field_check(self) -> None:
        request = self._request()
        if request is not None:
            self._begin(
                "fields",
                "Checking Parent.dat fields",
                lambda context: check_parent_fields(request, context),
            )

    def _start_bml_check(self) -> None:
        request = self._request()
        if request is not None:
            self._begin(
                "bml",
                "Checking Parent.dat BML references",
                lambda context: check_parent_bml_files(request, context),
            )

    def _begin(
        self,
        action: str,
        label: str,
        operation: TaskOperation,
    ) -> None:
        self._clear_output()
        self._current_action = action
        if not self.task_controller.start(label, operation):
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _clear_output(self) -> None:
        self.diagnostic_log.clear()
        self.files_metric.set_value(0)
        self.clean_metric.set_value(0)
        self.changed_metric.set_value(0)
        self.issues_metric.set_value(0)
        self.result_label.setText("No operation has run.")

    def _on_started(self, _label: str) -> None:
        self._set_actions_enabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        files = int(result.metrics.get("files", 0))
        errors = int(result.metrics.get("errors", 0))
        clean = int(
            result.metrics.get(
                "valid",
                result.metrics.get("clean", max(0, files - errors)),
            )
        )
        issue_count = (
            int(result.metrics.get("issues", 0))
            + int(result.metrics.get("missing", 0))
            + int(result.metrics.get("unreferenced", 0))
            + errors
        )

        self.files_metric.set_value(files)
        self.clean_metric.set_value(clean)
        self.changed_metric.set_value(result.metrics.get("changed", 0))
        self.issues_metric.set_value(issue_count)
        self.result_label.setText(result.summary)
        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText(f"CANCELLED: {result.summary}")

    def _on_cancelled(self) -> None:
        self.result_label.setText(
            "CANCELLED: completed files were retained safely"
        )

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Reformat Parents",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self._current_action = ""
        self._set_actions_enabled(True)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.reformat_button.setEnabled(enabled)
        self.fields_button.setEnabled(enabled)
        self.bml_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

    def cancel_task(self) -> None:
        self.task_controller.cancel()

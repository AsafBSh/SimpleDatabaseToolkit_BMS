"""Technical Console implementation of Replace Features."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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
from simple_database_toolkit.services import (
    ReplaceFeatureRequest,
    ReplaceMode,
    replace_features,
    scan_replacements,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.workers import TaskController, TaskOperation


class ReplacePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_controller = TaskController(self)
        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "FEATURES / REPLACE",
                "Replace Features",
                "Scan for a FeatureCtIdx and replace it in one objective or "
                "across an entire theater.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(11)

        title = QLabel("OPERATION PARAMETERS")
        title.setObjectName("PanelTitle")
        setup_layout.addWidget(title)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(5)

        mode_label = QLabel("Target mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            "Single objective — select OCD folder",
            ReplaceMode.SINGLE,
        )
        self.mode_combo.addItem(
            "Entire theater — select Class Table XML",
            ReplaceMode.BATCH,
        )

        old_label = QLabel("Feature number to remove")
        old_label.setObjectName("MutedText")
        self.old_feature_spin = QSpinBox()
        self.old_feature_spin.setRange(0, 2_147_483_647)

        new_label = QLabel("Replacement feature number")
        new_label.setObjectName("MutedText")
        self.new_feature_spin = QSpinBox()
        self.new_feature_spin.setRange(0, 2_147_483_647)

        form.addWidget(mode_label, 0, 0)
        form.addWidget(old_label, 0, 1)
        form.addWidget(new_label, 0, 2)
        form.addWidget(self.mode_combo, 1, 0)
        form.addWidget(self.old_feature_spin, 1, 1)
        form.addWidget(self.new_feature_spin, 1, 2)
        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 1)
        setup_layout.addLayout(form)

        self.target_picker = PathPicker()
        setup_layout.addWidget(self.target_picker)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.scan_button = QPushButton("SCAN TARGET")
        self.apply_button = QPushButton("EXECUTE REPLACE")
        self.apply_button.setProperty("primary", True)
        self.clear_button = QPushButton("CLEAR OUTPUT")

        self.request_summary = QLabel("READY FOR INPUT")
        self.request_summary.setObjectName("MutedText")

        actions.addWidget(self.scan_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.clear_button)
        actions.addStretch(1)
        actions.addWidget(self.request_summary)
        setup_layout.addLayout(actions)

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
        self.matches_metric = MetricPanel("Matches", "0")
        self.changed_metric = MetricPanel("Changed", "0")
        self.errors_metric = MetricPanel("Errors", "0")
        self.result_label = QLabel("No operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(7)
        metric_grid.addWidget(self.files_metric, 0, 0)
        metric_grid.addWidget(self.matches_metric, 0, 1)
        metric_grid.addWidget(self.changed_metric, 1, 0)
        metric_grid.addWidget(self.errors_metric, 1, 1)

        metrics_layout.addWidget(metrics_title)
        metrics_layout.addLayout(metric_grid)
        metrics_layout.addWidget(self.result_label)
        metrics_layout.addStretch(1)

        output.addWidget(log_panel, 1)
        output.addWidget(metrics_panel)
        layout.addLayout(output, 1)

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.old_feature_spin.valueChanged.connect(self._update_summary)
        self.new_feature_spin.valueChanged.connect(self._update_summary)
        self.scan_button.clicked.connect(self._start_scan)
        self.apply_button.clicked.connect(self._start_apply)
        self.clear_button.clicked.connect(self._clear_output)

        self.task_controller.started.connect(self._on_started)
        self.task_controller.diagnostic.connect(
            self.diagnostic_log.append_event
        )
        self.task_controller.completed.connect(self._on_completed)
        self.task_controller.cancelled.connect(self._on_cancelled)
        self.task_controller.failed.connect(self._on_failed)
        self.task_controller.finished.connect(self._on_finished)

    def _on_mode_changed(self) -> None:
        mode = self._selected_mode()
        if mode is ReplaceMode.BATCH:
            self.target_picker.set_mode(
                PathSelectionMode.XML_FILE,
                label="Theater Class Table XML",
                dialog_title="Select theater Class Table XML",
                placeholder_text=(
                    "Select Falcon4_CT.xml beside ObjectiveRelatedData"
                ),
                help_text=(
                    "The tool scans OCD_* folders in the ObjectiveRelatedData "
                    "folder beside the selected Class Table XML."
                ),
            )
        else:
            self.target_picker.set_mode(
                PathSelectionMode.DIRECTORY,
                label="Single OCD objective folder",
                dialog_title="Select OCD_XXXXX objective folder",
                placeholder_text=(
                    "Select OCD_XXXXX containing FED_XXXXX.xml"
                ),
                help_text=(
                    "Only the matching FED XML in this one objective folder "
                    "is scanned or changed."
                ),
            )
        self._update_summary()

    def _selected_mode(self) -> ReplaceMode:
        value = self.mode_combo.currentData()
        try:
            return ReplaceMode(value)
        except (TypeError, ValueError):
            return ReplaceMode.SINGLE

    def _update_summary(self) -> None:
        self.request_summary.setText(
            f"{self._selected_mode().value.upper()} / "
            f"{self.old_feature_spin.value()} -> "
            f"{self.new_feature_spin.value()}"
        )

    def _build_request(self) -> ReplaceFeatureRequest | None:
        target = self.target_picker.path
        if target is None:
            QMessageBox.warning(
                self,
                "Target required",
                "Select an objective folder or Class Table XML first.",
            )
            return None

        old_number = self.old_feature_spin.value()
        new_number = self.new_feature_spin.value()
        if old_number == new_number:
            QMessageBox.warning(
                self,
                "No effective change",
                "The old and replacement feature numbers must differ.",
            )
            return None

        return ReplaceFeatureRequest(
            target=target,
            old_feature_number=old_number,
            new_feature_number=new_number,
            mode=self._selected_mode(),
        )

    def _start_scan(self) -> None:
        request = self._build_request()
        if request is None:
            return
        self._begin(
            "Scanning replacement candidates",
            lambda context: scan_replacements(request, context),
        )

    def _start_apply(self) -> None:
        request = self._build_request()
        if request is None:
            return

        answer = QMessageBox.question(
            self,
            "Confirm feature replacement",
            f"Replace FeatureCtIdx {request.old_feature_number} with "
            f"{request.new_feature_number}?\n\nTarget:\n{request.target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._begin(
            "Replacing feature numbers",
            lambda context: replace_features(request, context),
        )

    def _begin(self, label: str, operation: TaskOperation) -> None:
        self._clear_output()
        started = self.task_controller.start(label, operation)
        if not started:
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _clear_output(self) -> None:
        self.diagnostic_log.clear()
        self.files_metric.set_value(0)
        self.matches_metric.set_value(0)
        self.changed_metric.set_value(0)
        self.errors_metric.set_value(0)
        self.result_label.setText("No operation has run.")

    def _on_started(self, _label: str) -> None:
        self.scan_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        self.files_metric.set_value(result.metrics.get("files", 0))
        self.matches_metric.set_value(result.metrics.get("matches", 0))
        self.changed_metric.set_value(result.metrics.get("changed_files", 0))
        self.errors_metric.set_value(result.metrics.get("errors", 0))
        self.result_label.setText(result.summary)

        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText(
                "CANCELLED: completed files remain committed"
            )

    def _on_cancelled(self) -> None:
        self.result_label.setText("CANCELLED")

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Replace Features",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.apply_button.setEnabled(True)
        self.clear_button.setEnabled(True)

    def cancel_task(self) -> None:
        self.task_controller.cancel()

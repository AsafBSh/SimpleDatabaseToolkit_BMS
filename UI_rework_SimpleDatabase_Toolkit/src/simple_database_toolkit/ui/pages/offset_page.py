"""Technical Console implementation of the Offset Fixer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
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
    FeatureScanRequest,
    OffsetAdjustment,
    OffsetMode,
    OffsetOperation,
    OffsetRequest,
    apply_offset,
    scan_features,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.workers import TaskController, TaskOperation


OPERATION_LABELS = {
    OffsetOperation.XY: "Fix XY offsets",
    OffsetOperation.SET_Z: "Set Z",
    OffsetOperation.ROTATE: "Rotate heading",
    OffsetOperation.SET_HEADING: "Set heading",
    OffsetOperation.SET_VALUE: "Set value",
}


class OffsetPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_controller = TaskController(self)
        self.feature_counts: dict[int, int] = {}
        self._current_action = ""

        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()
        self._on_operation_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "FEATURES / OFFSET",
                "Offset Fixer",
                "Scan FeatureCtIdx values and apply heading-aware position, "
                "height, rotation, heading, or value changes.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(10)

        setup_title = QLabel("TARGET AND FEATURE")
        setup_title.setObjectName("PanelTitle")
        setup_layout.addWidget(setup_title)

        target_grid = QGridLayout()
        target_grid.setHorizontalSpacing(10)
        target_grid.setVerticalSpacing(5)

        mode_label = QLabel("Target mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            "Single objective — select OCD folder",
            OffsetMode.SINGLE,
        )
        self.mode_combo.addItem(
            "Entire theater — select Class Table XML",
            OffsetMode.BATCH,
        )

        feature_label = QLabel("Feature number")
        feature_label.setObjectName("MutedText")
        self.feature_spin = QSpinBox()
        self.feature_spin.setRange(0, 2_147_483_647)

        discovered_label = QLabel("Discovered features")
        discovered_label.setObjectName("MutedText")
        self.feature_combo = QComboBox()
        self.feature_combo.addItem("Scan target to populate", None)

        target_grid.addWidget(mode_label, 0, 0)
        target_grid.addWidget(feature_label, 0, 1)
        target_grid.addWidget(discovered_label, 0, 2)
        target_grid.addWidget(self.mode_combo, 1, 0)
        target_grid.addWidget(self.feature_spin, 1, 1)
        target_grid.addWidget(self.feature_combo, 1, 2)
        target_grid.setColumnStretch(0, 1)
        target_grid.setColumnStretch(1, 1)
        target_grid.setColumnStretch(2, 2)
        setup_layout.addLayout(target_grid)

        self.target_picker = PathPicker()
        setup_layout.addWidget(self.target_picker)

        target_actions = QHBoxLayout()
        self.scan_button = QPushButton("SCAN FEATURES")
        self.scan_button.setProperty("primary", True)
        target_actions.addWidget(self.scan_button)
        target_actions.addStretch(1)
        setup_layout.addLayout(target_actions)

        layout.addWidget(setup_panel)

        operation_panel = QFrame()
        operation_panel.setObjectName("Panel")
        operation_layout = QVBoxLayout(operation_panel)
        operation_layout.setContentsMargins(15, 13, 15, 15)
        operation_layout.setSpacing(9)

        operation_title = QLabel("TRANSFORMATION")
        operation_title.setObjectName("PanelTitle")
        operation_layout.addWidget(operation_title)

        operation_row = QHBoxLayout()
        operation_row.setSpacing(10)

        self.operation_combo = QComboBox()
        for operation, label in OPERATION_LABELS.items():
            self.operation_combo.addItem(label, operation)
        self.operation_combo.setMinimumWidth(180)

        self.parameter_stack = QStackedWidget()
        self.parameter_stack.addWidget(self._build_xy_parameters())
        self.parameter_stack.addWidget(
            self._build_value_parameter(
                "Z coordinate",
                -10_000,
                10_000,
                "z_spin",
            )
        )
        self.parameter_stack.addWidget(
            self._build_value_parameter(
                "Rotation delta (degrees)",
                -360_000,
                360_000,
                "rotation_spin",
            )
        )
        self.parameter_stack.addWidget(
            self._build_value_parameter(
                "Absolute heading (degrees)",
                0,
                360,
                "heading_spin",
            )
        )
        self.parameter_stack.addWidget(
            self._build_value_parameter(
                "Value (0-100)",
                0,
                100,
                "value_spin",
            )
        )

        operation_row.addWidget(self.operation_combo)
        operation_row.addWidget(self.parameter_stack, 1)
        operation_layout.addLayout(operation_row)

        apply_row = QHBoxLayout()
        apply_row.setSpacing(8)
        self.apply_button = QPushButton("EXECUTE CHANGE")
        self.apply_button.setProperty("primary", True)
        self.clear_button = QPushButton("CLEAR OUTPUT")
        self.request_summary = QLabel()
        self.request_summary.setObjectName("MutedText")

        apply_row.addWidget(self.apply_button)
        apply_row.addWidget(self.clear_button)
        apply_row.addStretch(1)
        apply_row.addWidget(self.request_summary)
        operation_layout.addLayout(apply_row)

        layout.addWidget(operation_panel)

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
        self.entries_metric = MetricPanel("Entries", "0")
        self.changed_metric = MetricPanel("Changed files", "0")
        self.errors_metric = MetricPanel("Errors", "0")
        self.result_label = QLabel("No operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(7)
        metric_grid.addWidget(self.files_metric, 0, 0)
        metric_grid.addWidget(self.entries_metric, 0, 1)
        metric_grid.addWidget(self.changed_metric, 1, 0)
        metric_grid.addWidget(self.errors_metric, 1, 1)

        metrics_layout.addWidget(metrics_title)
        metrics_layout.addLayout(metric_grid)
        metrics_layout.addWidget(self.result_label)
        metrics_layout.addStretch(1)

        output.addWidget(log_panel, 1)
        output.addWidget(metrics_panel)
        layout.addLayout(output, 1)

    def _build_xy_parameters(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)

        x_label = QLabel("Local X delta")
        x_label.setObjectName("MutedText")
        self.x_spin = self._double_spin(-1_000_000, 1_000_000)

        y_label = QLabel("Local Y delta")
        y_label.setObjectName("MutedText")
        self.y_spin = self._double_spin(-1_000_000, 1_000_000)

        layout.addWidget(x_label, 0, 0)
        layout.addWidget(y_label, 0, 1)
        layout.addWidget(self.x_spin, 1, 0)
        layout.addWidget(self.y_spin, 1, 1)
        return widget

    def _build_value_parameter(
        self,
        label: str,
        minimum: float,
        maximum: float,
        attribute_name: str,
    ) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label_widget = QLabel(label)
        label_widget.setObjectName("MutedText")
        spin = self._double_spin(minimum, maximum)
        setattr(self, attribute_name, spin)

        layout.addWidget(label_widget)
        layout.addWidget(spin)
        return widget

    @staticmethod
    def _double_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(3)
        spin.setSingleStep(1)
        return spin

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.operation_combo.currentIndexChanged.connect(
            self._on_operation_changed
        )
        self.target_picker.path_changed.connect(
            lambda _path: self._reset_feature_choices()
        )
        self.feature_combo.currentIndexChanged.connect(
            self._on_feature_selected
        )
        self.feature_spin.valueChanged.connect(self._update_summary)

        for spin in (
            self.x_spin,
            self.y_spin,
            self.z_spin,
            self.rotation_spin,
            self.heading_spin,
            self.value_spin,
        ):
            spin.valueChanged.connect(self._update_summary)

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
        if self._selected_mode() is OffsetMode.BATCH:
            self.target_picker.set_mode(
                PathSelectionMode.XML_FILE,
                label="Theater Class Table XML",
                dialog_title="Select theater Class Table XML",
                placeholder_text=(
                    "Select Falcon4_CT.xml beside ObjectiveRelatedData"
                ),
                help_text=(
                    "The feature scan and offset operation inspect FED XML "
                    "files under the adjacent ObjectiveRelatedData/OCD_* folders."
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
        self._reset_feature_choices()
        self._update_summary()

    def _selected_mode(self) -> OffsetMode:
        value = self.mode_combo.currentData()
        try:
            return OffsetMode(value)
        except (TypeError, ValueError):
            return OffsetMode.SINGLE

    def _selected_operation(self) -> OffsetOperation:
        value = self.operation_combo.currentData()
        try:
            return OffsetOperation(value)
        except (TypeError, ValueError):
            return OffsetOperation.XY

    def _on_operation_changed(self) -> None:
        self.parameter_stack.setCurrentIndex(
            self.operation_combo.currentIndex()
        )
        self._update_summary()

    def _on_feature_selected(self) -> None:
        feature = self.feature_combo.currentData()
        if isinstance(feature, int):
            self.feature_spin.setValue(feature)

    def _reset_feature_choices(self) -> None:
        self.feature_counts = {}
        self.feature_combo.clear()
        self.feature_combo.addItem("Scan target to populate", None)

    def _build_adjustment(self) -> OffsetAdjustment:
        operation = self._selected_operation()
        if operation is OffsetOperation.XY:
            return OffsetAdjustment(
                operation,
                x=self.x_spin.value(),
                y=self.y_spin.value(),
            )

        value_spin = {
            OffsetOperation.SET_Z: self.z_spin,
            OffsetOperation.ROTATE: self.rotation_spin,
            OffsetOperation.SET_HEADING: self.heading_spin,
            OffsetOperation.SET_VALUE: self.value_spin,
        }[operation]
        return OffsetAdjustment(operation, value=value_spin.value())

    def _update_summary(self) -> None:
        if not hasattr(self, "request_summary"):
            return
        adjustment = self._build_adjustment()
        estimate = self.feature_counts.get(self.feature_spin.value(), 0)
        self.request_summary.setText(
            f"FEATURE {self.feature_spin.value()} / "
            f"{adjustment.description.upper()} / EST. {estimate}"
        )

    def _require_target(self) -> Path | None:
        target = self.target_picker.path
        if target is None:
            QMessageBox.warning(
                self,
                "Target required",
                "Select an objective folder or Class Table XML first.",
            )
        return target

    def _start_scan(self) -> None:
        target = self._require_target()
        if target is None:
            return
        request = FeatureScanRequest(target, self._selected_mode())
        self._current_action = "scan"
        self._begin(
            "Scanning feature numbers",
            lambda context: scan_features(request, context),
        )

    def _start_apply(self) -> None:
        target = self._require_target()
        if target is None:
            return

        adjustment = self._build_adjustment()
        if (
            adjustment.operation is OffsetOperation.XY
            and adjustment.x == 0
            and adjustment.y == 0
        ):
            QMessageBox.warning(
                self,
                "No effective change",
                "Enter a non-zero X or Y offset.",
            )
            return
        if (
            adjustment.operation is OffsetOperation.ROTATE
            and adjustment.value == 0
        ):
            QMessageBox.warning(
                self,
                "No effective change",
                "Enter a non-zero rotation.",
            )
            return

        request = OffsetRequest(
            target=target,
            feature_number=self.feature_spin.value(),
            adjustment=adjustment,
            mode=self._selected_mode(),
        )
        estimated = self.feature_counts.get(request.feature_number, 0)
        answer = QMessageBox.question(
            self,
            "Confirm feature change",
            f"{adjustment.description}\n\n"
            f"Feature: {request.feature_number}\n"
            f"Estimated matching entries: {estimated}\n"
            f"Target:\n{request.target}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._current_action = "apply"
        self._begin(
            "Applying feature transformation",
            lambda context: apply_offset(request, context),
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
        self.entries_metric.set_value(0)
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
        self.entries_metric.set_value(result.metrics.get("entries", 0))
        self.changed_metric.set_value(result.metrics.get("changed_files", 0))
        self.errors_metric.set_value(result.metrics.get("errors", 0))
        self.result_label.setText(result.summary)

        if self._current_action == "scan":
            raw_features = result.metrics.get("features", {})
            if isinstance(raw_features, dict):
                self.feature_counts = {
                    int(feature): int(count)
                    for feature, count in raw_features.items()
                }
                self.feature_combo.clear()
                if self.feature_counts:
                    for feature, count in self.feature_counts.items():
                        self.feature_combo.addItem(
                            f"{feature} ({count}x)",
                            feature,
                        )
                    self.feature_combo.setCurrentIndex(0)
                else:
                    self.feature_combo.addItem("No features found", None)
                self._update_summary()

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
                module="Offset Fixer",
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

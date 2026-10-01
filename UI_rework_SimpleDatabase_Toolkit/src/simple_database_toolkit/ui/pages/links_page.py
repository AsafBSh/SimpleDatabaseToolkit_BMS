"""PySide6 implementation of Links Generator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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
    LinkGenerationRequest,
    LinkUpdateRequest,
    generate_all_links,
    update_changed_links,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.workers import TaskController, TaskOperation


class LinksPage(QWidget):
    GENERATE_INDEX = 0
    UPDATE_INDEX = 1

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
                "DATABASE / LINKS",
                "Links Generator",
                "Rebuild or selectively recalculate objective links using "
                "distance-to-cost heuristics.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(10)

        setup_title = QLabel("GENERATION PARAMETERS")
        setup_title.setObjectName("PanelTitle")
        setup_layout.addWidget(setup_title)

        options = QGridLayout()
        options.setHorizontalSpacing(12)
        options.setVerticalSpacing(5)

        mode_label = QLabel("Operation mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Generate — rebuild all links")
        self.mode_combo.addItem("Update — recalculate changed objectives")

        radius_label = QLabel("Neighbor radius (km)")
        radius_label.setObjectName("MutedText")
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.001, 100_000)
        self.radius_spin.setDecimals(3)
        self.radius_spin.setValue(120.0)
        self.radius_spin.setSuffix(" km")

        intersections_label = QLabel("Geometry")
        intersections_label.setObjectName("MutedText")
        self.intersections_checkbox = QCheckBox(
            "Allow links to cross existing segments"
        )

        options.addWidget(mode_label, 0, 0)
        options.addWidget(radius_label, 0, 1)
        options.addWidget(intersections_label, 0, 2)
        options.addWidget(self.mode_combo, 1, 0)
        options.addWidget(self.radius_spin, 1, 1)
        options.addWidget(self.intersections_checkbox, 1, 2)
        options.setColumnStretch(0, 2)
        options.setColumnStretch(1, 1)
        options.setColumnStretch(2, 2)
        setup_layout.addLayout(options)

        self.input_stack = QStackedWidget()
        self.input_stack.addWidget(self._build_generate_inputs())
        self.input_stack.addWidget(self._build_update_inputs())
        setup_layout.addWidget(self.input_stack)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.run_button = QPushButton("GENERATE LINKS")
        self.run_button.setProperty("primary", True)
        self.clear_paths_button = QPushButton("CLEAR PATHS")
        self.clear_output_button = QPushButton("CLEAR OUTPUT")
        self.request_summary = QLabel()
        self.request_summary.setObjectName("MutedText")
        self.request_summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        action_row.addWidget(self.run_button)
        action_row.addWidget(self.clear_paths_button)
        action_row.addWidget(self.clear_output_button)
        action_row.addStretch(1)
        action_row.addWidget(self.request_summary)
        setup_layout.addLayout(action_row)
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
        self.objectives_metric = MetricPanel("Objectives", "0")
        self.targets_metric = MetricPanel("Targets", "0")
        self.links_metric = MetricPanel("Links", "0")
        self.lut_metric = MetricPanel("LUT bins", "0")
        self.result_label = QLabel("No operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)

        metric_grid = QGridLayout()
        metric_grid.setSpacing(7)
        metric_grid.addWidget(self.objectives_metric, 0, 0)
        metric_grid.addWidget(self.targets_metric, 0, 1)
        metric_grid.addWidget(self.links_metric, 1, 0)
        metric_grid.addWidget(self.lut_metric, 1, 1)

        metrics_layout.addWidget(metrics_title)
        metrics_layout.addLayout(metric_grid)
        metrics_layout.addWidget(self.result_label)
        metrics_layout.addStretch(1)

        output.addWidget(log_panel, 1)
        output.addWidget(metrics_panel)
        layout.addLayout(output, 1)

    def _build_generate_inputs(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.generate_csv_picker = PathPicker(
            "Current objective dataset CSV",
            "Select objective dataset CSV",
            PathSelectionMode.CSV_FILE,
            placeholder_text=(
                "Select CSV with Name, Type, Subtype, ID, X, Y, LCount, Links"
            ),
            help_text=(
                "The complete current objective dataset is read and every "
                "objective's links are rebuilt."
            ),
        )
        self.generate_lut_picker = PathPicker(
            "Distance-to-cost LUT JSON (optional)",
            "Select optional LUT JSON",
            PathSelectionMode.JSON_FILE,
            placeholder_text=(
                "Optional: select JSON LUT; otherwise derive it from the CSV"
            ),
            help_text=(
                "When omitted, distance/cost bands are derived from valid "
                "existing links in the current dataset."
            ),
        )
        self.generate_output_picker = PathPicker(
            "New output CSV to create",
            "Save generated links CSV",
            PathSelectionMode.SAVE_CSV_FILE,
            placeholder_text="Choose where to save the rebuilt dataset CSV",
            help_text=(
                "The input CSV is not overwritten unless you explicitly choose "
                "the same path in the save dialog."
            ),
        )
        layout.addWidget(self.generate_csv_picker)
        layout.addWidget(self.generate_lut_picker)
        layout.addWidget(self.generate_output_picker)
        return widget

    def _build_update_inputs(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.old_csv_picker = PathPicker(
            "Previous objective dataset CSV",
            "Select previous objective dataset CSV",
            PathSelectionMode.CSV_FILE,
            placeholder_text="Select the older dataset used for comparison",
            help_text=(
                "IDs and coordinates are compared with the new dataset to "
                "detect added and moved objectives."
            ),
        )
        self.new_csv_picker = PathPicker(
            "Current objective dataset CSV",
            "Select new objective dataset CSV",
            PathSelectionMode.CSV_FILE,
            placeholder_text=(
                "Select current CSV with Name, Type, Subtype, ID, X, Y, "
                "LCount, Links"
            ),
            help_text=(
                "Only new, moved, and affected neighboring objectives have "
                "their links recalculated."
            ),
        )
        self.update_lut_picker = PathPicker(
            "Distance-to-cost LUT JSON (optional)",
            "Select optional LUT JSON",
            PathSelectionMode.JSON_FILE,
            placeholder_text=(
                "Optional: select JSON LUT; otherwise derive it from current CSV"
            ),
            help_text=(
                "When omitted, distance/cost bands are derived from the current "
                "dataset's valid existing links."
            ),
        )
        self.update_output_picker = PathPicker(
            "New output CSV to create",
            "Save updated links CSV",
            PathSelectionMode.SAVE_CSV_FILE,
            placeholder_text="Choose where to save the selectively updated CSV",
            help_text=(
                "The previous and current input files remain unchanged unless "
                "you explicitly select an input path as the output."
            ),
        )
        layout.addWidget(self.old_csv_picker)
        layout.addWidget(self.new_csv_picker)
        layout.addWidget(self.update_lut_picker)
        layout.addWidget(self.update_output_picker)
        return widget

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.radius_spin.valueChanged.connect(self._update_summary)
        self.intersections_checkbox.toggled.connect(self._update_summary)
        self.run_button.clicked.connect(self._start)
        self.clear_paths_button.clicked.connect(self._clear_paths)
        self.clear_output_button.clicked.connect(self._clear_output)

        self.task_controller.started.connect(self._on_started)
        self.task_controller.diagnostic.connect(
            self.diagnostic_log.append_event
        )
        self.task_controller.completed.connect(self._on_completed)
        self.task_controller.cancelled.connect(self._on_cancelled)
        self.task_controller.failed.connect(self._on_failed)
        self.task_controller.finished.connect(self._on_finished)

    def _on_mode_changed(self) -> None:
        self.input_stack.setCurrentIndex(self.mode_combo.currentIndex())
        self.run_button.setText(
            "UPDATE LINKS"
            if self._is_update_mode()
            else "GENERATE LINKS"
        )
        self._update_summary()

    def _is_update_mode(self) -> bool:
        return self.mode_combo.currentIndex() == self.UPDATE_INDEX

    def _update_summary(self) -> None:
        mode = "UPDATE" if self._is_update_mode() else "REBUILD ALL"
        geometry = (
            "ALLOW CROSSINGS"
            if self.intersections_checkbox.isChecked()
            else "AVOID CROSSINGS"
        )
        self.request_summary.setText(
            f"{mode} / {self.radius_spin.value():g} KM / {geometry}"
        )

    def _start(self) -> None:
        operation = self._build_operation()
        if operation is None:
            return
        output_path, task_label, task_operation = operation
        if output_path.exists():
            response = QMessageBox.question(
                self,
                "Confirm output replacement",
                f"The output file already exists:\n{output_path}\n\n"
                "Replace it atomically?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return

        self._clear_output()
        if not self.task_controller.start(task_label, task_operation):
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _build_operation(
        self,
    ) -> tuple[Path, str, TaskOperation] | None:
        if self._is_update_mode():
            required = (
                self.old_csv_picker.path,
                self.new_csv_picker.path,
                self.update_output_picker.path,
            )
            if any(path is None for path in required):
                self._target_warning(
                    "Select the previous CSV, new CSV, and output CSV."
                )
                return None
            old_csv, new_csv, output_csv = required
            assert old_csv is not None
            assert new_csv is not None
            assert output_csv is not None
            request = LinkUpdateRequest(
                old_csv=old_csv,
                new_csv=new_csv,
                output_csv=output_csv,
                lut_json=self.update_lut_picker.path,
                radius_km=self.radius_spin.value(),
                allow_intersections=self.intersections_checkbox.isChecked(),
            )
            return (
                output_csv,
                "Updating objective links",
                lambda context: update_changed_links(request, context),
            )

        source_csv = self.generate_csv_picker.path
        output_csv = self.generate_output_picker.path
        if source_csv is None or output_csv is None:
            self._target_warning("Select the dataset CSV and output CSV.")
            return None
        request = LinkGenerationRequest(
            source_csv=source_csv,
            output_csv=output_csv,
            lut_json=self.generate_lut_picker.path,
            radius_km=self.radius_spin.value(),
            allow_intersections=self.intersections_checkbox.isChecked(),
        )
        return (
            output_csv,
            "Generating objective links",
            lambda context: generate_all_links(request, context),
        )

    def _target_warning(self, message: str) -> None:
        QMessageBox.warning(self, "Paths required", message)

    def _clear_paths(self) -> None:
        for picker in (
            self.generate_csv_picker,
            self.generate_lut_picker,
            self.generate_output_picker,
            self.old_csv_picker,
            self.new_csv_picker,
            self.update_lut_picker,
            self.update_output_picker,
        ):
            picker.clear()

    def _clear_output(self) -> None:
        self.diagnostic_log.clear()
        self.objectives_metric.set_value(0)
        self.targets_metric.set_value(0)
        self.links_metric.set_value(0)
        self.lut_metric.set_value(0)
        self.result_label.setText("No operation has run.")

    def _on_started(self, _label: str) -> None:
        self._set_actions_enabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        self.objectives_metric.set_value(
            result.metrics.get("objectives", 0)
        )
        self.targets_metric.set_value(result.metrics.get("targets", 0))
        self.links_metric.set_value(result.metrics.get("links", 0))
        self.lut_metric.set_value(result.metrics.get("lut_bins", 0))
        self.result_label.setText(result.summary)
        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText(f"CANCELLED: {result.summary}")

    def _on_cancelled(self) -> None:
        self.result_label.setText("CANCELLED: output was not replaced")

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Links Generator",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self._set_actions_enabled(True)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.run_button.setEnabled(enabled)
        self.clear_paths_button.setEnabled(enabled)
        self.clear_output_button.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)

    def cancel_task(self) -> None:
        self.task_controller.cancel()

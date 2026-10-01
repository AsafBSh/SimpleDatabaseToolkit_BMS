"""PySide6 Runway Dimension Fixer page."""

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
    QSizePolicy,
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
    CHECK_LABELS,
    HeadingChoice,
    RunwayCheck,
    RunwayMapComparison,
    RunwayMode,
    RunwayRequest,
    check_runways,
    fix_runways,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.ui.runway_map_dialog import RunwayMapDialog
from simple_database_toolkit.workers import TaskController


class RunwayPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.task_controller = TaskController(self)
        self._map_data: RunwayMapComparison | None = None
        self._map_dialog: RunwayMapDialog | None = None

        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()
        self._on_checks_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "AIRBASE / RUNWAY",
                "Runway Dimension Fixer",
                "Validate headings, RunwayDim assignments, path trees, "
                "and runway-crossing markers with safe PHD/PDX repairs.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(10)
        setup_title = QLabel("TARGET AND VALIDATION RULES")
        setup_title.setObjectName("PanelTitle")
        setup_layout.addWidget(setup_title)

        parameters = QGridLayout()
        parameters.setHorizontalSpacing(12)
        parameters.setVerticalSpacing(5)
        mode_label = QLabel("Target mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        self.mode_combo.addItem(
            "Single airbase — select OCD folder",
            RunwayMode.SINGLE,
        )
        self.mode_combo.addItem(
            "Entire theater — select Class Table XML",
            RunwayMode.BATCH,
        )
        choice_label = QLabel("Fallback / forced heading")
        choice_label.setObjectName("MutedText")
        self.heading_choice_combo = QComboBox()
        self.heading_choice_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        self.heading_choice_combo.addItem(
            "First available heading",
            HeadingChoice.FIRST,
        )
        self.heading_choice_combo.addItem(
            "Second available heading",
            HeadingChoice.SECOND,
        )
        parameters.addWidget(mode_label, 0, 0)
        parameters.addWidget(choice_label, 0, 1)
        parameters.addWidget(self.mode_combo, 1, 0)
        parameters.addWidget(self.heading_choice_combo, 1, 1)
        parameters.setColumnStretch(0, 1)
        parameters.setColumnStretch(1, 1)
        setup_layout.addLayout(parameters)

        heading_options = QHBoxLayout()
        self.heading_cone_spin = QSpinBox()
        self.heading_cone_spin.setRange(4, 6)
        self.heading_cone_spin.setValue(5)
        self.heading_cone_spin.setSuffix("°")
        self.force_heading_checkbox = QCheckBox(
            "Force selected first/second heading"
        )
        heading_options.addWidget(QLabel("Near-match cone (±°)"))
        heading_options.addWidget(self.heading_cone_spin)
        heading_options.addWidget(self.force_heading_checkbox)
        heading_options.addStretch(1)
        setup_layout.addLayout(heading_options)
        self.heading_policy_label = QLabel()
        self.heading_policy_label.setObjectName("MutedText")
        self.heading_policy_label.setWordWrap(True)
        setup_layout.addWidget(self.heading_policy_label)

        self.target_picker = PathPicker()
        setup_layout.addWidget(self.target_picker)

        checks_label = QLabel("Checks to run")
        checks_label.setObjectName("MutedText")
        setup_layout.addWidget(checks_label)
        checks_layout = QGridLayout()
        checks_layout.setHorizontalSpacing(16)
        checks_layout.setVerticalSpacing(6)
        self.check_boxes: dict[RunwayCheck, QCheckBox] = {}
        checks = (
            RunwayCheck.LIST_HEADING,
            RunwayCheck.DIM_ASSIGNMENT,
            RunwayCheck.DIM_HEADING,
            RunwayCheck.CROSSING,
            RunwayCheck.PATHS,
        )
        for index, check in enumerate(checks):
            checkbox = QCheckBox(CHECK_LABELS[check])
            checkbox.setChecked(check is not RunwayCheck.PATHS)
            if check is RunwayCheck.PATHS:
                checkbox.setToolTip(
                    "Checks path structure and distances; does not modify XML."
                )
            self.check_boxes[check] = checkbox
            checks_layout.addWidget(checkbox, index // 2, index % 2)
        setup_layout.addLayout(checks_layout)

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(8)
        action_grid.setVerticalSpacing(6)
        self.check_button = QPushButton("CHECK RUNWAYS")
        self.check_button.setProperty("primary", True)
        self.fix_button = QPushButton("FIX RUNWAYS")
        self.map_button = QPushButton("SHOW MAP")
        self.clear_button = QPushButton("CLEAR OUTPUT")
        self.errors_only_checkbox = QCheckBox("Errors and warnings only")
        action_grid.addWidget(self.check_button, 0, 0)
        action_grid.addWidget(self.fix_button, 0, 1)
        action_grid.addWidget(self.map_button, 1, 0)
        action_grid.addWidget(self.clear_button, 1, 1)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)
        setup_layout.addLayout(action_grid)

        output_options_row = QHBoxLayout()
        output_options_row.setSpacing(8)
        output_options_row.addWidget(self.errors_only_checkbox)
        output_options_row.addStretch(1)
        setup_layout.addLayout(output_options_row)
        layout.addWidget(setup_panel)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.airbases_metric = MetricPanel("Airbases", "0")
        self.issues_metric = MetricPanel("Issues", "0")
        self.fixes_metric = MetricPanel("Fixes", "0")
        self.files_metric = MetricPanel("Files changed", "0")
        metrics.addWidget(self.airbases_metric, 0, 0)
        metrics.addWidget(self.issues_metric, 0, 1)
        metrics.addWidget(self.fixes_metric, 0, 2)
        metrics.addWidget(self.files_metric, 0, 3)
        layout.addLayout(metrics)

        output_panel = QFrame()
        output_panel.setObjectName("Panel")
        output_layout = QVBoxLayout(output_panel)
        output_layout.setContentsMargins(10, 9, 10, 10)
        output_layout.setSpacing(7)
        output_header = QHBoxLayout()
        output_title = QLabel("DIAGNOSTIC OUTPUT")
        output_title.setObjectName("PanelTitle")
        self.result_label = QLabel("No runway operation has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.result_label.setWordWrap(True)
        output_header.addWidget(output_title)
        output_header.addStretch(1)
        output_header.addWidget(self.result_label)
        self.diagnostic_log = DiagnosticLog()
        self.diagnostic_log.setMinimumHeight(220)
        output_layout.addLayout(output_header)
        output_layout.addWidget(self.diagnostic_log, 1)
        layout.addWidget(output_panel, 1)

        note = QLabel(
            "Paths Checker is read-only and disables Fix. The map is "
            "available after a single-objective crossing check or fix."
        )
        note.setObjectName("MutedText")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        for checkbox in self.check_boxes.values():
            checkbox.toggled.connect(self._on_checks_changed)
        self.heading_cone_spin.valueChanged.connect(self._update_heading_policy)
        self.force_heading_checkbox.toggled.connect(self._update_heading_policy)
        self.check_button.clicked.connect(self._start_check)
        self.fix_button.clicked.connect(self._start_fix)
        self.map_button.clicked.connect(self._show_map)
        self.clear_button.clicked.connect(self._clear_output)
        self.errors_only_checkbox.toggled.connect(
            self.diagnostic_log.set_errors_only
        )

        self.task_controller.started.connect(self._on_started)
        self.task_controller.diagnostic.connect(
            self.diagnostic_log.append_event
        )
        self.task_controller.completed.connect(self._on_completed)
        self.task_controller.cancelled.connect(self._on_cancelled)
        self.task_controller.failed.connect(self._on_failed)
        self.task_controller.finished.connect(self._on_finished)

    def _selected_mode(self) -> RunwayMode:
        value = self.mode_combo.currentData()
        try:
            return RunwayMode(value)
        except (TypeError, ValueError):
            return RunwayMode.SINGLE

    def _selected_choice(self) -> HeadingChoice:
        value = self.heading_choice_combo.currentData()
        try:
            return HeadingChoice(value)
        except (TypeError, ValueError):
            return HeadingChoice.FIRST

    def _selected_checks(self) -> frozenset[RunwayCheck]:
        return frozenset(
            check
            for check, checkbox in self.check_boxes.items()
            if checkbox.isChecked()
        )

    def _on_mode_changed(self) -> None:
        if self._selected_mode() is RunwayMode.BATCH:
            self.target_picker.set_mode(
                PathSelectionMode.XML_FILE,
                label="Theater Class Table XML",
                dialog_title="Select theater Class Table XML",
                placeholder_text=(
                    "Select Falcon4_CT.xml beside ObjectiveRelatedData"
                ),
                help_text=(
                    "The tool scans immediate OCD_* folders in the "
                    "ObjectiveRelatedData folder beside this XML file."
                ),
            )
        else:
            self.target_picker.set_mode(
                PathSelectionMode.DIRECTORY,
                label="Single airbase OCD objective folder",
                dialog_title="Select one airbase OCD_XXXXX folder",
                placeholder_text=(
                    "Select OCD_XXXXX containing PHD_XXXXX.xml"
                ),
                help_text=(
                    "Only this objective is checked. PDX_XXXXX.xml is also "
                    "required for every check except RunwayDim heading."
                ),
            )
        self._discard_map()

    def _on_checks_changed(self) -> None:
        selected = self._selected_checks()
        paths_enabled = RunwayCheck.PATHS in selected
        self.fix_button.setEnabled(
            not paths_enabled and not self.task_controller.is_running
        )
        self.heading_choice_combo.setEnabled(
            RunwayCheck.DIM_HEADING in selected
            and not self.task_controller.is_running
        )
        self.heading_cone_spin.setEnabled(
            RunwayCheck.DIM_HEADING in selected
            and not self.task_controller.is_running
        )
        self.force_heading_checkbox.setEnabled(
            RunwayCheck.DIM_HEADING in selected
            and not self.task_controller.is_running
        )
        self._update_heading_policy()
        self._discard_map()

    def _update_heading_policy(self) -> None:
        if self.force_heading_checkbox.isChecked():
            policy = "Override even a valid opposite heading."
        else:
            policy = (
                f"Closest heading within ±{self.heading_cone_spin.value()}°; "
                "otherwise use the selected fallback."
            )
        self.heading_policy_label.setText(policy)

    def _request(self) -> RunwayRequest | None:
        target = self.target_picker.path
        if target is None:
            QMessageBox.warning(
                self,
                "Target required",
                "Select an objective folder or Class Table XML.",
            )
            return None
        checks = self._selected_checks()
        if not checks:
            QMessageBox.warning(
                self,
                "Checks required",
                "Select at least one runway check.",
            )
            return None
        return RunwayRequest(
            target=Path(target),
            mode=self._selected_mode(),
            checks=checks,
            heading_choice=self._selected_choice(),
            heading_cone_degrees=self.heading_cone_spin.value(),
            force_heading_choice=self.force_heading_checkbox.isChecked(),
        )

    def _start_check(self) -> None:
        request = self._request()
        if request is None:
            return
        self._clear_output()
        if not self.task_controller.start(
            "Checking runway data",
            lambda context: check_runways(request, context),
        ):
            self._already_running()

    def _start_fix(self) -> None:
        request = self._request()
        if request is None:
            return
        if RunwayCheck.PATHS in request.checks:
            QMessageBox.warning(
                self,
                "Check-only rule selected",
                "Paths Checker cannot be used during Fix.",
            )
            return
        labels = ", ".join(CHECK_LABELS[check] for check in request.checks)
        response = QMessageBox.question(
            self,
            "Confirm runway repair",
            f"Apply these runway repairs?\n\n{labels}\n\n"
            f"Heading cone: ±{request.heading_cone_degrees}°; "
            f"fallback: {request.heading_choice.value}; "
            f"Force: {'ON' if request.force_heading_choice else 'OFF'}.\n\n"
            "Affected PHD/PDX files are committed atomically per airbase.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self._clear_output()
        if not self.task_controller.start(
            "Fixing runway data",
            lambda context: fix_runways(request, context),
        ):
            self._already_running()

    def _already_running(self) -> None:
        QMessageBox.information(
            self,
            "Task already running",
            "Wait for the active task to finish or cancel it.",
        )

    def _show_map(self) -> None:
        if self._map_data is None:
            return
        self._map_dialog = RunwayMapDialog(self._map_data, self)
        self._map_dialog.show()
        self._map_dialog.raise_()
        self._map_dialog.activateWindow()

    def _discard_map(self) -> None:
        self._map_data = None
        if hasattr(self, "map_button"):
            self.map_button.setEnabled(False)

    def _clear_output(self) -> None:
        self._discard_map()
        self.diagnostic_log.clear()
        self.airbases_metric.set_value(0)
        self.issues_metric.set_value(0)
        self.fixes_metric.set_value(0)
        self.files_metric.set_value(0)
        self.result_label.setText("No runway operation has run.")

    def _on_started(self, _label: str) -> None:
        self._set_actions_enabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        self.airbases_metric.set_value(result.metrics.get("airbases", 0))
        errors = int(result.metrics.get("errors", 0))
        warnings = int(result.metrics.get("warnings", 0))
        self.issues_metric.set_value(errors + warnings)
        self.fixes_metric.set_value(result.metrics.get("fixed", 0))
        self.files_metric.set_value(result.metrics.get("files", 0))
        self.result_label.setText(result.summary)
        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText(f"CANCELLED: {result.summary}")
        map_data = result.metrics.get("map")
        if isinstance(map_data, RunwayMapComparison):
            self._map_data = map_data

    def _on_cancelled(self) -> None:
        self._discard_map()
        self.result_label.setText(
            "CANCELLED: completed airbase transactions remain valid"
        )

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self._discard_map()
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Runway Dimension Fixer",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self._set_actions_enabled(True)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.check_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.target_picker.setEnabled(enabled)
        for checkbox in self.check_boxes.values():
            checkbox.setEnabled(enabled)
        paths_enabled = self.check_boxes[RunwayCheck.PATHS].isChecked()
        self.fix_button.setEnabled(enabled and not paths_enabled)
        self.heading_choice_combo.setEnabled(
            enabled
            and self.check_boxes[RunwayCheck.DIM_HEADING].isChecked()
        )
        self.heading_cone_spin.setEnabled(
            enabled and self.check_boxes[RunwayCheck.DIM_HEADING].isChecked()
        )
        self.force_heading_checkbox.setEnabled(
            enabled and self.check_boxes[RunwayCheck.DIM_HEADING].isChecked()
        )
        self.map_button.setEnabled(enabled and self._map_data is not None)

    def cancel_task(self) -> None:
        self.task_controller.cancel()

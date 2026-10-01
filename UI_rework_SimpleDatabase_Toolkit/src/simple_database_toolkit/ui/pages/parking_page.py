"""PySide6 Parking Fixer with mandatory relocation preview."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
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
    ParkingMode,
    ParkingPreview,
    ParkingRequest,
    apply_parking,
    preview_parking,
)
from simple_database_toolkit.ui.components import (
    DiagnosticLog,
    MetricPanel,
    PageHeader,
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.workers import TaskController


class ParkingPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.task_controller = TaskController(self)
        self._current_action = ""
        self._preview: ParkingPreview | None = None

        self._build_ui()
        self._connect_signals()
        self._on_mode_changed()
        self._set_actions_enabled(True)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(
            PageHeader(
                "AIRBASE / PARKING",
                "Parking Fixer",
                "Preview and relocate parking points to nearby hangar "
                "feature centers without rewriting unrelated PDX data.",
            )
        )

        setup_panel = QFrame()
        setup_panel.setObjectName("Panel")
        setup_layout = QVBoxLayout(setup_panel)
        setup_layout.setContentsMargins(15, 13, 15, 15)
        setup_layout.setSpacing(10)

        setup_title = QLabel("TARGET AND RELOCATION PARAMETERS")
        setup_title.setObjectName("PanelTitle")
        setup_layout.addWidget(setup_title)

        parameters = QGridLayout()
        parameters.setHorizontalSpacing(12)
        parameters.setVerticalSpacing(5)

        mode_label = QLabel("Target mode")
        mode_label.setObjectName("MutedText")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(
            "Single objective — select OCD folder",
            ParkingMode.SINGLE,
        )
        self.mode_combo.addItem(
            "All objectives — select ObjectiveRelatedData",
            ParkingMode.BATCH,
        )

        radius_label = QLabel("Search radius")
        radius_label.setObjectName("MutedText")
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0, 100_000)
        self.radius_spin.setDecimals(3)
        self.radius_spin.setValue(10)
        self.radius_spin.setSuffix(" ft")

        hangar_label = QLabel("Hangar CT numbers")
        hangar_label.setObjectName("MutedText")
        self.hangar_edit = QLineEdit("0")
        self.hangar_edit.setPlaceholderText(
            "0 for all, or values separated by commas"
        )

        parameters.addWidget(mode_label, 0, 0)
        parameters.addWidget(radius_label, 0, 1)
        parameters.addWidget(hangar_label, 0, 2)
        parameters.addWidget(self.mode_combo, 1, 0)
        parameters.addWidget(self.radius_spin, 1, 1)
        parameters.addWidget(self.hangar_edit, 1, 2)
        parameters.setColumnStretch(0, 2)
        parameters.setColumnStretch(1, 1)
        parameters.setColumnStretch(2, 2)
        setup_layout.addLayout(parameters)

        self.target_picker = PathPicker()
        self.class_table_picker = PathPicker(
            "Class Table XML used for hangar types",
            "Select Class Table XML used for hangar types",
            PathSelectionMode.XML_FILE,
            placeholder_text=(
                "Select Falcon4_CT.xml containing Type 45 hangar records"
            ),
            help_text=(
                "This file supplies the valid hangar CT numbers. It is not "
                "used as the folder-tree target."
            ),
        )
        setup_layout.addWidget(self.target_picker)
        setup_layout.addWidget(self.class_table_picker)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.preview_button = QPushButton("PREVIEW MOVES")
        self.preview_button.setProperty("primary", True)
        self.apply_button = QPushButton("APPLY PREVIEWED MOVES")
        self.clear_button = QPushButton("CLEAR OUTPUT")
        self.request_summary = QLabel()
        self.request_summary.setObjectName("MutedText")
        self.request_summary.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.request_summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.apply_button)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        action_row.addWidget(self.request_summary)
        setup_layout.addLayout(action_row)
        layout.addWidget(setup_panel)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        self.objectives_metric = MetricPanel("Objectives", "0")
        self.parking_metric = MetricPanel("Parking points", "0")
        self.moves_metric = MetricPanel("Proposed moves", "0")
        self.errors_metric = MetricPanel("Errors", "0")
        metrics.addWidget(self.objectives_metric, 0, 0)
        metrics.addWidget(self.parking_metric, 0, 1)
        metrics.addWidget(self.moves_metric, 1, 0)
        metrics.addWidget(self.errors_metric, 1, 1)
        layout.addLayout(metrics)

        preview_panel = QFrame()
        preview_panel.setObjectName("Panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(10, 9, 10, 10)
        preview_layout.setSpacing(7)
        preview_title = QLabel("RELOCATION PREVIEW")
        preview_title.setObjectName("PanelTitle")
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setHorizontalHeaderLabels(
            [
                "OBJECTIVE",
                "PD",
                "CURRENT X / Y",
                "NEW X / Y",
                "DISTANCE",
                "HANGAR CT",
            ]
        )
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.verticalHeader().setVisible(False)
        table_header = self.preview_table.horizontalHeader()
        table_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        for column in range(1, 6):
            table_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        self.preview_note = QLabel(
            "Run Preview before Apply. Parameters are revalidated from disk "
            "when changes are committed."
        )
        self.preview_note.setObjectName("MutedText")
        self.preview_note.setWordWrap(True)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview_table, 1)
        preview_layout.addWidget(self.preview_note)
        layout.addWidget(preview_panel, 1)

        log_panel = QFrame()
        log_panel.setObjectName("Panel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(10, 9, 10, 10)
        log_layout.setSpacing(7)
        log_title = QLabel("DIAGNOSTIC OUTPUT")
        log_title.setObjectName("PanelTitle")
        self.diagnostic_log = DiagnosticLog()
        self.result_label = QLabel("No preview has run.")
        self.result_label.setObjectName("MutedText")
        self.result_label.setWordWrap(True)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.diagnostic_log, 1)
        log_layout.addWidget(self.result_label)
        layout.addWidget(log_panel, 1)

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.radius_spin.valueChanged.connect(self._invalidate_preview)
        self.hangar_edit.textChanged.connect(self._invalidate_preview)
        self.target_picker.path_changed.connect(self._invalidate_preview)
        self.class_table_picker.path_changed.connect(
            self._invalidate_preview
        )
        self.preview_button.clicked.connect(self._start_preview)
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

    def _selected_mode(self) -> ParkingMode:
        mode = self.mode_combo.currentData()
        try:
            return ParkingMode(mode)
        except (TypeError, ValueError):
            return ParkingMode.SINGLE

    def _on_mode_changed(self) -> None:
        if self._selected_mode() is ParkingMode.BATCH:
            self.target_picker.set_mode(
                PathSelectionMode.DIRECTORY,
                label="ObjectiveRelatedData folder",
                dialog_title="Select ObjectiveRelatedData folder",
                placeholder_text=(
                    "Select ObjectiveRelatedData containing OCD_* folders"
                ),
                help_text=(
                    "Each immediate OCD_* child folder with matching FED and "
                    "PDX XML files is previewed. Subfolders are not recursive."
                ),
            )
        else:
            self.target_picker.set_mode(
                PathSelectionMode.DIRECTORY,
                label="Single OCD objective folder",
                dialog_title="Select one OCD_XXXXX objective folder",
                placeholder_text=(
                    "Select OCD_XXXXX containing FED_XXXXX.xml and PDX_XXXXX.xml"
                ),
                help_text=(
                    "Only this objective is previewed. The separate Class "
                    "Table XML identifies which feature CT numbers are hangars."
                ),
            )
        self._invalidate_preview()

    def _parse_hangar_numbers(self) -> tuple[int, ...] | None:
        text = self.hangar_edit.text().strip()
        if not text:
            return ()
        tokens = [
            token
            for token in re.split(r"[\s,;]+", text)
            if token
        ]
        try:
            values = tuple(int(token) for token in tokens)
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid hangar CT numbers",
                "Use non-negative whole CT numbers separated by spaces, "
                "commas, or semicolons.",
            )
            return None
        if any(value < 0 for value in values):
            QMessageBox.warning(
                self,
                "Invalid hangar CT numbers",
                "Hangar CT numbers cannot be negative.",
            )
            return None
        return values

    def _request(self) -> ParkingRequest | None:
        target = self.target_picker.path
        class_table = self.class_table_picker.path
        if target is None or class_table is None:
            QMessageBox.warning(
                self,
                "Paths required",
                "Select the objective target and Class Table XML.",
            )
            return None
        hangar_numbers = self._parse_hangar_numbers()
        if hangar_numbers is None:
            return None
        return ParkingRequest(
            target=Path(target),
            class_table=Path(class_table),
            mode=self._selected_mode(),
            radius_feet=self.radius_spin.value(),
            hangar_ct_numbers=hangar_numbers,
        )

    def _start_preview(self) -> None:
        request = self._request()
        if request is None:
            return
        self._clear_output()
        self._current_action = "preview"
        if not self.task_controller.start(
            "Previewing parking relocations",
            lambda context: preview_parking(request, context),
        ):
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _start_apply(self) -> None:
        current_request = self._request()
        if current_request is None:
            return
        if self._preview is None or current_request != self._preview.request:
            QMessageBox.warning(
                self,
                "Preview required",
                "The parameters changed. Run Preview again before applying.",
            )
            return
        move_count = len(self._preview.moves)
        if move_count == 0:
            return
        response = QMessageBox.question(
            self,
            "Confirm parking relocation",
            f"Relocate {move_count} parking point(s) across "
            f"{len(self._preview.objectives)} objective(s)?\n\n"
            "Only affected PDX OffsetX/OffsetY values will be atomically "
            "replaced.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        confirmed_preview = self._preview
        self.diagnostic_log.clear()
        self._current_action = "apply"
        if not self.task_controller.start(
            "Applying parking relocations",
            lambda context: apply_parking(
                current_request,
                context,
                expected_preview=confirmed_preview,
            ),
        ):
            QMessageBox.information(
                self,
                "Task already running",
                "Wait for the active task to finish or cancel it.",
            )

    def _invalidate_preview(self, *_args) -> None:
        self._preview = None
        if hasattr(self, "apply_button"):
            self.apply_button.setEnabled(False)
        if hasattr(self, "request_summary"):
            mode = (
                "ALL OBJECTIVES"
                if self._selected_mode() is ParkingMode.BATCH
                else "SINGLE OBJECTIVE"
            )
            hangars = self.hangar_edit.text().strip() or "ALL"
            self.request_summary.setText(
                f"{mode} / {self.radius_spin.value():g} FT / CT {hangars}"
            )

    def _populate_preview(self, preview: ParkingPreview) -> None:
        self.preview_table.setRowCount(0)
        for row, move in enumerate(preview.moves):
            self.preview_table.insertRow(row)
            values = [
                move.objective_name,
                move.point_number,
                f"{move.old_x:g} / {move.old_y:g}",
                f"{move.new_x:g} / {move.new_y:g}",
                f"{move.distance_feet:.2f} ft",
                str(move.hangar_ct_number),
            ]
            for column, value in enumerate(values):
                self.preview_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

    def _clear_output(self) -> None:
        self._preview = None
        self.preview_table.setRowCount(0)
        self.diagnostic_log.clear()
        self.objectives_metric.set_value(0)
        self.parking_metric.set_value(0)
        self.moves_metric.set_value(0)
        self.errors_metric.set_value(0)
        self.result_label.setText("No preview has run.")
        self.apply_button.setEnabled(False)

    def _on_started(self, _label: str) -> None:
        self._set_actions_enabled(False)
        self.result_label.setText("Operation running...")

    def _on_completed(self, result: OperationResult) -> None:
        self.objectives_metric.set_value(
            result.metrics.get("objectives", 0)
        )
        self.parking_metric.set_value(
            result.metrics.get("parking_points", 0)
        )
        self.moves_metric.set_value(result.metrics.get("moves", 0))
        self.errors_metric.set_value(result.metrics.get("errors", 0))
        self.result_label.setText(result.summary)
        if result.status is OperationStatus.FAILED:
            self.result_label.setText(f"FAILED: {result.summary}")
        elif result.status is OperationStatus.CANCELLED:
            self.result_label.setText(f"CANCELLED: {result.summary}")

        if self._current_action == "preview":
            preview = result.metrics.get("preview")
            if isinstance(preview, ParkingPreview):
                self._preview = preview
                self._populate_preview(preview)
        else:
            self._preview = None

    def _on_cancelled(self) -> None:
        self._preview = None
        self.result_label.setText(
            "CANCELLED: completed PDX files remain valid"
        )

    def _on_failed(self, message: str, _traceback_text: str) -> None:
        self._preview = None
        self.diagnostic_log.append_event(
            DiagnosticEvent(
                severity=DiagnosticSeverity.ERROR,
                module="Parking Fixer",
                message=f"Unexpected worker failure: {message}",
            )
        )
        self.result_label.setText("FAILED: unexpected worker error")

    def _on_finished(self) -> None:
        self._current_action = ""
        self._set_actions_enabled(True)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.preview_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.radius_spin.setEnabled(enabled)
        self.hangar_edit.setEnabled(enabled)
        self.target_picker.setEnabled(enabled)
        self.class_table_picker.setEnabled(enabled)
        self.apply_button.setEnabled(
            enabled
            and self._preview is not None
            and bool(self._preview.moves)
        )

    def cancel_task(self) -> None:
        self.task_controller.cancel()

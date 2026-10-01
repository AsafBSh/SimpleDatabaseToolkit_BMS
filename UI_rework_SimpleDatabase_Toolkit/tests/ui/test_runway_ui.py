from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
)
from simple_database_toolkit.services import (
    RunwayCheck,
    RunwayMapComparison,
    RunwayMapSnapshot,
    RunwayPolygon,
)
from simple_database_toolkit.ui.components import DiagnosticLog
from simple_database_toolkit.ui.pages import RunwayPage
from simple_database_toolkit.ui.runway_map_dialog import RunwayMapDialog


def _application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(["runway-ui-test"])


def test_runway_page_defaults_and_paths_check_only_state() -> None:
    _application()
    page = RunwayPage()

    assert len(page._selected_checks()) == 4
    assert RunwayCheck.PATHS not in page._selected_checks()
    assert page.fix_button.isEnabled()
    assert not page.map_button.isEnabled()

    page.check_boxes[RunwayCheck.PATHS].setChecked(True)
    assert not page.fix_button.isEnabled()

    page.check_boxes[RunwayCheck.PATHS].setChecked(False)
    assert page.fix_button.isEnabled()


def test_diagnostic_log_errors_only_filter_updates_existing_and_new_rows() -> None:
    _application()
    log = DiagnosticLog()
    log.append_event(
        DiagnosticEvent(
            DiagnosticSeverity.SUCCESS,
            "runway",
            "Heading is valid.",
        )
    )
    log.append_event(
        DiagnosticEvent(
            DiagnosticSeverity.ERROR,
            "runway",
            "Heading mismatch.",
        )
    )

    log.set_errors_only(True)

    assert log.tree.topLevelItem(0).isHidden()
    assert not log.tree.topLevelItem(1).isHidden()

    log.append_event(
        DiagnosticEvent(
            DiagnosticSeverity.INFO,
            "runway",
            "Scan detail.",
        )
    )
    assert log.tree.topLevelItem(2).isHidden()


def test_runway_map_dialog_builds_current_state_canvas() -> None:
    _application()
    snapshot = RunwayMapSnapshot(
        folder=Path("OCD_00001"),
        title="OCD_00001 — Test Airbase",
        polygons=(
            RunwayPolygon(
                "1",
                ((-10, -10), (10, -10), (10, 10), (-10, 10)),
            ),
        ),
        paths=(),
        runway_points=((0, 0, "1"),),
        takeoff_points=((0, -100, "1"),),
    )

    dialog = RunwayMapDialog(RunwayMapComparison(snapshot))

    assert dialog.windowTitle() == "Runway Map — OCD_00001 — Test Airbase"
    assert dialog.layout().count() == 1

"""Runway dimension validation, repair, path checks, and map snapshots."""

from __future__ import annotations

import copy
import math
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .xml_edit import patch_xml

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
    OperationCancelled,
    OperationContext,
    OperationResult,
    OperationStatus,
    ProgressUpdate,
)


class RunwayMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


class RunwayCheck(str, Enum):
    LIST_HEADING = "runway-list-heading"
    DIM_ASSIGNMENT = "runway-dim-assignment"
    DIM_HEADING = "runway-dim-heading"
    CROSSING = "crossing-functionality"
    PATHS = "paths-checker"


class HeadingChoice(str, Enum):
    FIRST = "first"
    SECOND = "second"


CHECK_LABELS = {
    RunwayCheck.LIST_HEADING: "RunwayList heading",
    RunwayCheck.DIM_ASSIGNMENT: "RunwayDim assignment",
    RunwayCheck.DIM_HEADING: "RunwayDim heading",
    RunwayCheck.CROSSING: "Crossing functionality",
    RunwayCheck.PATHS: "Paths checker",
}

PATH_TYPES = {"1", "2", "3", "11", "12", "15", "19", "21"}
PARK_TYPES = {"11", "12"}
TAXI_TYPES = {"3", "19"}
PATH_TYPE_NAMES = {
    "1": "Runway",
    "2": "Takeoff",
    "3": "Taxi",
    "11": "SmallPark",
    "12": "LargePark",
    "15": "TakeRunway",
    "19": "CritTaxi",
    "21": "VacateRunway",
}
PATH_ALLOWED = {
    "11": {"3", "19"},
    "12": {"3", "19"},
    "3": {"3", "19", "15"},
    "19": {"3", "19", "15"},
    "15": {"15", "2"},
    "21": {"3", "19"},
    "2": {"1"},
    "1": set(),
}
PATH_DISTANCE_LIMITS = {
    ("11", "3"): (None, 200.0),
    ("11", "19"): (None, 200.0),
    ("12", "3"): (None, 200.0),
    ("12", "19"): (None, 200.0),
    ("3", "3"): (None, 300.0),
    ("3", "19"): (None, 300.0),
    ("19", "3"): (None, 300.0),
    ("19", "19"): (None, 300.0),
    ("3", "15"): (None, 300.0),
    ("19", "15"): (None, 300.0),
    ("15", "15"): (None, 300.0),
    ("15", "2"): (180.0, None),
    ("2", "1"): (None, None),
}


@dataclass(frozen=True, slots=True)
class RunwayRequest:
    target: Path
    mode: RunwayMode = RunwayMode.SINGLE
    checks: frozenset[RunwayCheck] = frozenset(
        {
            RunwayCheck.LIST_HEADING,
            RunwayCheck.DIM_ASSIGNMENT,
            RunwayCheck.DIM_HEADING,
            RunwayCheck.CROSSING,
        }
    )
    heading_choice: HeadingChoice = HeadingChoice.FIRST
    heading_cone_degrees: int = 5
    force_heading_choice: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))
        object.__setattr__(self, "checks", frozenset(self.checks))
        if self.heading_cone_degrees not in (4, 5, 6):
            raise ValueError("Heading cone must be between 4 and 6 degrees.")


@dataclass(frozen=True, slots=True)
class RunwayMapPoint:
    x: float
    y: float
    relative_index: int
    point_type: str
    crossing_point: int | None
    runway_number: str | None


@dataclass(frozen=True, slots=True)
class RunwayMapPath:
    phd_number: str
    points: tuple[RunwayMapPoint, ...]


@dataclass(frozen=True, slots=True)
class RunwayPolygon:
    runway_number: str
    vertices: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class RunwayMapSnapshot:
    folder: Path
    title: str
    polygons: tuple[RunwayPolygon, ...]
    paths: tuple[RunwayMapPath, ...]
    runway_points: tuple[tuple[float, float, str], ...]
    takeoff_points: tuple[tuple[float, float, str], ...]


@dataclass(frozen=True, slots=True)
class RunwayMapComparison:
    before: RunwayMapSnapshot
    after: RunwayMapSnapshot | None = None


@dataclass(frozen=True, slots=True)
class _Target:
    folder: Path
    phd_path: Path
    pdx_path: Path | None
    objective_name: str


@dataclass(slots=True)
class _Stats:
    ok: int = 0
    fixed: int = 0
    errors: int = 0
    warnings: int = 0
    decisions: dict[str, int] | None = None


def check_runways(
    request: RunwayRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    return _run(request, context or OperationContext(), apply=False)


def fix_runways(
    request: RunwayRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    return _run(request, context or OperationContext(), apply=True)


def _run(
    request: RunwayRequest,
    context: OperationContext,
    *,
    apply: bool,
) -> OperationResult:
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    validation_error = _validate_request(request, apply)
    if validation_error:
        report(
            DiagnosticSeverity.ERROR,
            validation_error,
            request.target,
            "runway",
        )
        return _failed_result(validation_error, diagnostics)

    try:
        targets, discovery_errors = _discover_targets(request, report)
    except (OSError, ValueError) as exc:
        report(
            DiagnosticSeverity.ERROR,
            f"Could not discover runway data: {exc}",
            request.target,
            "runway",
        )
        return _failed_result("Runway discovery failed", diagnostics)

    effective_checks = set(request.checks)
    if apply:
        effective_checks.discard(RunwayCheck.PATHS)
    stats = {check: _Stats() for check in effective_checks}
    airbases = 0
    changed_files: list[Path] = []
    processing_errors = discovery_errors
    map_data: RunwayMapComparison | None = None

    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                phd_original = target.phd_path.read_bytes()
                phd_tree = ET.ElementTree(ET.fromstring(phd_original))
                phd_root = phd_tree.getroot()
                if not _is_airbase(phd_root):
                    report(
                        DiagnosticSeverity.INFO,
                        "Skipped non-airbase objective.",
                        target.folder,
                        "runway",
                    )
                    continue

                pdx_root: ET.Element | None = None
                pdx_original: bytes | None = None
                pdx_issue = "PDX XML was not found"
                needs_pdx = bool(
                    effective_checks - {RunwayCheck.DIM_HEADING}
                )
                if target.pdx_path is not None and needs_pdx:
                    try:
                        pdx_original = target.pdx_path.read_bytes()
                        pdx_root = ET.fromstring(pdx_original)
                    except (ET.ParseError, OSError) as exc:
                        pdx_issue = f"PDX XML could not be loaded: {exc}"

                airbases += 1
                before_map = (
                    _map_snapshot(target, phd_root, pdx_root)
                    if request.mode is RunwayMode.SINGLE
                    and RunwayCheck.CROSSING in effective_checks
                    and pdx_root is not None
                    else None
                )

                phd_changed = False
                pdx_changed = False
                for check in (
                    RunwayCheck.LIST_HEADING,
                    RunwayCheck.DIM_ASSIGNMENT,
                    RunwayCheck.DIM_HEADING,
                    RunwayCheck.CROSSING,
                    RunwayCheck.PATHS,
                ):
                    if check not in effective_checks:
                        continue
                    if check is RunwayCheck.DIM_HEADING:
                        heading_root = phd_root
                        if not apply and pdx_root is not None:
                            heading_root = copy.deepcopy(phd_root)
                            if RunwayCheck.LIST_HEADING in effective_checks:
                                _run_list_heading(
                                    target, heading_root, pdx_root,
                                    _Stats(), lambda *_: None, True,
                                )
                            if RunwayCheck.DIM_ASSIGNMENT in effective_checks:
                                _run_dim_assignment(
                                    target, heading_root, pdx_root,
                                    _Stats(), lambda *_: None, True,
                                )
                        changed = _run_dim_heading(
                            target,
                            heading_root,
                            stats[check],
                            report,
                            apply,
                            request.heading_choice,
                            request.heading_cone_degrees,
                            request.force_heading_choice,
                        )
                        phd_changed |= changed
                        continue
                    if pdx_root is None:
                        stats[check].errors += 1
                        report(
                            DiagnosticSeverity.ERROR,
                            f"{CHECK_LABELS[check]} skipped: {pdx_issue}.",
                            target.folder,
                            check.value,
                        )
                        continue
                    if check is RunwayCheck.LIST_HEADING:
                        phd_changed |= _run_list_heading(
                            target,
                            phd_root,
                            pdx_root,
                            stats[check],
                            report,
                            apply,
                        )
                    elif check is RunwayCheck.DIM_ASSIGNMENT:
                        phd_changed |= _run_dim_assignment(
                            target,
                            phd_root,
                            pdx_root,
                            stats[check],
                            report,
                            apply,
                        )
                    elif check is RunwayCheck.CROSSING:
                        pdx_changed |= _run_crossings(
                            target,
                            phd_root,
                            pdx_root,
                            stats[check],
                            report,
                            apply,
                        )
                    else:
                        _run_paths(
                            target,
                            phd_root,
                            pdx_root,
                            stats[check],
                            report,
                        )

                if apply and (phd_changed or pdx_changed):
                    replacements: dict[Path, bytes] = {}
                    expected: dict[Path, bytes] = {}
                    if phd_changed:
                        replacements[target.phd_path] = patch_xml(phd_original, phd_root)
                        expected[target.phd_path] = phd_original
                    if pdx_changed and target.pdx_path is not None:
                        assert pdx_original is not None and pdx_root is not None
                        replacements[target.pdx_path] = patch_xml(pdx_original, pdx_root)
                        expected[target.pdx_path] = pdx_original
                    context.backup_files(
                        list(replacements),
                        request.target if request.target.is_dir() else request.target.parent,
                    )
                    changed_files.extend(_commit_transaction(replacements, expected))

                if before_map is not None:
                    after_map = (
                        _map_snapshot(target, phd_root, pdx_root)
                        if apply
                        else None
                    )
                    map_data = RunwayMapComparison(before_map, after_map)
            except (
                ET.ParseError,
                OSError,
                TypeError,
                ValueError,
            ) as exc:
                processing_errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not process objective: {exc}",
                    target.folder,
                    "runway",
                )
            context.report_progress(
                ProgressUpdate(
                    current=index,
                    total=len(targets),
                    message=f"Processed {target.folder.name}",
                )
            )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Operation cancelled; completed objective transactions remain.",
            request.target,
            "runway",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Runway operation cancelled",
            diagnostics=diagnostics,
            changed_files=changed_files,
            metrics=_metrics(
                airbases,
                stats,
                changed_files,
                processing_errors,
                map_data,
            ),
        )

    metrics = _metrics(
        airbases,
        stats,
        changed_files,
        processing_errors,
        map_data,
    )
    errors = metrics["errors"]
    warnings = metrics["warnings"]
    fixes = metrics["fixed"]
    if airbases == 0 or (
        apply
        and processing_errors > 0
        and fixes > 0
        and not changed_files
    ):
        status = OperationStatus.FAILED
    elif errors or warnings:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS
    action = "Fixed" if apply else "Checked"
    heading_counts = stats.get(RunwayCheck.DIM_HEADING)
    decisions_text = ""
    if heading_counts is not None and heading_counts.decisions:
        decisions_text = "; headings: " + ", ".join(
            f"{name} {count}"
            for name, count in heading_counts.decisions.items()
        )
    return OperationResult(
        status=status,
        summary=(
            f"{action} {airbases} airbase(s); "
            f"{errors} error(s), {warnings} warning(s)"
            + (f", {fixes} fix(es)" if apply else "")
            + decisions_text
        ),
        diagnostics=diagnostics,
        changed_files=changed_files,
        metrics=metrics,
    )


def _validate_request(
    request: RunwayRequest,
    apply: bool,
) -> str | None:
    if not request.target.exists():
        return "The selected runway target does not exist."
    if not request.checks:
        return "Select at least one runway check."
    if any(not isinstance(check, RunwayCheck) for check in request.checks):
        return "The runway request contains an unknown check."
    if request.mode is RunwayMode.SINGLE and not request.target.is_dir():
        return "Single mode requires an OCD objective folder."
    if request.mode is RunwayMode.BATCH and not request.target.is_file():
        return "All mode requires a Class Table XML file."
    if apply and request.checks == frozenset({RunwayCheck.PATHS}):
        return "Paths Checker is check-only; select a fix-capable check."
    return None


def _discover_targets(
    request: RunwayRequest,
    report,
) -> tuple[list[_Target], int]:
    if request.mode is RunwayMode.SINGLE:
        candidates = [request.target]
    else:
        objective_root = request.target.parent / "ObjectiveRelatedData"
        if not objective_root.is_dir():
            raise ValueError(
                "ObjectiveRelatedData was not found beside the Class Table."
            )
        candidates = sorted(
            (
                path
                for path in objective_root.iterdir()
                if path.is_dir() and path.name.casefold().startswith("ocd_")
            ),
            key=lambda path: path.name.casefold(),
        )
    if not candidates:
        raise ValueError("No OCD objective folders were found.")

    targets: list[_Target] = []
    errors = 0
    for folder in candidates:
        if not folder.name.casefold().startswith("ocd_"):
            errors += 1
            report(
                DiagnosticSeverity.ERROR,
                "Objective folder name must start with OCD_.",
                folder,
                "runway",
            )
            continue
        suffix = folder.name[4:]
        phd_path = _find_file(folder, f"PHD_{suffix}.xml")
        if phd_path is None:
            errors += 1
            report(
                DiagnosticSeverity.ERROR,
                f"Missing PHD_{suffix}.xml.",
                folder,
                "runway",
            )
            continue
        pdx_path = _find_file(folder, f"PDX_{suffix}.xml")
        ocd_path = _find_file(folder, f"OCD_{suffix}.xml")
        targets.append(
            _Target(
                folder=folder,
                phd_path=phd_path,
                pdx_path=pdx_path,
                objective_name=_objective_name(ocd_path, folder.name),
            )
        )
    if not targets:
        raise ValueError("No objective folders with PHD XML were found.")
    return targets, errors


def _run_list_heading(
    target: _Target,
    phd_root: ET.Element,
    pdx_root: ET.Element,
    stats: _Stats,
    report,
    apply: bool,
) -> bool:
    changed = False
    pd_by_num = _pd_index(pdx_root)
    for phd in _phds_of_type(phd_root, "1"):
        phd_number = phd.get("Num") or "?"
        try:
            first, count = _phd_range(phd)
            calculated = calculate_runway_heading(pd_by_num, first, count)
            if calculated is None:
                raise ValueError("runway or takeoff point is missing")
            data = _required_child(phd, "Data")
            stored = float((data.text or "").strip())
        except ValueError as exc:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                f"PHD#{phd_number}: cannot check heading: {exc}.",
                target.folder,
                RunwayCheck.LIST_HEADING.value,
            )
            continue
        stored_text = f"{stored:.3f}"
        calculated_text = f"{calculated:.3f}"
        if stored_text == calculated_text:
            stats.ok += 1
            report(
                DiagnosticSeverity.SUCCESS,
                f"PHD#{phd_number}: heading {stored_text} is correct.",
                target.folder,
                RunwayCheck.LIST_HEADING.value,
            )
        elif apply:
            data.text = calculated_text
            stats.fixed += 1
            changed = True
            report(
                DiagnosticSeverity.SUCCESS,
                (
                    f"PHD#{phd_number}: heading {stored_text} → "
                    f"{calculated_text}."
                ),
                target.folder,
                RunwayCheck.LIST_HEADING.value,
            )
        else:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                (
                    f"PHD#{phd_number}: stored heading {stored_text}, "
                    f"calculated {calculated_text}."
                ),
                target.folder,
                RunwayCheck.LIST_HEADING.value,
            )
    return changed


def calculate_runway_heading(
    pd_by_num: dict[int, ET.Element],
    first_point_index: int,
    point_count: int,
) -> float | None:
    runway: tuple[float, float] | None = None
    takeoff: tuple[float, float] | None = None
    for number in range(first_point_index, first_point_index + point_count):
        pd = pd_by_num.get(number)
        if pd is None:
            continue
        point_type = _child_text(pd, "Type")
        if point_type == "1" and runway is None:
            runway = _coordinates(pd)
        elif point_type == "2" and takeoff is None:
            takeoff = _coordinates(pd)
        if runway is not None and takeoff is not None:
            break
    if runway is None or takeoff is None:
        return None
    dx = runway[0] - takeoff[0]
    dy = runway[1] - takeoff[1]
    return round(math.degrees(math.atan2(dx, dy)) % 360, 3)


def _run_dim_assignment(
    target: _Target,
    phd_root: ET.Element,
    pdx_root: ET.Element,
    stats: _Stats,
    report,
    apply: bool,
) -> bool:
    changed = False
    pd_by_num = _pd_index(pdx_root)
    boxes = build_runway_dim_boxes(phd_root, pd_by_num)
    for phd in _phds_of_type(phd_root, "1"):
        phd_number = phd.get("Num") or "?"
        try:
            runway_number_element = _required_child(phd, "RunwayNumber")
            runway_number = (runway_number_element.text or "").strip()
            first, count = _phd_range(phd)
            runway_point, takeoff_point = _runway_takeoff_points(
                pd_by_num,
                first,
                count,
            )
            if runway_point is None or takeoff_point is None:
                raise ValueError("runway or takeoff point is missing")
        except ValueError as exc:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                f"PHD#{phd_number}: cannot check assignment: {exc}.",
                target.folder,
                RunwayCheck.DIM_ASSIGNMENT.value,
            )
            continue

        assigned_box = boxes.get(runway_number)
        if assigned_box and point_in_box(runway_point, assigned_box):
            stats.ok += 1
            report(
                DiagnosticSeverity.SUCCESS,
                f"PHD#{phd_number}: RunwayDim {runway_number} is correct.",
                target.folder,
                RunwayCheck.DIM_ASSIGNMENT.value,
            )
            continue
        correct = next(
            (
                number
                for number, box in boxes.items()
                if point_in_box(runway_point, box)
            ),
            None,
        )
        if correct is None:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                (
                    f"PHD#{phd_number}: runway point is outside every "
                    "RunwayDim bounding box."
                ),
                target.folder,
                RunwayCheck.DIM_ASSIGNMENT.value,
            )
        elif apply:
            runway_number_element.text = correct
            stats.fixed += 1
            changed = True
            report(
                DiagnosticSeverity.SUCCESS,
                (
                    f"PHD#{phd_number}: RunwayDim {runway_number} → "
                    f"{correct}."
                ),
                target.folder,
                RunwayCheck.DIM_ASSIGNMENT.value,
            )
        else:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                (
                    f"PHD#{phd_number}: assigned RunwayDim "
                    f"{runway_number}, expected {correct}."
                ),
                target.folder,
                RunwayCheck.DIM_ASSIGNMENT.value,
            )
    return changed


def build_runway_dim_boxes(
    phd_root: ET.Element,
    pd_by_num: dict[int, ET.Element],
) -> dict[str, tuple[float, float, float, float]]:
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for phd in _phds_of_type(phd_root, "8"):
        runway_number = _child_text(phd, "RunwayNumber")
        first, count = _phd_range(phd)
        points = [
            _coordinates(pd_by_num[number])
            for number in range(first, first + count)
            if number in pd_by_num
        ]
        if runway_number and points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            boxes[runway_number] = (
                min(xs),
                max(xs),
                min(ys),
                max(ys),
            )
    return boxes


def point_in_box(
    point: tuple[float, float],
    box: tuple[float, float, float, float],
) -> bool:
    return (
        box[0] <= point[0] <= box[1]
        and box[2] <= point[1] <= box[3]
    )


def _run_dim_heading(
    target: _Target,
    phd_root: ET.Element,
    stats: _Stats,
    report,
    apply: bool,
    choice: HeadingChoice,
    cone: int,
    force: bool,
) -> bool:
    available: dict[str, list[str]] = {}
    for phd in _phds_of_type(phd_root, "1"):
        runway_number = _child_text(phd, "RunwayNumber")
        data = _child_text(phd, "Data")
        if runway_number is not None and data is not None:
            available.setdefault(runway_number, []).append(data)

    changed = False
    for phd in _phds_of_type(phd_root, "8"):
        phd_number = phd.get("Num") or "?"
        runway_number = _child_text(phd, "RunwayNumber") or ""
        data_element = phd.find("Data")
        current = (
            (data_element.text or "").strip()
            if data_element is not None
            else ""
        )
        candidates = available.get(runway_number, [])
        decision, replacement, differences = decide_dim_heading(
            current, candidates, choice, cone, force
        )
        detail = (
            f"PHD#{phd_number} RunwayDim {runway_number}: "
            f"current {current or '<missing>'}; first "
            f"{candidates[0] if candidates else '<missing>'}; second "
            f"{candidates[1] if len(candidates) > 1 else '<missing>'}; "
            f"circular differences {differences}; decision {decision}"
        )
        if stats.decisions is None:
            stats.decisions = {}
        stats.decisions[decision] = stats.decisions.get(decision, 0) + 1
        if decision == "unchanged":
            stats.ok += 1
            report(
                DiagnosticSeverity.SUCCESS,
                f"{detail}; unchanged.",
                target.folder,
                RunwayCheck.DIM_HEADING.value,
            )
        elif decision == "skipped":
            stats.warnings += 1
            report(
                DiagnosticSeverity.WARNING,
                f"{detail}; no safe automatic repair.",
                target.folder,
                RunwayCheck.DIM_HEADING.value,
            )
        elif apply:
            assert replacement is not None
            if data_element is None:
                data_element = ET.SubElement(phd, "Data")
            data_element.text = replacement
            stats.fixed += 1
            changed = True
            report(
                (DiagnosticSeverity.WARNING if decision == "forced"
                 else DiagnosticSeverity.SUCCESS),
                f"{detail}; changed to {replacement}.",
                target.folder,
                RunwayCheck.DIM_HEADING.value,
            )
        else:
            stats.warnings += 1
            report(
                DiagnosticSeverity.WARNING,
                f"{detail}; would change to {replacement}.",
                target.folder,
                RunwayCheck.DIM_HEADING.value,
            )
    return changed


def decide_dim_heading(
    current: str,
    candidates: list[str],
    choice: HeadingChoice,
    cone: int = 5,
    force: bool = False,
) -> tuple[str, str | None, list[float | None]]:
    """Choose a safe runway-end heading using circular angular distance."""
    def parse(value: str) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return round(number % 360, 3) if math.isfinite(number) else None

    selected = 1 if choice is HeadingChoice.SECOND else 0
    parsed = [parse(value) for value in candidates]
    current_number = parse(current)
    differences = [
        None if current_number is None or number is None else
        round(abs(((current_number - number + 180) % 360) - 180), 3)
        for number in parsed
    ]
    if force:
        if selected < len(candidates) and parsed[selected] is not None:
            replacement = candidates[selected]
            if current_number == parsed[selected]:
                return "unchanged", None, differences
            return "forced", replacement, differences
        return "skipped", None, differences
    if current_number is None or not any(number is not None for number in parsed):
        return "skipped", None, differences
    exact = [index for index, difference in enumerate(differences)
             if difference == 0]
    if exact:
        return "unchanged", None, differences
    nearest = min((difference for difference in differences
                   if difference is not None), default=None)
    if nearest is not None and nearest <= cone:
        nearest_indices = [index for index, difference in enumerate(differences)
                           if difference == nearest]
        if len({parsed[index] for index in nearest_indices}) > 1:
            return "skipped", None, differences
        return "near-match", candidates[nearest_indices[0]], differences
    if selected < len(candidates) and parsed[selected] is not None:
        return "fallback", candidates[selected], differences
    if len(candidates) == 1 and parsed[0] is not None:
        return "fallback", candidates[0], differences
    return "skipped", None, differences


def _run_paths(
    target: _Target,
    phd_root: ET.Element,
    pdx_root: ET.Element,
    stats: _Stats,
    report,
) -> None:
    pd_by_num = _pd_index(pdx_root)
    for phd in _phds_of_type(phd_root, "1"):
        phd_number = phd.get("Num") or "?"
        first, count = _phd_range(phd)
        points, children, root, parents = build_taxi_tree(
            pd_by_num,
            first,
            count,
        )
        findings_before = stats.errors + stats.warnings
        if root is None:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                f"PHD#{phd_number}: path tree is empty.",
                target.folder,
                RunwayCheck.PATHS.value,
            )
            continue
        if _child_text(points[root], "Type") != "1":
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                (
                    f"PHD#{phd_number} Pt{root}: root is "
                    f"{_type_label(points[root])}, expected Runway."
                ),
                target.folder,
                RunwayCheck.PATHS.value,
            )
        for relative_index in sorted(points):
            if relative_index != root and relative_index not in parents:
                stats.errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    (
                        f"PHD#{phd_number} Pt{relative_index} "
                        f"({_type_label(points[relative_index])}) is orphaned."
                    ),
                    target.folder,
                    RunwayCheck.PATHS.value,
                )

        for child, parent in parents.items():
            source = points[child]
            destination = points[parent]
            source_type = _child_text(source, "Type") or ""
            destination_type = _child_text(destination, "Type") or ""
            if parent >= child:
                stats.errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    (
                        f"PHD#{phd_number} Pt{child} → Pt{parent}: "
                        "parent index must be lower than child index."
                    ),
                    target.folder,
                    RunwayCheck.PATHS.value,
                )
            if destination_type not in PATH_ALLOWED.get(source_type, set()):
                stats.errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    (
                        f"PHD#{phd_number} Pt{child}"
                        f"({_type_label(source)}) → Pt{parent}"
                        f"({_type_label(destination)}): invalid transition."
                    ),
                    target.folder,
                    RunwayCheck.PATHS.value,
                )
                continue
            limits = PATH_DISTANCE_LIMITS.get(
                (source_type, destination_type)
            )
            if limits is None:
                continue
            distance = math.dist(
                _coordinates(source),
                _coordinates(destination),
            )
            minimum, maximum = limits
            if maximum is not None and distance > maximum:
                severe = distance > 2 * maximum
                _path_distance_finding(
                    target,
                    stats,
                    report,
                    severe,
                    (
                        f"PHD#{phd_number} Pt{child} → Pt{parent}: "
                        f"{distance:.0f} ft > max {maximum:.0f} ft."
                    ),
                )
            if minimum is not None and distance < minimum:
                severe = distance * 2 < minimum
                _path_distance_finding(
                    target,
                    stats,
                    report,
                    severe,
                    (
                        f"PHD#{phd_number} Pt{child} → Pt{parent}: "
                        f"{distance:.0f} ft < min {minimum:.0f} ft."
                    ),
                )
        if stats.errors + stats.warnings == findings_before:
            stats.ok += 1
            report(
                DiagnosticSeverity.SUCCESS,
                f"PHD#{phd_number}: path structure and distances are valid.",
                target.folder,
                RunwayCheck.PATHS.value,
            )


def build_taxi_tree(
    pd_by_num: dict[int, ET.Element],
    first_point_index: int,
    point_count: int,
) -> tuple[
    dict[int, ET.Element],
    dict[int, list[int]],
    int | None,
    dict[int, int],
]:
    points = {
        number - first_point_index: pd
        for number, pd in pd_by_num.items()
        if first_point_index <= number < first_point_index + point_count
        and _child_text(pd, "Type") in PATH_TYPES
    }
    if not points:
        return {}, {}, None, {}
    relative_indices = sorted(points)
    children = {index: [] for index in relative_indices}
    parents: dict[int, int] = {}
    root = relative_indices[0]
    for position, relative_index in enumerate(relative_indices):
        pd = points[relative_index]
        root_text = _child_text(pd, "RootIdx")
        if root_text is not None:
            try:
                parent = int(root_text)
            except ValueError:
                continue
            if parent in children and parent != relative_index:
                children[parent].append(relative_index)
                parents[relative_index] = parent
        elif position > 0:
            for candidate in reversed(relative_indices[:position]):
                if _child_text(points[candidate], "Type") not in PARK_TYPES:
                    children[candidate].append(relative_index)
                    parents[relative_index] = candidate
                    break
    return points, children, root, parents


def walk_taxi_paths(
    points: dict[int, ET.Element],
    children: dict[int, list[int]],
    root: int | None,
) -> tuple[tuple[tuple[ET.Element, int], ...], ...]:
    if root is None:
        return ()
    result: list[tuple[tuple[ET.Element, int], ...]] = []
    stack: list[tuple[int, list[int]]] = [(root, [root])]
    while stack:
        node, path = stack.pop()
        child_nodes = [
            child
            for child in children.get(node, [])
            if child not in path
        ]
        if not child_nodes:
            result.append(
                tuple((points[index], index) for index in reversed(path))
            )
        else:
            for child in child_nodes:
                stack.append((child, path + [child]))
    return tuple(result)


def _run_crossings(
    target: _Target,
    phd_root: ET.Element,
    pdx_root: ET.Element,
    stats: _Stats,
    report,
    apply: bool,
) -> bool:
    initial_findings = stats.errors + stats.warnings
    pd_by_num = _pd_index(pdx_root)
    polygons = build_runway_polygons(phd_root, pd_by_num)
    landing_sides = _landing_pattern_sides(phd_root)
    expectations: dict[int, tuple[int, str]] = {}
    path_points: set[int] = set()
    conflict_points: set[int] = set()
    no_interior_findings: set[tuple[str, int, int, str]] = set()

    for phd in _phds_of_type(phd_root, "1"):
        phd_number = phd.get("Num") or "?"
        first, count = _phd_range(phd)
        points, children, root, _parents = build_taxi_tree(
            pd_by_num,
            first,
            count,
        )
        for path in walk_taxi_paths(points, children, root):
            for pd, _relative_index in path:
                number = int(pd.get("Num") or "")
                path_points.add(number)
            pairs = build_crossing_pairs(path, polygons)
            for entry_position, exit_position, runway_number in pairs:
                if not any(
                    _child_text(path[position][0], "Type") in TAXI_TYPES
                    for position in range(entry_position + 1, exit_position)
                ):
                    entry_number = int(
                        path[entry_position][0].get("Num") or ""
                    )
                    exit_number = int(
                        path[exit_position][0].get("Num") or ""
                    )
                    finding_key = (
                        phd_number,
                        entry_number,
                        exit_number,
                        runway_number,
                    )
                    if finding_key not in no_interior_findings:
                        no_interior_findings.add(finding_key)
                        stats.warnings += 1
                        report(
                            DiagnosticSeverity.WARNING,
                            (
                                f"PHD#{phd_number}: crossing Runway "
                                f"{runway_number} has no intermediate "
                                "taxi point."
                            ),
                            target.folder,
                            RunwayCheck.CROSSING.value,
                        )
                for position, marker in (
                    (entry_position, 1),
                    (exit_position, -1),
                ):
                    pd = path[position][0]
                    absolute_number = int(pd.get("Num") or "")
                    expected = (marker, runway_number)
                    previous = expectations.get(absolute_number)
                    if previous is not None and previous != expected:
                        conflict_points.add(absolute_number)
                    else:
                        expectations[absolute_number] = expected

    for number in sorted(conflict_points):
        stats.errors += 1
        expectations.pop(number, None)
        report(
            DiagnosticSeverity.ERROR,
            f"PD#{number}: crossing branches require conflicting markers.",
            target.folder,
            RunwayCheck.CROSSING.value,
        )

    changed = False
    for number in sorted(path_points):
        pd = pd_by_num[number]
        point_type = _child_text(pd, "Type") or ""
        crossing_element = pd.find("CrossingPoint")
        parsed = _parse_crossing_point(crossing_element)
        invalid_marker = bool(
            crossing_element is not None
            and crossing_element.text
            and crossing_element.text.strip()
            and parsed is None
        )
        expected = expectations.get(number) if point_type in TAXI_TYPES else None
        if point_type not in TAXI_TYPES:
            if invalid_marker or parsed not in (None, 0):
                if apply:
                    _set_child(pd, "CrossingPoint", "0")
                    stats.fixed += 1
                    changed = True
                    report(
                        DiagnosticSeverity.SUCCESS,
                        f"PD#{number}: cleared non-taxi CrossingPoint.",
                        target.folder,
                        RunwayCheck.CROSSING.value,
                    )
                else:
                    stats.warnings += 1
                    report(
                        DiagnosticSeverity.WARNING,
                        f"PD#{number}: CrossingPoint is on a non-taxi point.",
                        target.folder,
                        RunwayCheck.CROSSING.value,
                    )
            continue
        if expected is None:
            if invalid_marker or parsed not in (None, 0):
                if apply:
                    _set_child(pd, "CrossingPoint", "0")
                    stats.fixed += 1
                    changed = True
                    report(
                        DiagnosticSeverity.SUCCESS,
                        f"PD#{number}: cleared stray CrossingPoint.",
                        target.folder,
                        RunwayCheck.CROSSING.value,
                    )
                else:
                    stats.errors += 1
                    report(
                        DiagnosticSeverity.ERROR,
                        (
                            f"PD#{number}: CrossingPoint={parsed!r} has no "
                            "detected runway crossing."
                        ),
                        target.folder,
                        RunwayCheck.CROSSING.value,
                    )
            continue

        marker, runway_number = expected
        expected_side = landing_sides.get(runway_number, "0")
        current_runway = _child_text(pd, "RunwayNumber")
        current_side = _child_text(pd, "RunwaySide")
        mismatched = (
            parsed != marker
            or current_runway != runway_number
            or current_side != expected_side
        )
        if not mismatched:
            continue
        if apply:
            _set_child(pd, "CrossingPoint", str(marker))
            _set_child(pd, "RunwayNumber", runway_number)
            _set_child(pd, "RunwaySide", expected_side)
            stats.fixed += 1
            changed = True
            report(
                DiagnosticSeverity.SUCCESS,
                (
                    f"PD#{number}: set CrossingPoint={marker}, "
                    f"RunwayNumber={runway_number}, "
                    f"RunwaySide={expected_side}."
                ),
                target.folder,
                RunwayCheck.CROSSING.value,
            )
        else:
            stats.errors += 1
            report(
                DiagnosticSeverity.ERROR,
                (
                    f"PD#{number}: expected CrossingPoint={marker}, "
                    f"RunwayNumber={runway_number}, "
                    f"RunwaySide={expected_side}."
                ),
                target.folder,
                RunwayCheck.CROSSING.value,
            )
    if stats.errors + stats.warnings == initial_findings:
        stats.ok += 1
        report(
            DiagnosticSeverity.SUCCESS,
            (
                f"Crossing markers are valid "
                f"({len(expectations) // 2} crossing(s))."
            ),
            target.folder,
            RunwayCheck.CROSSING.value,
        )
    return changed


def build_runway_polygons(
    phd_root: ET.Element,
    pd_by_num: dict[int, ET.Element],
) -> dict[str, tuple[tuple[float, float], ...]]:
    polygons: dict[str, tuple[tuple[float, float], ...]] = {}
    for phd in _phds_of_type(phd_root, "8"):
        runway_number = _child_text(phd, "RunwayNumber")
        if runway_number is None:
            continue
        first, count = _phd_range(phd)
        points = [
            _coordinates(pd_by_num[number])
            for number in range(first, first + count)
            if number in pd_by_num
            and _child_text(pd_by_num[number], "Type") == "8"
        ]
        if len(points) < 3:
            continue
        center_x = sum(point[0] for point in points) / len(points)
        center_y = sum(point[1] for point in points) / len(points)
        points.sort(
            key=lambda point: math.atan2(
                point[1] - center_y,
                point[0] - center_x,
            )
        )
        polygons[runway_number] = tuple(points)
    return polygons


def segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def cross(
        origin: tuple[float, float],
        point: tuple[float, float],
        query: tuple[float, float],
    ) -> float:
        return (
            (point[0] - origin[0]) * (query[1] - origin[1])
            - (point[1] - origin[1]) * (query[0] - origin[0])
        )

    d1 = cross(c, d, a)
    d2 = cross(c, d, b)
    d3 = cross(a, b, c)
    d4 = cross(a, b, d)
    return (
        ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
        and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))
    )


def segment_polygon_crossings(
    start: tuple[float, float],
    end: tuple[float, float],
    polygon: tuple[tuple[float, float], ...],
) -> int:
    return sum(
        segments_intersect(
            start,
            end,
            polygon[index],
            polygon[(index + 1) % len(polygon)],
        )
        for index in range(len(polygon))
    )


def build_crossing_pairs(
    path: tuple[tuple[ET.Element, int], ...],
    polygons: dict[str, tuple[tuple[float, float], ...]],
) -> tuple[tuple[int, int, str], ...]:
    coordinates = [_coordinates(pd) for pd, _relative in path]
    types = [_child_text(pd, "Type") or "" for pd, _relative in path]
    events: list[tuple[int, int, str, str]] = []
    for index in range(len(path) - 1):
        for runway_number, polygon in polygons.items():
            count = segment_polygon_crossings(
                coordinates[index],
                coordinates[index + 1],
                polygon,
            )
            if count >= 2:
                events.append((index, index + 1, runway_number, "through"))
            elif count == 1:
                events.append((index, index + 1, runway_number, "half"))

    pairs: list[tuple[int, int, str]] = []
    through_segments: set[tuple[int, str]] = set()
    for start, end, runway_number, kind in events:
        if (
            kind == "through"
            and types[start] in TAXI_TYPES
            and types[end] in TAXI_TYPES
        ):
            pairs.append((start, end, runway_number))
            through_segments.add((start, runway_number))
    halves = [
        (start, end, runway_number)
        for start, end, runway_number, kind in events
        if kind == "half" and (start, runway_number) not in through_segments
    ]
    index = 0
    while index < len(halves):
        start, _end, runway_number = halves[index]
        matching_exit = next(
            (
                candidate
                for candidate in range(index + 1, len(halves))
                if halves[candidate][2] == runway_number
            ),
            None,
        )
        if matching_exit is None:
            index += 1
            continue
        exit_end = halves[matching_exit][1]
        if types[start] in TAXI_TYPES and types[exit_end] in TAXI_TYPES:
            pairs.append((start, exit_end, runway_number))
        index = matching_exit + 1
    return tuple(sorted(pairs, key=lambda pair: pair[0]))


def _map_snapshot(
    target: _Target,
    phd_root: ET.Element,
    pdx_root: ET.Element,
) -> RunwayMapSnapshot:
    pd_by_num = _pd_index(pdx_root)
    polygons = build_runway_polygons(phd_root, pd_by_num)
    paths: list[RunwayMapPath] = []
    runway_points: list[tuple[float, float, str]] = []
    takeoff_points: list[tuple[float, float, str]] = []
    for phd in _phds_of_type(phd_root, "1"):
        phd_number = phd.get("Num") or "?"
        runway_number = _child_text(phd, "RunwayNumber") or "?"
        first, count = _phd_range(phd)
        runway, takeoff = _runway_takeoff_points(pd_by_num, first, count)
        if runway is not None:
            runway_points.append((*runway, runway_number))
        if takeoff is not None:
            takeoff_points.append((*takeoff, runway_number))
        points, children, root, _parents = build_taxi_tree(
            pd_by_num,
            first,
            count,
        )
        for path in walk_taxi_paths(points, children, root):
            paths.append(
                RunwayMapPath(
                    phd_number=phd_number,
                    points=tuple(
                        RunwayMapPoint(
                            x=_coordinates(pd)[0],
                            y=_coordinates(pd)[1],
                            relative_index=relative_index,
                            point_type=_child_text(pd, "Type") or "",
                            crossing_point=(
                                _parse_crossing_point(
                                    pd.find("CrossingPoint")
                                )
                                if _child_text(pd, "Type") in TAXI_TYPES
                                else 0
                            ),
                            runway_number=_child_text(pd, "RunwayNumber"),
                        )
                        for pd, relative_index in path
                    ),
                )
            )
    return RunwayMapSnapshot(
        folder=target.folder,
        title=f"{target.folder.name} — {target.objective_name}",
        polygons=tuple(
            RunwayPolygon(number, vertices)
            for number, vertices in polygons.items()
        ),
        paths=tuple(paths),
        runway_points=tuple(runway_points),
        takeoff_points=tuple(takeoff_points),
    )


def _runway_takeoff_points(
    pd_by_num: dict[int, ET.Element],
    first: int,
    count: int,
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    runway = None
    takeoff = None
    for number in range(first, first + count):
        pd = pd_by_num.get(number)
        if pd is None:
            continue
        point_type = _child_text(pd, "Type")
        if point_type == "1" and runway is None:
            runway = _coordinates(pd)
        elif point_type == "2" and takeoff is None:
            takeoff = _coordinates(pd)
    return runway, takeoff


def _landing_pattern_sides(phd_root: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for phd in _phds_of_type(phd_root, "1"):
        runway_number = _child_text(phd, "RunwayNumber")
        if runway_number is None:
            continue
        landing_pattern = _child_text(phd, "LandingPattern")
        result[runway_number] = "1" if landing_pattern == "1" else "0"
    return result


def _parse_crossing_point(element: ET.Element | None) -> int | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    if not value:
        return None
    if value.casefold() == "true":
        return 1
    if value.casefold() == "false":
        return 0
    try:
        return int(value)
    except ValueError:
        return None


def _path_distance_finding(
    target: _Target,
    stats: _Stats,
    report,
    severe: bool,
    message: str,
) -> None:
    severity = (
        DiagnosticSeverity.ERROR
        if severe
        else DiagnosticSeverity.WARNING
    )
    if severe:
        stats.errors += 1
    else:
        stats.warnings += 1
    report(
        severity,
        message,
        target.folder,
        RunwayCheck.PATHS.value,
    )


def _phds_of_type(
    root: ET.Element,
    phd_type: str,
) -> tuple[ET.Element, ...]:
    return tuple(
        phd
        for phd in root.findall("PHD")
        if _child_text(phd, "Type") == phd_type
    )


def _is_airbase(root: ET.Element) -> bool:
    return bool(_phds_of_type(root, "8"))


def _phd_range(phd: ET.Element) -> tuple[int, int]:
    first = int(_required_text(phd, "FirstPtIdx"))
    count = int(_required_text(phd, "PointCount"))
    if first < 0 or count < 0:
        raise ValueError("FirstPtIdx and PointCount must be non-negative")
    return first, count


def _pd_index(root: ET.Element) -> dict[int, ET.Element]:
    result: dict[int, ET.Element] = {}
    for pd in root.findall("PD"):
        number_text = pd.get("Num")
        if number_text is None:
            raise ValueError("PD entry is missing its Num attribute")
        number = int(number_text)
        if number in result:
            raise ValueError(f"Duplicate PD Num {number}")
        result[number] = pd
    return result


def _coordinates(element: ET.Element) -> tuple[float, float]:
    x = float(_required_text(element, "OffsetX"))
    y = float(_required_text(element, "OffsetY"))
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("Point coordinates must be finite")
    return x, y


def _required_text(element: ET.Element, name: str) -> str:
    child = _required_child(element, name)
    value = (child.text or "").strip()
    if not value:
        raise ValueError(f"{element.tag} is missing {name}")
    return value


def _required_child(element: ET.Element, name: str) -> ET.Element:
    child = element.find(name)
    if child is None:
        raise ValueError(f"{element.tag} is missing {name}")
    return child


def _child_text(element: ET.Element, name: str) -> str | None:
    child = element.find(name)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _set_child(element: ET.Element, name: str, value: str) -> None:
    child = element.find(name)
    if child is None:
        child = ET.SubElement(element, name)
    child.text = value


def _type_label(pd: ET.Element) -> str:
    point_type = _child_text(pd, "Type") or "?"
    return PATH_TYPE_NAMES.get(point_type, point_type)


def _find_file(folder: Path, name: str) -> Path | None:
    expected = name.casefold()
    for path in folder.iterdir():
        if path.is_file() and path.name.casefold() == expected:
            return path
    return None


def _objective_name(path: Path | None, fallback: str) -> str:
    if path is None:
        return fallback
    try:
        name = ET.parse(path).getroot().find(".//Name")
        if name is not None and (name.text or "").strip():
            return (name.text or "").strip()
    except (ET.ParseError, OSError):
        pass
    return fallback


def _commit_transaction(
    replacements: dict[Path, bytes], expected: dict[Path, bytes] | None = None,
) -> list[Path]:
    originals = {path: path.read_bytes() for path in replacements}
    if expected is not None and originals != expected:
        raise ValueError("Runway XML changed while preparing the edit; retry the operation.")
    committed: list[Path] = []
    try:
        for path, content in replacements.items():
            if originals[path] == content:
                continue
            _atomic_write(path, content)
            committed.append(path)
    except OSError as exc:
        rollback_errors: list[str] = []
        for path in reversed(committed):
            try:
                _atomic_write(path, originals[path])
            except OSError as rollback_error:
                rollback_errors.append(f"{path.name}: {rollback_error}")
        if rollback_errors:
            raise OSError(
                f"{exc}; rollback failed for " + "; ".join(rollback_errors)
            ) from exc
        raise
    return committed


def _atomic_write(path: Path, content: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        shutil.copymode(path, temporary_path)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _metrics(
    airbases: int,
    stats: dict[RunwayCheck, _Stats],
    changed_files: list[Path],
    processing_errors: int,
    map_data: RunwayMapComparison | None,
) -> dict[str, object]:
    check_metrics = {
        check.value: {
            "ok": value.ok,
            "fixed": value.fixed,
            "errors": value.errors,
            "warnings": value.warnings,
            "decisions": value.decisions or {},
        }
        for check, value in stats.items()
    }
    return {
        "airbases": airbases,
        "ok": sum(value.ok for value in stats.values()),
        "fixed": sum(value.fixed for value in stats.values()),
        "errors": (
            processing_errors + sum(value.errors for value in stats.values())
        ),
        "warnings": sum(value.warnings for value in stats.values()),
        "files": len(changed_files),
        "checks": check_metrics,
        "map": map_data,
    }


def _reporter(
    context: OperationContext,
    diagnostics: list[DiagnosticEvent],
):
    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | str,
        module: str,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module=module,
            target=str(target),
            message=message,
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    return report


def _failed_result(
    summary: str,
    diagnostics: list[DiagnosticEvent],
) -> OperationResult:
    return OperationResult(
        status=OperationStatus.FAILED,
        summary=summary,
        diagnostics=diagnostics,
        metrics={
            "airbases": 0,
            "ok": 0,
            "fixed": 0,
            "errors": 1,
            "warnings": 0,
            "files": 0,
            "checks": {},
            "map": None,
        },
    )

"""Parking-point preview and relocation services."""

from __future__ import annotations

import math
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
    OperationCancelled,
    OperationContext,
    OperationResult,
    OperationStatus,
    ProgressUpdate,
)


PARKING_TYPES = {"11", "12"}
HANGAR_TYPE = "45"


class ParkingMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class ParkingRequest:
    target: Path
    class_table: Path
    mode: ParkingMode = ParkingMode.SINGLE
    radius_feet: float = 10.0
    hangar_ct_numbers: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))
        object.__setattr__(self, "class_table", Path(self.class_table))
        object.__setattr__(
            self,
            "hangar_ct_numbers",
            tuple(sorted(set(self.hangar_ct_numbers))),
        )


@dataclass(frozen=True, slots=True)
class ParkingMove:
    objective_folder: Path
    objective_name: str
    pdx_path: Path
    point_number: str
    old_x: float
    old_y: float
    new_x: float
    new_y: float
    distance_feet: float
    hangar_ct_number: int


@dataclass(frozen=True, slots=True)
class ParkingObjectivePreview:
    folder: Path
    objective_name: str
    pdx_path: Path
    parking_points: int
    hangar_locations: int
    moves: tuple[ParkingMove, ...]


@dataclass(frozen=True, slots=True)
class ParkingPreview:
    request: ParkingRequest
    selected_hangar_ct_numbers: tuple[int, ...]
    objectives: tuple[ParkingObjectivePreview, ...]

    @property
    def moves(self) -> tuple[ParkingMove, ...]:
        return tuple(
            move
            for objective in self.objectives
            for move in objective.moves
        )


@dataclass(frozen=True, slots=True)
class _Target:
    folder: Path
    objective_name: str
    pdx_path: Path
    fed_path: Path


@dataclass(frozen=True, slots=True)
class _HangarLocation:
    ct_number: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class _ParkingPoint:
    number: str
    x: float
    y: float


def preview_parking(
    request: ParkingRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    """Build a non-mutating parking relocation preview."""
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)

    try:
        preview, errors = _build_preview(request, context, report)
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Parking preview cancelled.",
            request.target,
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Parking preview cancelled",
            diagnostics=diagnostics,
        )
    except (OSError, ValueError, ET.ParseError) as exc:
        report(
            DiagnosticSeverity.ERROR,
            f"Parking preview failed: {exc}",
            request.target,
        )
        return _failed_result("Parking preview failed", diagnostics)

    metrics = _preview_metrics(preview, errors)
    moves = len(preview.moves)
    if not preview.objectives:
        status = OperationStatus.FAILED
    elif errors or moves == 0:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS
    report(
        DiagnosticSeverity.SUCCESS if moves else DiagnosticSeverity.INFO,
        f"Preview contains {moves} parking relocation(s).",
        request.target,
    )
    return OperationResult(
        status=status,
        summary=(
            f"Previewed {metrics['parking_points']} parking point(s); "
            f"{moves} would move"
        ),
        diagnostics=diagnostics,
        metrics={"preview": preview, **metrics},
    )


def apply_parking(
    request: ParkingRequest,
    context: OperationContext | None = None,
    *,
    expected_preview: ParkingPreview | None = None,
) -> OperationResult:
    """Recalculate and atomically apply parking relocations."""
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    changed_files: list[Path] = []
    changed_points = 0

    try:
        preview, planning_errors = _build_preview(request, context, report)
        if (
            expected_preview is not None
            and _preview_signature(preview)
            != _preview_signature(expected_preview)
        ):
            raise ValueError(
                "Objective data changed after Preview; run Preview again."
            )
        if not preview.objectives:
            raise ValueError("No valid objective folders are available.")
        for index, objective in enumerate(preview.objectives, start=1):
            context.check_cancelled()
            if objective.moves:
                count = _apply_moves_atomic(
                    objective.pdx_path,
                    objective.moves,
                    context,
                    request.target if request.target.is_dir() else request.target.parent,
                )
                changed_files.append(objective.pdx_path)
                changed_points += count
                report(
                    DiagnosticSeverity.SUCCESS,
                    (
                        f"Relocated {count} parking point(s) in "
                        f"{objective.objective_name}."
                    ),
                    objective.pdx_path,
                )
            else:
                report(
                    DiagnosticSeverity.INFO,
                    "No parking points were within the selected radius.",
                    objective.pdx_path,
                )
            context.report_progress(
                ProgressUpdate(
                    current=index,
                    total=len(preview.objectives),
                    message=f"Applied {objective.folder.name}",
                )
            )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Operation cancelled; completed PDX files remain committed.",
            request.target,
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Parking relocation cancelled",
            diagnostics=diagnostics,
            changed_files=changed_files,
            metrics={
                "objectives": len(changed_files),
                "moves": changed_points,
                "files": len(changed_files),
            },
        )
    except (OSError, ValueError, ET.ParseError) as exc:
        report(
            DiagnosticSeverity.ERROR,
            f"Parking relocation failed: {exc}",
            request.target,
        )
        return OperationResult(
            status=(
                OperationStatus.WARNING
                if changed_files
                else OperationStatus.FAILED
            ),
            summary="Parking relocation failed",
            diagnostics=diagnostics,
            changed_files=changed_files,
            metrics={
                "objectives": len(preview.objectives)
                if "preview" in locals()
                else 0,
                "moves": changed_points,
                "files": len(changed_files),
                "errors": 1,
            },
        )

    metrics = _preview_metrics(preview, planning_errors)
    metrics["files"] = len(changed_files)
    metrics["moves"] = changed_points
    if planning_errors or changed_points == 0:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS
    return OperationResult(
        status=status,
        summary=(
            f"Relocated {changed_points} parking point(s) across "
            f"{len(changed_files)} PDX file(s)"
        ),
        diagnostics=diagnostics,
        changed_files=changed_files,
        metrics=metrics,
    )


def _build_preview(
    request: ParkingRequest,
    context: OperationContext,
    report,
) -> tuple[ParkingPreview, int]:
    validation_error = _validate_request(request)
    if validation_error:
        raise ValueError(validation_error)

    available_ct_numbers = _read_hangar_ct_numbers(request.class_table)
    requested = set(request.hangar_ct_numbers)
    select_all = not requested or 0 in requested
    if select_all:
        selected = available_ct_numbers
    else:
        selected = available_ct_numbers & requested
        missing = sorted(requested - available_ct_numbers)
        if missing:
            report(
                DiagnosticSeverity.WARNING,
                "Requested CT number(s) are not Type-45 hangars: "
                + ", ".join(str(value) for value in missing),
                request.class_table,
            )
    if not selected:
        raise ValueError(
            "No selected Type-45 hangar CT numbers were found."
        )
    report(
        DiagnosticSeverity.INFO,
        f"Using {len(selected)} hangar CT number(s).",
        request.class_table,
    )

    targets, discovery_errors = _discover_targets(request, report)
    objectives: list[ParkingObjectivePreview] = []
    errors = discovery_errors
    for index, target in enumerate(targets, start=1):
        context.check_cancelled()
        try:
            hangars = _read_hangar_locations(target.fed_path, selected)
            parking_points = _read_parking_points(target.pdx_path)
            moves = _calculate_moves(
                target,
                parking_points,
                hangars,
                request.radius_feet,
            )
            objectives.append(
                ParkingObjectivePreview(
                    folder=target.folder,
                    objective_name=target.objective_name,
                    pdx_path=target.pdx_path,
                    parking_points=len(parking_points),
                    hangar_locations=len(hangars),
                    moves=moves,
                )
            )
            if not hangars:
                report(
                    DiagnosticSeverity.WARNING,
                    "No matching hangar features were present in FED XML.",
                    target.fed_path,
                )
            else:
                report(
                    DiagnosticSeverity.INFO,
                    (
                        f"{len(parking_points)} parking point(s), "
                        f"{len(hangars)} hangar location(s), "
                        f"{len(moves)} move(s)."
                    ),
                    target.folder,
                )
        except (OSError, ValueError, ET.ParseError) as exc:
            errors += 1
            report(
                DiagnosticSeverity.ERROR,
                f"Could not preview objective: {exc}",
                target.folder,
            )
        context.report_progress(
            ProgressUpdate(
                current=index,
                total=len(targets),
                message=f"Previewed {target.folder.name}",
            )
        )

    return (
        ParkingPreview(
            request=request,
            selected_hangar_ct_numbers=tuple(sorted(selected)),
            objectives=tuple(objectives),
        ),
        errors,
    )


def _validate_request(request: ParkingRequest) -> str | None:
    if not request.target.exists():
        return "The selected objective path does not exist."
    if not request.target.is_dir():
        return "The selected objective path must be a folder."
    if not request.class_table.is_file():
        return "The selected Class Table XML file does not exist."
    if not math.isfinite(request.radius_feet) or request.radius_feet < 0:
        return "Radius must be a finite value greater than or equal to 0."
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in request.hangar_ct_numbers
    ):
        return "Hangar CT numbers must be non-negative integers."
    return None


def _read_hangar_ct_numbers(path: Path) -> set[int]:
    root = ET.parse(path).getroot()
    result: set[int] = set()
    for element in root.findall("CT"):
        if _optional_text(element, "Type") != HANGAR_TYPE:
            continue
        number = element.get("Num")
        if number is None:
            raise ValueError("Type-45 CT entry is missing its Num attribute.")
        try:
            result.add(int(number))
        except ValueError as exc:
            raise ValueError(
                f"Type-45 CT Num is not an integer: {number!r}."
            ) from exc
    if not result:
        raise ValueError("The Class Table contains no Type-45 hangars.")
    return result


def _discover_targets(
    request: ParkingRequest,
    report,
) -> tuple[list[_Target], int]:
    if request.mode is ParkingMode.SINGLE:
        candidates = [request.target]
    else:
        candidates = sorted(
            (
                path
                for path in request.target.iterdir()
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
            )
            continue
        suffix = folder.name[4:]
        fed_path = _find_named_file(folder, f"FED_{suffix}.xml")
        pdx_path = _find_named_file(folder, f"PDX_{suffix}.xml")
        if fed_path is None or pdx_path is None:
            errors += 1
            missing = []
            if fed_path is None:
                missing.append(f"FED_{suffix}.xml")
            if pdx_path is None:
                missing.append(f"PDX_{suffix}.xml")
            report(
                DiagnosticSeverity.ERROR,
                "Missing required objective file(s): " + ", ".join(missing),
                folder,
            )
            continue
        ocd_path = _find_named_file(folder, f"OCD_{suffix}.xml")
        targets.append(
            _Target(
                folder=folder,
                objective_name=_read_objective_name(ocd_path, folder.name),
                pdx_path=pdx_path,
                fed_path=fed_path,
            )
        )
    if not targets and errors:
        raise ValueError("No complete objective folders were found.")
    return targets, errors


def _read_objective_name(path: Path | None, fallback: str) -> str:
    if path is None:
        return fallback
    try:
        root = ET.parse(path).getroot()
        name = root.find(".//Name")
        if name is not None and (name.text or "").strip():
            return (name.text or "").strip()
    except (OSError, ET.ParseError):
        pass
    return fallback


def _read_hangar_locations(
    path: Path,
    selected_ct_numbers: set[int],
) -> tuple[_HangarLocation, ...]:
    root = ET.parse(path).getroot()
    result: list[_HangarLocation] = []
    for element in root.findall("FED"):
        feature_text = _optional_text(element, "FeatureCtIdx")
        if feature_text is None:
            continue
        try:
            feature_number = int(feature_text)
        except ValueError:
            continue
        if feature_number not in selected_ct_numbers:
            continue
        x = _required_float(element, "OffsetX", "FED")
        y = _required_float(element, "OffsetY", "FED")
        result.append(_HangarLocation(feature_number, x, y))
    return tuple(result)


def _read_parking_points(path: Path) -> tuple[_ParkingPoint, ...]:
    root = ET.parse(path).getroot()
    points: list[_ParkingPoint] = []
    seen_numbers: set[str] = set()
    for element in root.findall("PD"):
        if _optional_text(element, "Type") not in PARKING_TYPES:
            continue
        number = (element.get("Num") or "").strip()
        if not number:
            raise ValueError("Parking PD entry is missing its Num attribute.")
        if number in seen_numbers:
            raise ValueError(f"Duplicate parking PD Num: {number}.")
        seen_numbers.add(number)
        points.append(
            _ParkingPoint(
                number=number,
                x=_required_float(element, "OffsetX", "PD"),
                y=_required_float(element, "OffsetY", "PD"),
            )
        )
    return tuple(points)


def _required_float(
    element: ET.Element,
    field_name: str,
    record_name: str,
) -> float:
    value = _optional_text(element, field_name)
    if value is None:
        raise ValueError(f"{record_name} entry is missing {field_name}.")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(
            f"{record_name} {field_name} is not numeric: {value!r}."
        ) from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{record_name} {field_name} must be finite.")
    return parsed


def _optional_text(element: ET.Element, field_name: str) -> str | None:
    child = element.find(field_name)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _calculate_moves(
    target: _Target,
    parking_points: tuple[_ParkingPoint, ...],
    hangars: tuple[_HangarLocation, ...],
    radius_feet: float,
) -> tuple[ParkingMove, ...]:
    moves: list[ParkingMove] = []
    for point in parking_points:
        nearest: _HangarLocation | None = None
        nearest_distance = math.inf
        for hangar in hangars:
            distance = math.hypot(
                point.x - hangar.x,
                point.y - hangar.y,
            )
            if distance <= radius_feet and distance < nearest_distance:
                nearest = hangar
                nearest_distance = distance
        if nearest is None or (
            point.x == nearest.x and point.y == nearest.y
        ):
            continue
        moves.append(
            ParkingMove(
                objective_folder=target.folder,
                objective_name=target.objective_name,
                pdx_path=target.pdx_path,
                point_number=point.number,
                old_x=point.x,
                old_y=point.y,
                new_x=nearest.x,
                new_y=nearest.y,
                distance_feet=nearest_distance,
                hangar_ct_number=nearest.ct_number,
            )
        )
    return tuple(moves)


_PD_BLOCK_PATTERN = re.compile(
    r"<PD\b(?P<attributes>[^>]*)>.*?</PD\s*>",
    re.DOTALL,
)
_PD_NUMBER_PATTERN = re.compile(
    r"\bNum\s*=\s*[\"'](?P<number>[^\"']+)[\"']"
)
_OFFSET_X_PATTERN = re.compile(
    r"(<OffsetX\b[^>]*>)([^<]*)(</OffsetX\s*>)"
)
_OFFSET_Y_PATTERN = re.compile(
    r"(<OffsetY\b[^>]*>)([^<]*)(</OffsetY\s*>)"
)


def _apply_moves_atomic(
    path: Path,
    moves: tuple[ParkingMove, ...],
    context: OperationContext | None = None,
    scope: Path | None = None,
) -> int:
    original = path.read_bytes()
    has_bom = original.startswith(b"\xef\xbb\xbf")
    text = original.decode("utf-8-sig")
    move_map = {move.point_number: move for move in moves}
    changed_numbers: set[str] = set()

    def replace_block(match: re.Match[str]) -> str:
        attributes = match.group("attributes")
        number_match = _PD_NUMBER_PATTERN.search(attributes)
        if number_match is None:
            return match.group(0)
        number = number_match.group("number").strip()
        move = move_map.get(number)
        if move is None:
            return match.group(0)
        block = match.group(0)
        block, x_count = _OFFSET_X_PATTERN.subn(
            lambda field: (
                field.group(1)
                + f"{move.new_x:.3f}"
                + field.group(3)
            ),
            block,
            count=1,
        )
        block, y_count = _OFFSET_Y_PATTERN.subn(
            lambda field: (
                field.group(1)
                + f"{move.new_y:.3f}"
                + field.group(3)
            ),
            block,
            count=1,
        )
        if x_count != 1 or y_count != 1:
            raise ValueError(
                f"PD {number} is missing writable OffsetX/OffsetY fields."
            )
        changed_numbers.add(number)
        return block

    updated = _PD_BLOCK_PATTERN.sub(replace_block, text)
    missing = set(move_map) - changed_numbers
    if missing:
        raise ValueError(
            "Could not locate previewed PD record(s): "
            + ", ".join(sorted(missing))
        )
    encoded = updated.encode("utf-8")
    if has_bom:
        encoded = b"\xef\xbb\xbf" + encoded
    if context is not None:
        context.backup_files([path], scope or path.parent)
    _atomic_write_bytes(path, encoded)
    return len(changed_numbers)


def _find_named_file(folder: Path, name: str) -> Path | None:
    expected = name.casefold()
    for path in folder.iterdir():
        if path.is_file() and path.name.casefold() == expected:
            return path
    return None


def _atomic_write_bytes(destination: Path, content: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        shutil.copymode(destination, temporary_path)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _preview_metrics(
    preview: ParkingPreview,
    errors: int,
) -> dict[str, int]:
    return {
        "objectives": len(preview.objectives),
        "parking_points": sum(
            item.parking_points for item in preview.objectives
        ),
        "hangars": sum(
            item.hangar_locations for item in preview.objectives
        ),
        "moves": len(preview.moves),
        "errors": errors,
    }


def _preview_signature(preview: ParkingPreview) -> tuple[object, ...]:
    return (
        preview.request,
        preview.selected_hangar_ct_numbers,
        tuple(
            (
                objective.folder,
                objective.pdx_path,
                objective.parking_points,
                objective.hangar_locations,
                tuple(
                    (
                        move.point_number,
                        move.old_x,
                        move.old_y,
                        move.new_x,
                        move.new_y,
                        move.hangar_ct_number,
                    )
                    for move in objective.moves
                ),
            )
            for objective in preview.objectives
        ),
    )


def _reporter(
    context: OperationContext,
    diagnostics: list[DiagnosticEvent],
):
    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | str = "",
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="parking-fixer",
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
            "objectives": 0,
            "parking_points": 0,
            "hangars": 0,
            "moves": 0,
            "errors": 1,
        },
    )

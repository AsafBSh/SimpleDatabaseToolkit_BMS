"""Feature scanning and offset/value transformation services."""

from __future__ import annotations

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


class OffsetMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


class OffsetOperation(str, Enum):
    XY = "xy"
    SET_Z = "set_z"
    ROTATE = "rotate"
    SET_HEADING = "set_heading"
    SET_VALUE = "set_value"


@dataclass(frozen=True, slots=True)
class FeatureScanRequest:
    target: Path
    mode: OffsetMode = OffsetMode.SINGLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))


@dataclass(frozen=True, slots=True)
class OffsetAdjustment:
    operation: OffsetOperation
    x: float = 0.0
    y: float = 0.0
    value: float = 0.0

    @property
    def description(self) -> str:
        if self.operation is OffsetOperation.XY:
            return f"Add local XY offset (X={self.x:g}, Y={self.y:g})"
        if self.operation is OffsetOperation.SET_Z:
            return f"Set Z to {self.value:g}"
        if self.operation is OffsetOperation.ROTATE:
            return f"Rotate heading by {self.value:g} degrees"
        if self.operation is OffsetOperation.SET_HEADING:
            return f"Set heading to {self.value:g} degrees"
        return f"Set value to {self.value:g}"


@dataclass(frozen=True, slots=True)
class OffsetRequest:
    target: Path
    feature_number: int
    adjustment: OffsetAdjustment
    mode: OffsetMode = OffsetMode.SINGLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))


@dataclass(frozen=True, slots=True)
class OffsetTarget:
    objective_name: str
    fed_path: Path
    ocd_path: Path


def scan_features(
    request: FeatureScanRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    feature_counts: dict[int, int] = {}

    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Offset Fixer",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    targets, discovery_error = _discover_targets(request.target, request.mode)
    if discovery_error is not None:
        report(DiagnosticSeverity.ERROR, discovery_error, request.target)
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Feature scan target is invalid",
            diagnostics=diagnostics,
            metrics=_scan_metrics(0, feature_counts, 0),
        )

    parse_errors = 0
    processed_files = 0
    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                root = ET.parse(target.fed_path).getroot()
                file_entries = 0
                for fed in root.findall(".//FED"):
                    feature = fed.find("FeatureCtIdx")
                    if feature is None:
                        continue
                    try:
                        feature_number = int((feature.text or "").strip())
                    except ValueError:
                        continue
                    feature_counts[feature_number] = (
                        feature_counts.get(feature_number, 0) + 1
                    )
                    file_entries += 1

                processed_files += 1
                report(
                    DiagnosticSeverity.INFO,
                    f"Scanned {file_entries} FED entries in "
                    f"{target.objective_name}.",
                    target.fed_path,
                )
            except (ET.ParseError, OSError) as exc:
                parse_errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not scan FED XML: {exc}",
                    target.fed_path,
                )

            context.report_progress(
                ProgressUpdate(
                    current=index,
                    total=len(targets),
                    message=f"Scanned {target.objective_name}",
                )
            )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Feature scan cancelled at a safe file boundary.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Feature scan cancelled",
            diagnostics=diagnostics,
            metrics=_scan_metrics(
                processed_files,
                feature_counts,
                parse_errors,
            ),
        )

    if parse_errors and not processed_files:
        status = OperationStatus.FAILED
    elif parse_errors or not feature_counts:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS

    total_entries = sum(feature_counts.values())
    summary = (
        f"Found {len(feature_counts)} unique feature(s) across "
        f"{total_entries} FED entries"
    )
    report(DiagnosticSeverity.SUCCESS, summary)
    return OperationResult(
        status=status,
        summary=summary,
        diagnostics=diagnostics,
        metrics=_scan_metrics(processed_files, feature_counts, parse_errors),
    )


def apply_offset(
    request: OffsetRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    changed_files: list[Path] = []

    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Offset Fixer",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    validation_error = _validate_request(request)
    if validation_error is not None:
        report(DiagnosticSeverity.ERROR, validation_error, request.target)
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Offset request is invalid",
            diagnostics=diagnostics,
            metrics=_apply_metrics(0, 0, 0, 0),
        )

    targets, discovery_error = _discover_targets(request.target, request.mode)
    if discovery_error is not None:
        report(DiagnosticSeverity.ERROR, discovery_error, request.target)
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Offset target is invalid",
            diagnostics=diagnostics,
            metrics=_apply_metrics(0, 0, 0, 0),
        )

    changed_entries = 0
    processed_files = 0
    error_count = 0

    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                count = _apply_to_file(
                    target.fed_path,
                    request.feature_number,
                    request.adjustment,
                    context,
                    request.target if request.target.is_dir() else request.target.parent,
                )
                processed_files += 1
                changed_entries += count
                if count:
                    changed_files.append(target.fed_path)
                    report(
                        DiagnosticSeverity.SUCCESS,
                        f"Updated {count} feature(s) in "
                        f"{_read_objective_name(target)}.",
                        target.fed_path,
                    )
                else:
                    report(
                        DiagnosticSeverity.INFO,
                        f"Feature {request.feature_number} was not present in "
                        f"{target.objective_name}.",
                        target.fed_path,
                    )
            except (ET.ParseError, OSError, ValueError) as exc:
                error_count += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not update FED XML: {exc}",
                    target.fed_path,
                )

            context.report_progress(
                ProgressUpdate(
                    current=index,
                    total=len(targets),
                    message=f"Processed {target.objective_name}",
                )
            )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Operation cancelled; completed files remain committed.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Offset operation cancelled",
            diagnostics=diagnostics,
            changed_files=changed_files,
            metrics=_apply_metrics(
                processed_files,
                changed_entries,
                len(changed_files),
                error_count,
            ),
        )

    if error_count and not processed_files:
        status = OperationStatus.FAILED
    elif error_count or changed_entries == 0:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS

    summary = (
        f"Updated {changed_entries} feature(s) across "
        f"{len(changed_files)} file(s)"
    )
    return OperationResult(
        status=status,
        summary=summary,
        diagnostics=diagnostics,
        changed_files=changed_files,
        metrics=_apply_metrics(
            processed_files,
            changed_entries,
            len(changed_files),
            error_count,
        ),
    )


def _discover_targets(
    selected_path: Path,
    mode: OffsetMode,
) -> tuple[list[OffsetTarget], str | None]:
    if mode is OffsetMode.SINGLE:
        folder = selected_path.parent if selected_path.is_file() else selected_path
        if not folder.is_dir():
            return [], "Single mode requires an objective folder."
        if not folder.name.upper().startswith("OCD_"):
            return [], "Objective folder name must start with OCD_."
        candidates = [folder]
    else:
        if not selected_path.is_file():
            return [], "Batch mode requires a Class Table XML file."
        objective_data = selected_path.parent / "ObjectiveRelatedData"
        if not objective_data.is_dir():
            return [], (
                "ObjectiveRelatedData directory was not found beside "
                "the Class Table."
            )
        candidates = sorted(
            (
                path
                for path in objective_data.iterdir()
                if path.is_dir() and path.name.upper().startswith("OCD_")
            ),
            key=lambda path: path.name,
        )

    targets: list[OffsetTarget] = []
    for folder in candidates:
        suffix = folder.name[4:]
        fed_path = folder / f"FED_{suffix}.xml"
        if not fed_path.is_file():
            continue
        targets.append(
            OffsetTarget(
                objective_name=folder.name,
                fed_path=fed_path,
                ocd_path=folder / f"OCD_{suffix}.xml",
            )
        )

    if not targets:
        return [], "No matching FED files were found."
    return targets, None


def _validate_request(request: OffsetRequest) -> str | None:
    if request.feature_number < 0:
        return "Feature number cannot be negative."

    values = (
        (request.adjustment.x, request.adjustment.y)
        if request.adjustment.operation is OffsetOperation.XY
        else (request.adjustment.value,)
    )
    if not all(math.isfinite(value) for value in values):
        return "Adjustment values must be finite numbers."

    if (
        request.adjustment.operation is OffsetOperation.SET_Z
        and not -10_000 <= request.adjustment.value <= 10_000
    ):
        return "Z value must be between -10000 and 10000."

    if (
        request.adjustment.operation is OffsetOperation.SET_HEADING
        and not 0 <= request.adjustment.value <= 360
    ):
        return "Heading must be between 0 and 360."

    if (
        request.adjustment.operation is OffsetOperation.SET_VALUE
        and not 0 <= request.adjustment.value <= 100
    ):
        return "Value must be between 0 and 100."

    return None


def _apply_to_file(
    file_path: Path,
    feature_number: int,
    adjustment: OffsetAdjustment,
    context: OperationContext | None = None,
    scope: Path | None = None,
) -> int:
    if adjustment.operation in (
        OffsetOperation.SET_Z,
        OffsetOperation.SET_HEADING,
        OffsetOperation.SET_VALUE,
    ):
        return _apply_set_operation(
            file_path,
            feature_number,
            adjustment,
            context,
            scope,
        )

    original = file_path.read_bytes()
    root = ET.fromstring(original)
    matching_feds = [
        fed
        for fed in root.findall("FED")
        if _feature_number(fed) == feature_number
    ]

    for fed in matching_feds:
        if adjustment.operation is OffsetOperation.XY:
            _apply_xy(fed, adjustment.x, adjustment.y)
        else:
            _apply_rotation(fed, adjustment.value)

    if matching_feds:
        xml_bytes = patch_xml(original, root)
        if context is not None:
            context.backup_files([file_path], scope or file_path.parent)
        if file_path.read_bytes() != original:
            raise ValueError("FED XML changed while preparing the edit; retry the operation.")
        _atomic_write_bytes(file_path, xml_bytes)
    return len(matching_feds)


def _apply_set_operation(
    file_path: Path,
    feature_number: int,
    adjustment: OffsetAdjustment,
    context: OperationContext | None = None,
    scope: Path | None = None,
) -> int:
    original_bytes = file_path.read_bytes()
    root = ET.fromstring(original_bytes)

    if adjustment.operation is OffsetOperation.SET_HEADING:
        field_name = "Heading"
        replacement = f"{adjustment.value:.3f}"
    elif adjustment.operation is OffsetOperation.SET_Z:
        field_name = "OffsetZ"
        replacement = f"{adjustment.value:.3f}"
    else:
        field_name = "Value"
        replacement = str(int(adjustment.value))

    changes = 0
    for fed in root.findall("FED"):
        if _feature_number(fed) != feature_number:
            continue
        field = fed.find(field_name)
        if field is not None and (field.text or "").strip() != replacement:
            field.text = replacement
            changes += 1
    if changes:
        encoded = patch_xml(original_bytes, root)
        if context is not None:
            context.backup_files([file_path], scope or file_path.parent)
        if file_path.read_bytes() != original_bytes:
            raise ValueError("FED XML changed while preparing the edit; retry the operation.")
        _atomic_write_bytes(file_path, encoded)
    return changes


def _feature_number(fed: ET.Element) -> int | None:
    feature = fed.find("FeatureCtIdx")
    if feature is None:
        return None
    try:
        return int((feature.text or "").strip())
    except ValueError:
        return None


def _apply_xy(fed: ET.Element, x_offset: float, y_offset: float) -> None:
    heading_element = _required_element(fed, "Heading")
    offset_x_element = _required_element(fed, "OffsetX")
    offset_y_element = _required_element(fed, "OffsetY")

    heading_radians = math.radians(float(heading_element.text or ""))
    new_x = (
        float(offset_x_element.text or "")
        + x_offset * math.sin(heading_radians)
        + y_offset * math.cos(heading_radians)
    )
    new_y = (
        float(offset_y_element.text or "")
        + x_offset * math.cos(heading_radians)
        - y_offset * math.sin(heading_radians)
    )
    offset_x_element.text = f"{new_x:.3f}"
    offset_y_element.text = f"{new_y:.3f}"


def _apply_rotation(fed: ET.Element, rotation: float) -> None:
    heading_element = _required_element(fed, "Heading")
    heading = (float(heading_element.text or "") + rotation) % 360
    heading_element.text = f"{heading:.1f}"


def _required_element(parent: ET.Element, name: str) -> ET.Element:
    element = parent.find(name)
    if element is None:
        raise ValueError(f"Matching FED entry is missing {name}.")
    return element


def _read_objective_name(target: OffsetTarget) -> str:
    if not target.ocd_path.is_file():
        return target.objective_name
    try:
        root = ET.parse(target.ocd_path).getroot()
        name = root.findtext("OCD/Name")
        return name.strip() if name and name.strip() else target.objective_name
    except (ET.ParseError, OSError):
        return target.objective_name


def _atomic_write_bytes(destination: Path, content: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        shutil.copymode(destination, temporary_path)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _scan_metrics(
    files: int,
    feature_counts: dict[int, int],
    errors: int,
) -> dict[str, object]:
    return {
        "files": files,
        "unique_features": len(feature_counts),
        "entries": sum(feature_counts.values()),
        "features": dict(sorted(feature_counts.items())),
        "errors": errors,
    }


def _apply_metrics(
    files: int,
    changed_entries: int,
    changed_files: int,
    errors: int,
) -> dict[str, int]:
    return {
        "files": files,
        "entries": changed_entries,
        "changed_files": changed_files,
        "errors": errors,
    }

"""Feature replacement service extracted from the legacy Replace page."""

from __future__ import annotations

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


class ReplaceMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class ReplaceFeatureRequest:
    target: Path
    old_feature_number: int
    new_feature_number: int
    mode: ReplaceMode = ReplaceMode.SINGLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))


@dataclass(frozen=True, slots=True)
class ReplacementTarget:
    objective_name: str
    file_path: Path


def scan_replacements(
    request: ReplaceFeatureRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    return _run_replacement(request, context or OperationContext(), apply=False)


def replace_features(
    request: ReplaceFeatureRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    return _run_replacement(request, context or OperationContext(), apply=True)


def _run_replacement(
    request: ReplaceFeatureRequest,
    context: OperationContext,
    *,
    apply: bool,
) -> OperationResult:
    diagnostics: list[DiagnosticEvent] = []
    changed_files: list[Path] = []

    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Replace Features",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    if request.old_feature_number < 0 or request.new_feature_number < 0:
        report(
            DiagnosticSeverity.ERROR,
            "Feature numbers cannot be negative.",
            request.target,
        )
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Feature numbers are invalid",
            diagnostics=diagnostics,
            metrics={"files": 0, "matches": 0, "changed_files": 0},
        )

    if request.old_feature_number == request.new_feature_number:
        report(
            DiagnosticSeverity.ERROR,
            "Old and replacement feature numbers must differ.",
            request.target,
        )
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Replacement would not change any values",
            diagnostics=diagnostics,
            metrics={"files": 0, "matches": 0, "changed_files": 0},
        )

    targets, discovery_error = _discover_targets(request)
    if discovery_error is not None:
        report(DiagnosticSeverity.ERROR, discovery_error, request.target)
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Replacement target is invalid",
            diagnostics=diagnostics,
            metrics={"files": 0, "matches": 0, "changed_files": 0},
        )

    if not targets:
        report(
            DiagnosticSeverity.WARNING,
            "No matching FED files were found.",
            request.target,
        )
        return OperationResult(
            status=OperationStatus.WARNING,
            summary="No matching FED files found",
            diagnostics=diagnostics,
            metrics={"files": 0, "matches": 0, "changed_files": 0},
        )

    total_matches = 0
    processed_files = 0
    error_count = 0

    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                original = target.file_path.read_bytes()
                root = ET.fromstring(original)
                matches = _matching_feature_elements(
                    root,
                    str(request.old_feature_number),
                )
                total_matches += len(matches)
                processed_files += 1

                if apply and matches:
                    for element in matches:
                        element.text = str(request.new_feature_number)
                    content = patch_xml(original, root)
                    context.backup_files(
                        [target.file_path],
                        request.target if request.target.is_dir() else request.target.parent,
                    )
                    if target.file_path.read_bytes() != original:
                        raise ValueError("FED XML changed while preparing the edit; retry the operation.")
                    _atomic_write_xml(content, target.file_path)
                    changed_files.append(target.file_path)
                    report(
                        DiagnosticSeverity.SUCCESS,
                        f"Replaced {len(matches)} occurrence(s) in "
                        f"{target.objective_name}.",
                        target.file_path,
                    )
                elif matches:
                    report(
                        DiagnosticSeverity.INFO,
                        f"Found {len(matches)} replacement candidate(s) in "
                        f"{target.objective_name}.",
                        target.file_path,
                    )
                else:
                    report(
                        DiagnosticSeverity.INFO,
                        f"No occurrences found in {target.objective_name}.",
                        target.file_path,
                    )
            except (ET.ParseError, OSError, ValueError) as exc:
                error_count += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not process FED XML: {exc}",
                    target.file_path,
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
            "Operation cancelled at a safe file boundary.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Feature replacement cancelled",
            diagnostics=diagnostics,
            changed_files=changed_files,
            metrics={
                "files": processed_files,
                "matches": total_matches,
                "changed_files": len(changed_files),
                "errors": error_count,
            },
        )

    if error_count and not processed_files:
        status = OperationStatus.FAILED
    elif error_count or total_matches == 0:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS

    action = "Replaced" if apply else "Found"
    summary = f"{action} {total_matches} occurrence(s) across {processed_files} file(s)"

    return OperationResult(
        status=status,
        summary=summary,
        diagnostics=diagnostics,
        changed_files=changed_files,
        metrics={
            "files": processed_files,
            "matches": total_matches,
            "changed_files": len(changed_files),
            "errors": error_count,
        },
    )


def _discover_targets(
    request: ReplaceFeatureRequest,
) -> tuple[list[ReplacementTarget], str | None]:
    if request.mode is ReplaceMode.SINGLE:
        if not request.target.is_dir():
            return [], "Single mode requires an objective folder."

        folder_name = request.target.name
        if not folder_name.upper().startswith("OCD_"):
            return [], "Objective folder name must start with OCD_."

        suffix = folder_name[4:]
        fed_path = request.target / f"FED_{suffix}.xml"
        if not fed_path.is_file():
            return [], f"Expected FED file was not found: {fed_path.name}"

        return [ReplacementTarget(folder_name, fed_path)], None

    if not request.target.is_file():
        return [], "Batch mode requires a Class Table XML file."

    objective_data = request.target.parent / "ObjectiveRelatedData"
    if not objective_data.is_dir():
        return [], "ObjectiveRelatedData directory was not found beside the Class Table."

    targets: list[ReplacementTarget] = []
    for folder in sorted(objective_data.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or not folder.name.upper().startswith("OCD_"):
            continue
        suffix = folder.name[4:]
        fed_path = folder / f"FED_{suffix}.xml"
        if fed_path.is_file():
            targets.append(ReplacementTarget(folder.name, fed_path))
    return targets, None


def _matching_feature_elements(
    root: ET.Element,
    old_feature_number: str,
) -> list[ET.Element]:
    matches: list[ET.Element] = []
    for fed in root.findall("FED"):
        feature = fed.find("FeatureCtIdx")
        if feature is not None and (feature.text or "").strip() == old_feature_number:
            matches.append(feature)
    return matches


def _atomic_write_xml(content: bytes, destination: Path) -> None:
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

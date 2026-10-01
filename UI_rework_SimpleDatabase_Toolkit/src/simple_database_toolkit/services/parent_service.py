"""Parent.dat validation, reference checks, and normalization."""

from __future__ import annotations

import os
import shutil
import tempfile
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


class ParentMode(str, Enum):
    SINGLE = "single"
    BATCH = "batch"


@dataclass(frozen=True, slots=True)
class ParentRequest:
    target: Path
    mode: ParentMode = ParentMode.SINGLE
    convert_lod_to_bml: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", Path(self.target))


def check_parent_fields(
    request: ParentRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    targets, error = _discover_parent_files(request)
    if error is not None:
        report(DiagnosticSeverity.ERROR, error, request.target)
        return _invalid_target_result(error, diagnostics)

    checked = 0
    valid = 0
    issue_count = 0
    read_errors = 0
    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                content = target.read_text(encoding="utf-8-sig")
                issues = validate_parent_content(content)
                checked += 1
                if issues:
                    issue_count += len(issues)
                    for issue in issues:
                        report(DiagnosticSeverity.ERROR, issue, target)
                else:
                    valid += 1
                    report(
                        DiagnosticSeverity.SUCCESS,
                        "All required Parent.dat fields are valid.",
                        target,
                    )
            except OSError as exc:
                read_errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not read Parent.dat: {exc}",
                    target,
                )
            _progress(context, index, len(targets), target)
    except OperationCancelled:
        return _cancelled_result(
            "Parent field check cancelled",
            diagnostics,
            {
                "files": checked,
                "valid": valid,
                "issues": issue_count,
                "errors": read_errors,
            },
        )

    status = _inspection_status(checked, issue_count + read_errors)
    return OperationResult(
        status=status,
        summary=(
            f"Checked {checked} Parent.dat file(s); "
            f"{valid} valid, {issue_count + read_errors} issue(s)"
        ),
        diagnostics=diagnostics,
        metrics={
            "files": checked,
            "valid": valid,
            "issues": issue_count,
            "errors": read_errors,
        },
    )


def check_parent_bml_files(
    request: ParentRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    targets, error = _discover_parent_files(request)
    if error is not None:
        report(DiagnosticSeverity.ERROR, error, request.target)
        return _invalid_target_result(error, diagnostics)

    checked = 0
    clean = 0
    missing_count = 0
    extra_count = 0
    malformed_count = 0
    read_errors = 0
    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                content = target.read_text(encoding="utf-8-sig")
                references, malformed = _addlod_references(content)
                actual = {
                    path.name.casefold(): path.name
                    for path in target.parent.iterdir()
                    if path.is_file() and path.suffix.casefold() == ".bml"
                }
                missing = sorted(set(references) - set(actual))
                extra = sorted(set(actual) - set(references))
                checked += 1
                missing_count += len(missing)
                extra_count += len(extra)
                malformed_count += len(malformed)

                for issue in malformed:
                    report(DiagnosticSeverity.ERROR, issue, target)
                for name in missing:
                    report(
                        DiagnosticSeverity.ERROR,
                        f"Referenced model is missing: {references[name]}",
                        target.parent,
                    )
                for name in extra:
                    report(
                        DiagnosticSeverity.WARNING,
                        f"BML file is not referenced: {actual[name]}",
                        target.parent,
                    )
                if not malformed and not missing and not extra:
                    clean += 1
                    report(
                        DiagnosticSeverity.SUCCESS,
                        "All BML files are referenced correctly.",
                        target,
                    )
            except OSError as exc:
                read_errors += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not check BML references: {exc}",
                    target,
                )
            _progress(context, index, len(targets), target)
    except OperationCancelled:
        return _cancelled_result(
            "BML reference check cancelled",
            diagnostics,
            {
                "files": checked,
                "clean": clean,
                "missing": missing_count,
                "unreferenced": extra_count,
                "errors": malformed_count + read_errors,
            },
        )

    issue_count = (
        missing_count + extra_count + malformed_count + read_errors
    )
    status = _inspection_status(checked, issue_count)
    return OperationResult(
        status=status,
        summary=(
            f"Checked {checked} model folder(s); "
            f"{missing_count} missing and {extra_count} unreferenced BML file(s)"
        ),
        diagnostics=diagnostics,
        metrics={
            "files": checked,
            "clean": clean,
            "missing": missing_count,
            "unreferenced": extra_count,
            "errors": malformed_count + read_errors,
        },
    )


def reformat_parents(
    request: ParentRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    targets, error = _discover_parent_files(request)
    if error is not None:
        report(DiagnosticSeverity.ERROR, error, request.target)
        return _invalid_target_result(error, diagnostics)

    processed = 0
    changed = 0
    converted = 0
    error_count = 0
    changed_files: list[Path] = []
    try:
        for index, target in enumerate(targets, start=1):
            context.check_cancelled()
            try:
                original = target.read_text(encoding="utf-8-sig")
                formatted = format_parent_content(
                    original,
                    convert_lod_to_bml=request.convert_lod_to_bml,
                )
                converted_in_file = _lod_conversion_count(original)
                if not request.convert_lod_to_bml:
                    converted_in_file = 0

                if formatted != original:
                    context.backup_files(
                        [target],
                        request.target if request.target.is_dir() else request.target.parent,
                    )
                    _atomic_write_text(target, formatted)
                    changed += 1
                    changed_files.append(target)
                    report(
                        DiagnosticSeverity.SUCCESS,
                        "Parent.dat rebuilt and formatted.",
                        target,
                    )
                else:
                    report(
                        DiagnosticSeverity.INFO,
                        "Parent.dat is already normalized.",
                        target,
                    )
                processed += 1
                converted += converted_in_file
            except (OSError, ValueError) as exc:
                error_count += 1
                report(
                    DiagnosticSeverity.ERROR,
                    f"Could not reformat Parent.dat: {exc}",
                    target,
                )
            _progress(context, index, len(targets), target)
    except OperationCancelled:
        return _cancelled_result(
            "Parent reformat cancelled at a safe file boundary",
            diagnostics,
            {
                "files": processed,
                "changed": changed,
                "converted": converted,
                "errors": error_count,
            },
            changed_files,
        )

    if error_count and not processed:
        status = OperationStatus.FAILED
    elif error_count:
        status = OperationStatus.WARNING
    else:
        status = OperationStatus.SUCCESS
    return OperationResult(
        status=status,
        summary=(
            f"Reformatted {changed} of {processed} Parent.dat file(s)"
        ),
        diagnostics=diagnostics,
        changed_files=changed_files,
        metrics={
            "files": processed,
            "changed": changed,
            "converted": converted,
            "errors": error_count,
        },
    )


def validate_parent_content(content: str) -> list[str]:
    issues: list[str] = []
    found = {
        "Dimensions": False,
        "TextureSets": False,
        "Switches": False,
        "Dofs": False,
    }

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            issues.append(f"Line {line_number}: expected 'key = value'.")
            continue

        key, value = (part.strip() for part in line.split("=", 1))
        if key in found:
            found[key] = True

        if key == "Dimensions":
            values = value.split()
            if len(values) != 7:
                issues.append(
                    f"Line {line_number}: Dimensions requires 7 values; "
                    f"found {len(values)}."
                )
            else:
                _validate_float_values(
                    values,
                    issues,
                    line_number,
                    "Dimensions",
                )
        elif key == "TextureSets":
            try:
                number = int(value)
                if number < 0:
                    raise ValueError
            except ValueError:
                issues.append(
                    f"Line {line_number}: TextureSets must be an integer "
                    f">= 0; found '{value}'."
                )
        elif key in {"Switches", "Dofs"}:
            try:
                number = int(value)
                if number < 0:
                    raise ValueError
            except ValueError:
                issues.append(
                    f"Line {line_number}: {key} must be an integer >= 0; "
                    f"found '{value}'."
                )
        elif key == "AddLOD":
            parts = value.split()
            if len(parts) != 2:
                issues.append(
                    f"Line {line_number}: AddLOD requires "
                    "'filename distance'."
                )
            else:
                try:
                    if float(parts[1]) < 0:
                        raise ValueError
                except ValueError:
                    issues.append(
                        f"Line {line_number}: AddLOD distance must be "
                        f"a number >= 0; found '{parts[1]}'."
                    )
        elif key == "AddSlot":
            values = value.split()
            if not values:
                issues.append(
                    f"Line {line_number}: AddSlot requires numeric values."
                )
            else:
                _validate_float_values(
                    [item.lstrip("+") for item in values],
                    issues,
                    line_number,
                    "AddSlot",
                )

    for key, was_found in found.items():
        if not was_found:
            issues.append(f"Missing required field: {key}.")
    return issues


def format_parent_content(
    content: str,
    *,
    convert_lod_to_bml: bool = False,
) -> str:
    formatted_lines: list[str] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or "=" not in line:
            formatted_lines.append(raw_line.rstrip())
            continue

        key, value = (part.strip() for part in line.split("=", 1))
        if key == "Dimensions":
            values = _parse_float_values(
                value.split(),
                line_number,
                "Dimensions",
                expected=7,
            )
            formatted_lines.append(
                f"{key:<16} = {_format_numbers(values)}"
            )
        elif key in {"TextureSets", "Switches", "Dofs"}:
            formatted_lines.append(f"{key:<16} = {value}")
        elif key == "AddLOD":
            parts = value.split()
            if len(parts) != 2:
                raise ValueError(
                    f"Line {line_number}: AddLOD requires "
                    "'filename distance'."
                )
            model, distance_text = parts
            distance = float(distance_text)
            if convert_lod_to_bml and model.casefold().endswith(".lod"):
                model = f"{model[:-4]}.bml"
            formatted_lines.append(
                f"{key:<16} = {model} {distance:.0f}"
            )
        elif key == "AddSlot":
            values = _parse_float_values(
                [item.lstrip("+") for item in value.split()],
                line_number,
                "AddSlot",
            )
            formatted_lines.append(
                f"{key:<16} = {_format_numbers(values)}"
            )
        else:
            formatted_lines.append(raw_line.rstrip())
    return "\n".join(formatted_lines) + "\n"


def _discover_parent_files(
    request: ParentRequest,
) -> tuple[list[Path], str | None]:
    if request.mode is ParentMode.SINGLE:
        target = request.target
        if target.is_dir():
            match = _parent_in_directory(target)
            if match is None:
                return [], "Parent.dat was not found in the selected folder."
            return [match], None
        if not target.is_file():
            return [], "The selected Parent.dat file does not exist."
        if target.name.casefold() != "parent.dat":
            return [], "Single mode requires a Parent.dat file."
        return [target], None

    if not request.target.is_dir():
        return [], "Batch mode requires a directory."
    targets: list[Path] = []
    for root, directory_names, _file_names in os.walk(request.target):
        directory_names.sort(key=str.casefold)
        match = _parent_in_directory(Path(root))
        if match is not None:
            targets.append(match)
    targets.sort(key=lambda path: str(path).casefold())
    if not targets:
        return [], "No Parent.dat files were found in the selected directory."
    return targets, None


def _parent_in_directory(directory: Path) -> Path | None:
    try:
        matches = sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and path.name.casefold() == "parent.dat"
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError:
        return None
    return matches[0] if matches else None


def _addlod_references(
    content: str,
) -> tuple[dict[str, str], list[str]]:
    references: dict[str, str] = {}
    malformed: list[str] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.casefold().startswith("addlod"):
            continue
        if "=" not in line:
            malformed.append(
                f"Line {line_number}: malformed AddLOD entry."
            )
            continue
        value = line.split("=", 1)[1].strip()
        parts = value.split()
        if len(parts) != 2:
            malformed.append(
                f"Line {line_number}: AddLOD requires 'filename distance'."
            )
            continue
        references[parts[0].casefold()] = parts[0]
    return references, malformed


def _parse_float_values(
    values: list[str],
    line_number: int,
    field: str,
    *,
    expected: int | None = None,
) -> list[float]:
    if expected is not None and len(values) != expected:
        raise ValueError(
            f"Line {line_number}: {field} requires {expected} values; "
            f"found {len(values)}."
        )
    if not values:
        raise ValueError(f"Line {line_number}: {field} has no values.")
    try:
        return [float(value) for value in values]
    except ValueError as exc:
        raise ValueError(
            f"Line {line_number}: {field} contains a non-numeric value."
        ) from exc


def _validate_float_values(
    values: list[str],
    issues: list[str],
    line_number: int,
    field: str,
) -> None:
    for index, value in enumerate(values):
        try:
            float(value)
        except ValueError:
            issues.append(
                f"Line {line_number}: {field}[{index}] '{value}' "
                "is not numeric."
            )


def _format_numbers(values: list[float]) -> str:
    return " ".join(f"{value:.10g}" for value in values)


def _lod_conversion_count(content: str) -> int:
    references, _malformed = _addlod_references(content)
    return sum(name.casefold().endswith(".lod") for name in references.values())


def _atomic_write_text(destination: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
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


def _reporter(
    context: OperationContext,
    diagnostics: list[DiagnosticEvent],
):
    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Reformat Parents",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    return report


def _progress(
    context: OperationContext,
    current: int,
    total: int,
    target: Path,
) -> None:
    context.report_progress(
        ProgressUpdate(
            current=current,
            total=total,
            message=f"Processed {target.parent.name}",
        )
    )


def _inspection_status(
    processed: int,
    issue_count: int,
) -> OperationStatus:
    if not processed:
        return OperationStatus.FAILED
    if issue_count:
        return OperationStatus.WARNING
    return OperationStatus.SUCCESS


def _invalid_target_result(
    message: str,
    diagnostics: list[DiagnosticEvent],
) -> OperationResult:
    return OperationResult(
        status=OperationStatus.FAILED,
        summary=message,
        diagnostics=diagnostics,
        metrics={"files": 0, "errors": 1},
    )


def _cancelled_result(
    summary: str,
    diagnostics: list[DiagnosticEvent],
    metrics: dict[str, int],
    changed_files: list[Path] | None = None,
) -> OperationResult:
    return OperationResult(
        status=OperationStatus.CANCELLED,
        summary=summary,
        diagnostics=diagnostics,
        changed_files=changed_files or [],
        metrics=metrics,
    )

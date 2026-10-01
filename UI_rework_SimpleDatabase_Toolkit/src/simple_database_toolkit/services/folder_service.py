"""Numbered folder creation service extracted from the legacy UI."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
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


PARENT_DAT_CONTENT = """Dimensions       = 0 0 0 0 0 0 0
TextureSets      = 1
Switches         = 0
Dofs             = 0
"""


@dataclass(frozen=True, slots=True)
class FolderCreateRequest:
    directory: Path
    start: int
    end: int
    include_parent_dat: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "directory", Path(self.directory))

    @property
    def count(self) -> int:
        return max(0, self.end - self.start + 1)


def create_folders(
    request: FolderCreateRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    """Create a complete numbered range or leave the target unchanged.

    All conflicts are detected before creation begins. If creation fails or is
    cancelled, only directories created by this operation are removed.
    """

    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    created_directories: list[Path] = []
    changed_paths: list[Path] = []

    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Folder Creator",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    def failed(summary: str) -> OperationResult:
        return OperationResult(
            status=OperationStatus.FAILED,
            summary=summary,
            diagnostics=diagnostics,
            metrics={"requested": request.count, "created": 0},
        )

    if request.start < 0:
        report(DiagnosticSeverity.ERROR, "Start number cannot be negative.")
        return failed("Invalid folder range")

    if request.end < request.start:
        report(
            DiagnosticSeverity.ERROR,
            "End number must be greater than or equal to the start number.",
        )
        return failed("Invalid folder range")

    if not request.directory.exists():
        report(
            DiagnosticSeverity.ERROR,
            "Target directory does not exist.",
            request.directory,
        )
        return failed("Target directory not found")

    if not request.directory.is_dir():
        report(
            DiagnosticSeverity.ERROR,
            "Selected target is not a directory.",
            request.directory,
        )
        return failed("Invalid target directory")

    targets = [
        request.directory / str(number)
        for number in range(request.start, request.end + 1)
    ]
    conflicts = [path for path in targets if path.exists()]

    if conflicts:
        for path in conflicts[:10]:
            report(
                DiagnosticSeverity.ERROR,
                "A file or folder with this name already exists.",
                path,
            )
        if len(conflicts) > 10:
            report(
                DiagnosticSeverity.ERROR,
                f"{len(conflicts) - 10} additional conflicts were omitted.",
            )
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Folder creation stopped during preflight",
            diagnostics=diagnostics,
            metrics={
                "requested": request.count,
                "created": 0,
                "conflicts": len(conflicts),
            },
        )

    try:
        for index, path in enumerate(targets, start=1):
            context.check_cancelled()
            path.mkdir()
            created_directories.append(path)
            changed_paths.append(path)

            if request.include_parent_dat:
                parent_path = path / "Parent.dat"
                parent_path.write_text(PARENT_DAT_CONTENT, encoding="utf-8")
                changed_paths.append(parent_path)

            report(DiagnosticSeverity.SUCCESS, "Created folder.", path)
            context.report_progress(
                ProgressUpdate(
                    current=index,
                    total=len(targets),
                    message=f"Created {path.name}",
                )
            )

    except OperationCancelled:
        _remove_created_directories(created_directories)
        report(
            DiagnosticSeverity.WARNING,
            "Operation cancelled; newly created folders were removed.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Folder creation cancelled",
            diagnostics=diagnostics,
            metrics={"requested": request.count, "created": 0},
        )
    except Exception as exc:
        _remove_created_directories(created_directories)
        report(
            DiagnosticSeverity.ERROR,
            f"Creation failed and changes were rolled back: {exc}",
        )
        return OperationResult(
            status=OperationStatus.FAILED,
            summary="Folder creation failed",
            diagnostics=diagnostics,
            metrics={"requested": request.count, "created": 0},
        )

    summary = (
        f"Created {len(created_directories)} folder"
        f"{'' if len(created_directories) == 1 else 's'}"
    )
    if request.include_parent_dat:
        summary += " with Parent.dat files"

    return OperationResult(
        status=OperationStatus.SUCCESS,
        summary=summary,
        diagnostics=diagnostics,
        changed_files=changed_paths,
        metrics={
            "requested": request.count,
            "created": len(created_directories),
            "parent_files": (
                len(created_directories) if request.include_parent_dat else 0
            ),
        },
    )


def _remove_created_directories(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            shutil.rmtree(path)
        except OSError:
            # The original error is more useful to the caller. A future
            # transactional writer will record rollback failures separately.
            pass

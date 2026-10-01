"""Cancellation and progress primitives shared by services and workers."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable
from pathlib import Path

from .backups import BackupSession, default_backup_root
from .result import DiagnosticEvent, DiagnosticSeverity, OperationResult


class OperationCancelled(RuntimeError):
    """Raised when a cooperative operation receives a cancellation request."""


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise OperationCancelled("Operation cancelled by the user.")


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    current: int
    total: int
    message: str = ""

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(100, round(self.current * 100 / self.total)))


class OperationContext:
    """Service-facing context with no Qt dependency."""

    def __init__(
        self,
        *,
        cancellation: CancellationToken | None = None,
        on_progress: Callable[[ProgressUpdate], None] | None = None,
        on_diagnostic: Callable[[DiagnosticEvent], None] | None = None,
        backup_enabled: bool | None = None,
        backup_root: Path | None = None,
        backup_label: str = "Edit",
    ) -> None:
        self.cancellation = cancellation or CancellationToken()
        self._on_progress = on_progress
        self._on_diagnostic = on_diagnostic
        self.backup_enabled = backup_enabled
        self.backup_root = backup_root or default_backup_root()
        self.backup_label = backup_label
        self.backup_session: BackupSession | None = None
        self._backup_skipped_reported = False

    def check_cancelled(self) -> None:
        self.cancellation.raise_if_cancelled()

    def report_progress(self, update: ProgressUpdate) -> None:
        if self._on_progress is not None:
            self._on_progress(update)

    def report_diagnostic(self, event: DiagnosticEvent) -> None:
        if self._on_diagnostic is not None:
            self._on_diagnostic(event)

    def backup_files(self, paths: list[Path] | tuple[Path, ...], scope: Path) -> None:
        existing = [Path(path) for path in paths if Path(path).exists()]
        if not existing:
            return
        if self.backup_enabled is None:
            return
        if not self.backup_enabled:
            if not self._backup_skipped_reported:
                self.report_diagnostic(DiagnosticEvent(
                    DiagnosticSeverity.INFO, "Backup", "Backup skipped by user choice."
                ))
                self._backup_skipped_reported = True
            return
        if self.backup_session is None:
            self.backup_session = BackupSession(
                self.backup_root, self.backup_label, scope
            )
        before = self.backup_session.count
        self.backup_session.capture(existing)
        captured = self.backup_session.count - before
        if captured:
            self.report_diagnostic(DiagnosticEvent(
                DiagnosticSeverity.SUCCESS, "Backup",
                f"Backed up {captured} original file(s) before edit. "
                f"Snapshot: {self.backup_session.folder}",
            ))

    def finish_backup(self, result: OperationResult) -> OperationResult:
        session = self.backup_session
        if session is not None:
            result.metrics["backup_path"] = str(session.folder)
            result.metrics["backup_count"] = session.count
            try:
                session.finish(result.status.value)
            except OSError as exc:
                warning = DiagnosticEvent(
                    DiagnosticSeverity.WARNING, "Backup",
                    f"Snapshot files exist, but the manifest could not be finalized: {exc}",
                )
                result.diagnostics.append(warning)
                self.report_diagnostic(warning)
            event = DiagnosticEvent(
                DiagnosticSeverity.INFO, "Backup",
                f"Backup snapshot: {session.folder} ({session.count} original file(s)).",
            )
            result.diagnostics.append(event)
            self.report_diagnostic(event)
        return result

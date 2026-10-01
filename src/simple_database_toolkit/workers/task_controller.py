"""Lifecycle controller for one active background task."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal

from .task_worker import TaskOperation, TaskWorker


class TaskController(QObject):
    started = Signal(str)
    progress = Signal(object)
    diagnostic = Signal(object)
    completed = Signal(object)
    cancelled = Signal()
    failed = Signal(str, str)
    finished = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._worker: TaskWorker | None = None
        self.start_guard: Callable[[], bool] | None = None
        self.backup_enabled: bool | None = None
        self.backup_root: Path | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None

    def start(self, label: str, operation: TaskOperation) -> bool:
        if self._worker is not None or (
            self.start_guard is not None and not self.start_guard()
        ):
            return False

        worker = TaskWorker(
            operation,
            backup_enabled=self.backup_enabled,
            backup_root=self.backup_root,
            backup_label=label.split()[0].title(),
        )
        worker.signals.progress.connect(self.progress)
        worker.signals.diagnostic.connect(self.diagnostic)
        worker.signals.completed.connect(self.completed)
        worker.signals.cancelled.connect(self.cancelled)
        worker.signals.failed.connect(self.failed)
        worker.signals.finished.connect(self._on_finished)
        self._worker = worker

        self.started.emit(label)
        self._thread_pool.start(worker)
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_finished(self) -> None:
        self._worker = None
        self.finished.emit()

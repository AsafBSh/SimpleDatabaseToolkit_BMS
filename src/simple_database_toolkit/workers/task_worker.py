"""Generic QRunnable adapter for framework-neutral services."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeAlias

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationCancelled,
    OperationContext,
)


TaskOperation: TypeAlias = Callable[[OperationContext], Any]


class TaskWorkerSignals(QObject):
    progress = Signal(object)
    diagnostic = Signal(object)
    completed = Signal(object)
    cancelled = Signal()
    failed = Signal(str, str)
    finished = Signal()


class TaskWorker(QRunnable):
    def __init__(self, operation: TaskOperation, *, backup_enabled: bool | None = None,
                 backup_root: Path | None = None, backup_label: str = "Edit") -> None:
        super().__init__()
        self.operation = operation
        self.signals = TaskWorkerSignals()
        self.cancellation = CancellationToken()
        self.backup_enabled = backup_enabled
        self.backup_root = backup_root
        self.backup_label = backup_label
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self.cancellation.cancel()

    @Slot()
    def run(self) -> None:
        context = OperationContext(
            cancellation=self.cancellation,
            on_progress=self.signals.progress.emit,
            on_diagnostic=self.signals.diagnostic.emit,
            backup_enabled=self.backup_enabled,
            backup_root=self.backup_root,
            backup_label=self.backup_label,
        )
        try:
            result = self.operation(context)
            result = context.finish_backup(result)
        except OperationCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:
            self.signals.failed.emit(str(exc), traceback.format_exc())
        else:
            self.signals.completed.emit(result)
        finally:
            self.signals.finished.emit()

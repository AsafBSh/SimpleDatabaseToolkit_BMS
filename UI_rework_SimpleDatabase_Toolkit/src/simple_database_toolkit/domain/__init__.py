"""Framework-neutral domain models used by services and the UI."""

from .progress import CancellationToken, OperationCancelled, OperationContext, ProgressUpdate
from .result import DiagnosticEvent, DiagnosticSeverity, OperationResult, OperationStatus

__all__ = [
    "CancellationToken",
    "DiagnosticEvent",
    "DiagnosticSeverity",
    "OperationCancelled",
    "OperationContext",
    "OperationResult",
    "OperationStatus",
    "ProgressUpdate",
]

"""Structured operation results independent of any UI framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class OperationStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    severity: DiagnosticSeverity
    module: str
    message: str
    target: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(slots=True)
class OperationResult:
    status: OperationStatus
    summary: str
    diagnostics: list[DiagnosticEvent] = field(default_factory=list)
    changed_files: list[Path] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status in (OperationStatus.SUCCESS, OperationStatus.WARNING)

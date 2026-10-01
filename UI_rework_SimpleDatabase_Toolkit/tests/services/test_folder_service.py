from __future__ import annotations

from pathlib import Path

import pytest

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationContext,
    OperationStatus,
)
from simple_database_toolkit.services.folder_service import (
    PARENT_DAT_CONTENT,
    FolderCreateRequest,
    create_folders,
)


def test_creates_complete_numbered_range(tmp_path: Path) -> None:
    progress = []
    context = OperationContext(on_progress=progress.append)
    request = FolderCreateRequest(tmp_path, start=3, end=5)

    result = create_folders(request, context)

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics == {
        "requested": 3,
        "created": 3,
        "parent_files": 0,
    }
    assert [path.name for path in tmp_path.iterdir()] == ["3", "4", "5"]
    assert [update.percent for update in progress] == [33, 67, 100]


def test_optionally_creates_parent_dat_files(tmp_path: Path) -> None:
    request = FolderCreateRequest(
        tmp_path,
        start=10,
        end=11,
        include_parent_dat=True,
    )

    result = create_folders(request)

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["parent_files"] == 2
    for number in (10, 11):
        parent_file = tmp_path / str(number) / "Parent.dat"
        assert parent_file.read_text(encoding="utf-8") == PARENT_DAT_CONTENT


def test_preflight_conflict_leaves_range_unchanged(tmp_path: Path) -> None:
    conflict = tmp_path / "2"
    conflict.mkdir()
    marker = conflict / "existing.txt"
    marker.write_text("keep", encoding="utf-8")

    result = create_folders(FolderCreateRequest(tmp_path, 1, 3))

    assert result.status is OperationStatus.FAILED
    assert result.metrics["created"] == 0
    assert not (tmp_path / "1").exists()
    assert not (tmp_path / "3").exists()
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (-1, 2),
        (5, 4),
    ],
)
def test_rejects_invalid_ranges(
    tmp_path: Path,
    start: int,
    end: int,
) -> None:
    result = create_folders(FolderCreateRequest(tmp_path, start, end))

    assert result.status is OperationStatus.FAILED
    assert list(tmp_path.iterdir()) == []


def test_pre_cancelled_operation_creates_nothing(tmp_path: Path) -> None:
    cancellation = CancellationToken()
    cancellation.cancel()
    context = OperationContext(cancellation=cancellation)

    result = create_folders(
        FolderCreateRequest(tmp_path, 1, 3),
        context,
    )

    assert result.status is OperationStatus.CANCELLED
    assert list(tmp_path.iterdir()) == []

from __future__ import annotations

from pathlib import Path

import pytest

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationContext,
    OperationStatus,
)
from simple_database_toolkit.services import parent_service
from simple_database_toolkit.services.parent_service import (
    ParentMode,
    ParentRequest,
    check_parent_bml_files,
    check_parent_fields,
    format_parent_content,
    reformat_parents,
    validate_parent_content,
)


VALID_PARENT = """Dimensions       = 1 2 3 4 5 6 7
TextureSets      = 1
Switches         = 0
Dofs             = 2
AddLOD           = model.bml 1000
AddSlot          = 1 2 3
"""


def test_validates_complete_parent_content() -> None:
    assert validate_parent_content(VALID_PARENT) == []


def test_reports_invalid_and_missing_fields() -> None:
    issues = validate_parent_content(
        """Dimensions = 1 2 bad
TextureSets = -1
Switches = -1
AddLOD = model.bml nope
AddSlot = +1 bad
"""
    )

    assert any("Dimensions requires 7 values" in issue for issue in issues)
    assert any("TextureSets must be an integer >= 0" in issue for issue in issues)
    assert any("Switches must be an integer >= 0" in issue for issue in issues)
    assert any("AddLOD distance" in issue for issue in issues)
    assert any("AddSlot[1]" in issue for issue in issues)
    assert "Missing required field: Dofs." in issues


def test_accepts_multiple_texture_sets_used_by_bml_models() -> None:
    content = VALID_PARENT.replace("TextureSets      = 1", "TextureSets = 4")

    assert validate_parent_content(content) == []


def test_formats_values_and_optionally_converts_lod_names() -> None:
    content = """# retained comment
Dimensions = 1.0000 2.50 3 4 5 6 7
TextureSets=1
Switches = 0
Dofs = 0
AddLOD = model.lod 1000.4
AddSlot = +1.500 +2.0 -3
Custom = unchanged
"""

    formatted = format_parent_content(
        content,
        convert_lod_to_bml=True,
    )

    assert "# retained comment\n" in formatted
    assert "Dimensions       = 1 2.5 3 4 5 6 7\n" in formatted
    assert "AddLOD           = model.bml 1000\n" in formatted
    assert "AddSlot          = 1.5 2 -3\n" in formatted
    assert "Custom = unchanged\n" in formatted
    assert formatted.endswith("\n")


def test_field_check_is_read_only_and_reports_success(tmp_path: Path) -> None:
    parent = tmp_path / "Parent.dat"
    parent.write_text(VALID_PARENT, encoding="utf-8")
    before = parent.read_bytes()

    result = check_parent_fields(ParentRequest(parent))

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["files"] == 1
    assert result.metrics["valid"] == 1
    assert parent.read_bytes() == before


def test_batch_field_check_finds_case_insensitive_names(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two" / "nested"
    first.mkdir()
    second.mkdir(parents=True)
    (first / "parent.dat").write_text(VALID_PARENT, encoding="utf-8")
    (second / "PARENT.DAT").write_text(VALID_PARENT, encoding="utf-8")
    progress = []

    result = check_parent_fields(
        ParentRequest(tmp_path, mode=ParentMode.BATCH),
        OperationContext(on_progress=progress.append),
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["files"] == 2
    assert [update.percent for update in progress] == [50, 100]


def test_bml_check_accepts_case_insensitive_file_names(
    tmp_path: Path,
) -> None:
    (tmp_path / "Parent.dat").write_text(
        VALID_PARENT,
        encoding="utf-8",
    )
    (tmp_path / "MODEL.BML").write_bytes(b"model")

    result = check_parent_bml_files(
        ParentRequest(tmp_path / "Parent.dat")
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["clean"] == 1
    assert result.metrics["missing"] == 0
    assert result.metrics["unreferenced"] == 0


def test_bml_check_reports_missing_and_unreferenced_files(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "Parent.dat"
    parent.write_text(
        VALID_PARENT.replace("model.bml", "missing.bml"),
        encoding="utf-8",
    )
    (tmp_path / "extra.bml").write_bytes(b"extra")

    result = check_parent_bml_files(ParentRequest(parent))

    assert result.status is OperationStatus.WARNING
    assert result.metrics["missing"] == 1
    assert result.metrics["unreferenced"] == 1
    messages = [event.message for event in result.diagnostics]
    assert any("missing.bml" in message for message in messages)
    assert any("extra.bml" in message for message in messages)


def test_reformats_single_parent_atomically(tmp_path: Path) -> None:
    parent = tmp_path / "Parent.dat"
    parent.write_text(
        VALID_PARENT.replace("model.bml 1000", "model.lod 1000.2"),
        encoding="utf-8",
    )

    result = reformat_parents(
        ParentRequest(parent, convert_lod_to_bml=True)
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["changed"] == 1
    assert result.metrics["converted"] == 1
    assert "model.bml 1000" in parent.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.tmp"))


def test_write_failure_keeps_original_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "Parent.dat"
    original = VALID_PARENT.replace("Dimensions       =", "Dimensions=")
    parent.write_text(original, encoding="utf-8")

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(parent_service.os, "replace", fail_replace)
    result = reformat_parents(ParentRequest(parent))

    assert result.status is OperationStatus.FAILED
    assert parent.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp"))


def test_batch_reformat_continues_after_malformed_file(
    tmp_path: Path,
) -> None:
    good_folder = tmp_path / "good"
    bad_folder = tmp_path / "bad"
    good_folder.mkdir()
    bad_folder.mkdir()
    good = good_folder / "Parent.dat"
    bad = bad_folder / "Parent.dat"
    good.write_text(
        VALID_PARENT.replace("Dimensions       =", "Dimensions="),
        encoding="utf-8",
    )
    bad.write_text(
        VALID_PARENT.replace(
            "Dimensions       = 1 2 3 4 5 6 7",
            "Dimensions = 1 2",
        ),
        encoding="utf-8",
    )
    bad_before = bad.read_text(encoding="utf-8")

    result = reformat_parents(
        ParentRequest(tmp_path, mode=ParentMode.BATCH)
    )

    assert result.status is OperationStatus.WARNING
    assert result.metrics["files"] == 1
    assert result.metrics["changed"] == 1
    assert result.metrics["errors"] == 1
    assert bad.read_text(encoding="utf-8") == bad_before


def test_pre_cancelled_operation_writes_nothing(tmp_path: Path) -> None:
    parent = tmp_path / "Parent.dat"
    original = VALID_PARENT.replace("Dimensions       =", "Dimensions=")
    parent.write_text(original, encoding="utf-8")
    cancellation = CancellationToken()
    cancellation.cancel()

    result = reformat_parents(
        ParentRequest(parent),
        OperationContext(cancellation=cancellation),
    )

    assert result.status is OperationStatus.CANCELLED
    assert parent.read_text(encoding="utf-8") == original


def test_rejects_invalid_or_empty_targets(tmp_path: Path) -> None:
    wrong_file = tmp_path / "other.dat"
    wrong_file.write_text(VALID_PARENT, encoding="utf-8")

    single = check_parent_fields(ParentRequest(wrong_file))
    batch = check_parent_fields(
        ParentRequest(tmp_path / "missing", mode=ParentMode.BATCH)
    )

    assert single.status is OperationStatus.FAILED
    assert batch.status is OperationStatus.FAILED

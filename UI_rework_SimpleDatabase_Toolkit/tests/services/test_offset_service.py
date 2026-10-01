from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simple_database_toolkit.domain import OperationContext, OperationStatus
from simple_database_toolkit.services import (
    FeatureScanRequest,
    OffsetAdjustment,
    OffsetMode,
    OffsetOperation,
    OffsetRequest,
    apply_offset,
    scan_features,
)


def _objective(
    root: Path,
    number: str,
    entries: list[dict[str, str | int | float]],
) -> tuple[Path, Path]:
    folder = root / f"OCD_{number}"
    folder.mkdir(parents=True)

    fed_records = []
    for entry in entries:
        fields = {
            "FeatureCtIdx": entry["feature"],
            "Heading": entry.get("heading", 0),
            "OffsetX": entry.get("x", 0),
            "OffsetY": entry.get("y", 0),
            "OffsetZ": entry.get("z", 0),
            "Value": entry.get("value", 100),
        }
        body = "\n".join(
            f"    <{name}>{value}</{name}>"
            for name, value in fields.items()
        )
        fed_records.append(f"  <FED>\n{body}\n  </FED>")

    fed_path = folder / f"FED_{number}.xml"
    fed_path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<FEDRecords>\n"
        + "\n".join(fed_records)
        + "\n</FEDRecords>",
        encoding="utf-8",
    )

    ocd_path = folder / f"OCD_{number}.xml"
    ocd_path.write_text(
        f"<OCDRecords><OCD><Name>Objective {number}</Name></OCD></OCDRecords>",
        encoding="utf-8",
    )
    return folder, fed_path


def _fed_values(path: Path, index: int = 0) -> dict[str, str]:
    fed = ET.parse(path).getroot().findall("FED")[index]
    return {
        child.tag: child.text or ""
        for child in fed
    }


def test_scans_feature_counts_in_single_objective(tmp_path: Path) -> None:
    folder, _fed = _objective(
        tmp_path,
        "00001",
        [{"feature": 5}, {"feature": 7}, {"feature": 5}],
    )

    result = scan_features(FeatureScanRequest(folder))

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["files"] == 1
    assert result.metrics["unique_features"] == 2
    assert result.metrics["entries"] == 3
    assert result.metrics["features"] == {5: 2, 7: 1}


def test_scans_all_objectives_in_batch_mode(tmp_path: Path) -> None:
    class_table = tmp_path / "Falcon4_CT.xml"
    class_table.write_text("<CTRecords />", encoding="utf-8")
    objective_data = tmp_path / "ObjectiveRelatedData"
    _objective(objective_data, "00001", [{"feature": 5}])
    _objective(objective_data, "00002", [{"feature": 5}, {"feature": 9}])

    result = scan_features(
        FeatureScanRequest(class_table, mode=OffsetMode.BATCH)
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["files"] == 2
    assert result.metrics["features"] == {5: 2, 9: 1}


def test_applies_heading_relative_xy_offsets(tmp_path: Path) -> None:
    folder, fed_path = _objective(
        tmp_path,
        "00003",
        [{"feature": 15, "heading": 0, "x": 1, "y": 2}],
    )
    request = OffsetRequest(
        target=folder,
        feature_number=15,
        adjustment=OffsetAdjustment(OffsetOperation.XY, x=10, y=5),
    )

    result = apply_offset(request)

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["entries"] == 1
    values = _fed_values(fed_path)
    assert values["OffsetX"] == "6.000"
    assert values["OffsetY"] == "12.000"
    assert fed_path.read_text(encoding="utf-8").startswith(
        '<?xml version="1.0" encoding="utf-8"?>'
    )


def test_rotation_wraps_at_360_degrees(tmp_path: Path) -> None:
    folder, fed_path = _objective(
        tmp_path,
        "00004",
        [{"feature": 20, "heading": 350}],
    )

    result = apply_offset(
        OffsetRequest(
            target=folder,
            feature_number=20,
            adjustment=OffsetAdjustment(
                OffsetOperation.ROTATE,
                value=20,
            ),
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert _fed_values(fed_path)["Heading"] == "10.0"


@pytest.mark.parametrize(
    ("operation", "value", "field", "expected"),
    [
        (OffsetOperation.SET_Z, -25.125, "OffsetZ", "-25.125"),
        (OffsetOperation.SET_HEADING, 90, "Heading", "90.000"),
        (OffsetOperation.SET_VALUE, 42.9, "Value", "42"),
    ],
)
def test_set_operations_preserve_text_formatting(
    tmp_path: Path,
    operation: OffsetOperation,
    value: float,
    field: str,
    expected: str,
) -> None:
    folder, fed_path = _objective(
        tmp_path,
        "00005",
        [{"feature": 25, "heading": 3, "z": 4, "value": 5}],
    )
    original = fed_path.read_text(encoding="utf-8")

    result = apply_offset(
        OffsetRequest(
            target=folder,
            feature_number=25,
            adjustment=OffsetAdjustment(operation, value=value),
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert _fed_values(fed_path)[field] == expected
    assert fed_path.read_text(encoding="utf-8").count("\n") == original.count("\n")


def test_invalid_z_value_does_not_modify_file(tmp_path: Path) -> None:
    folder, fed_path = _objective(
        tmp_path,
        "00006",
        [{"feature": 30, "z": 12}],
    )
    original = fed_path.read_bytes()

    result = apply_offset(
        OffsetRequest(
            target=folder,
            feature_number=30,
            adjustment=OffsetAdjustment(
                OffsetOperation.SET_Z,
                value=10_001,
            ),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert fed_path.read_bytes() == original


def test_set_operation_ignores_fake_records_in_comments_and_repeat_is_noop(tmp_path: Path) -> None:
    folder, path = _objective(tmp_path, "00099", [{"feature": 25, "heading": 3}])
    fake = b"<!-- <FED><FeatureCtIdx>25</FeatureCtIdx><Heading>3</Heading></FED> -->\r\n"
    original = path.read_bytes().replace(b"<FEDRecords>", b"<FEDRecords>" + fake)
    path.write_bytes(b"\xef\xbb\xbf" + original)
    request = OffsetRequest(folder, 25, OffsetAdjustment(OffsetOperation.SET_HEADING, value=90))
    first = apply_offset(request)
    assert first.metrics["entries"] == 1
    assert fake in path.read_bytes()
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    changed = path.read_bytes()
    context = OperationContext(backup_enabled=True, backup_root=tmp_path / "backups")
    second = apply_offset(request, context)
    assert not second.changed_files
    assert context.backup_session is None
    assert path.read_bytes() == changed


@pytest.mark.parametrize("operation", [OffsetOperation.XY, OffsetOperation.SET_HEADING])
def test_offset_rejects_source_changed_before_commit(tmp_path: Path, monkeypatch, operation) -> None:
    folder, path = _objective(tmp_path, "00098", [{"feature": 25}])
    external = path.read_bytes().replace(b"<Heading>0</Heading>", b"<Heading>45</Heading>")
    context = OperationContext()
    monkeypatch.setattr(context, "backup_files", lambda *_: path.write_bytes(external))
    result = apply_offset(OffsetRequest(folder, 25, OffsetAdjustment(operation, x=1, value=90)), context)
    assert not result.changed_files
    assert result.metrics["errors"] == 1
    assert path.read_bytes() == external


def test_missing_required_xy_field_does_not_write_partial_changes(
    tmp_path: Path,
) -> None:
    folder, fed_path = _objective(
        tmp_path,
        "00007",
        [{"feature": 35, "x": 1, "y": 2}],
    )
    content = fed_path.read_text(encoding="utf-8")
    content = content.replace("    <OffsetY>2</OffsetY>\n", "")
    fed_path.write_text(content, encoding="utf-8")
    original = fed_path.read_bytes()

    result = apply_offset(
        OffsetRequest(
            target=folder,
            feature_number=35,
            adjustment=OffsetAdjustment(OffsetOperation.XY, x=1, y=1),
        )
    )

    assert result.status is OperationStatus.FAILED
    assert result.metrics["changed_files"] == 0
    assert fed_path.read_bytes() == original

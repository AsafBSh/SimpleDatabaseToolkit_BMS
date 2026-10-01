from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from simple_database_toolkit.domain import OperationContext, OperationStatus
from simple_database_toolkit.services import (
    ReplaceFeatureRequest,
    ReplaceMode,
    replace_features,
    scan_replacements,
)


def _write_fed(path: Path, values: list[int]) -> None:
    records = "".join(
        f"<FED><FeatureCtIdx>{value}</FeatureCtIdx><Value>100</Value></FED>"
        for value in values
    )
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<FEDRecords>{records}</FEDRecords>',
        encoding="utf-8",
    )


def _single_objective(
    root: Path,
    number: str,
    values: list[int],
) -> tuple[Path, Path]:
    folder = root / f"OCD_{number}"
    folder.mkdir(parents=True)
    fed_path = folder / f"FED_{number}.xml"
    _write_fed(fed_path, values)
    return folder, fed_path


def _feature_values(path: Path) -> list[str]:
    root = ET.parse(path).getroot()
    return [
        element.text or ""
        for element in root.findall("FED/FeatureCtIdx")
    ]


def test_replacement_rejects_source_changed_before_commit(tmp_path: Path, monkeypatch) -> None:
    folder, path = _single_objective(tmp_path, "00099", [10])
    external = path.read_bytes().replace(b">10<", b">20<")
    context = OperationContext()
    monkeypatch.setattr(context, "backup_files", lambda *_: path.write_bytes(external))
    result = replace_features(ReplaceFeatureRequest(folder, 10, 99), context)
    assert not result.changed_files
    assert result.metrics["errors"] == 1
    assert path.read_bytes() == external


def test_scan_counts_candidates_without_writing(tmp_path: Path) -> None:
    folder, fed_path = _single_objective(tmp_path, "00001", [10, 20, 10])
    original = fed_path.read_bytes()
    request = ReplaceFeatureRequest(folder, 10, 99)

    result = scan_replacements(request)

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["matches"] == 2
    assert result.metrics["changed_files"] == 0
    assert fed_path.read_bytes() == original


def test_replaces_all_matching_feature_numbers_atomically(
    tmp_path: Path,
) -> None:
    folder, fed_path = _single_objective(tmp_path, "00002", [10, 20, 10])

    result = replace_features(ReplaceFeatureRequest(folder, 10, 99))

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["matches"] == 2
    assert result.metrics["changed_files"] == 1
    assert _feature_values(fed_path) == ["99", "20", "99"]
    assert fed_path.read_text(encoding="utf-8").startswith(
        '<?xml version="1.0" encoding="utf-8"?>'
    )


def test_batch_mode_processes_objective_related_data(
    tmp_path: Path,
) -> None:
    class_table = tmp_path / "Falcon4_CT.xml"
    class_table.write_text("<CTRecords />", encoding="utf-8")
    objective_data = tmp_path / "ObjectiveRelatedData"
    folder_a, fed_a = _single_objective(objective_data, "00001", [4, 4])
    folder_b, fed_b = _single_objective(objective_data, "00002", [4, 7])

    result = replace_features(
        ReplaceFeatureRequest(
            class_table,
            4,
            8,
            mode=ReplaceMode.BATCH,
        )
    )

    assert folder_a.exists() and folder_b.exists()
    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["files"] == 2
    assert result.metrics["matches"] == 3
    assert _feature_values(fed_a) == ["8", "8"]
    assert _feature_values(fed_b) == ["8", "7"]


def test_missing_single_fed_file_is_reported(tmp_path: Path) -> None:
    folder = tmp_path / "OCD_00003"
    folder.mkdir()

    result = replace_features(ReplaceFeatureRequest(folder, 1, 2))

    assert result.status is OperationStatus.FAILED
    assert result.metrics["changed_files"] == 0


def test_malformed_xml_is_not_modified(tmp_path: Path) -> None:
    folder = tmp_path / "OCD_00004"
    folder.mkdir()
    fed_path = folder / "FED_00004.xml"
    malformed = b"<FEDRecords><FED><FeatureCtIdx>1</FEDRecords>"
    fed_path.write_bytes(malformed)

    result = replace_features(ReplaceFeatureRequest(folder, 1, 2))

    assert result.status is OperationStatus.FAILED
    assert result.metrics["changed_files"] == 0
    assert fed_path.read_bytes() == malformed

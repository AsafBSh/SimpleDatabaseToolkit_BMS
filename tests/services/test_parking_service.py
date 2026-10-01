from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationContext,
    OperationStatus,
)
from simple_database_toolkit.services import (
    ParkingMode,
    ParkingPreview,
    ParkingRequest,
    apply_parking,
    preview_parking,
)
from simple_database_toolkit.services import parking_service


def _class_table(
    root: Path,
    entries: list[tuple[int, int]],
) -> Path:
    path = root / "Falcon4_CT.xml"
    records = "".join(
        f'<CT Num="{number}"><Type>{feature_type}</Type></CT>'
        for number, feature_type in entries
    )
    path.write_text(
        f"<CTRecords>{records}</CTRecords>",
        encoding="utf-8",
    )
    return path


def _objective(
    root: Path,
    number: str,
    *,
    hangars: list[tuple[int, float, float]],
    parking: list[tuple[str, str, float, float]],
    name: str | None = None,
) -> tuple[Path, Path]:
    folder = root / f"OCD_{number}"
    folder.mkdir(parents=True)

    fed_records = "\n".join(
        "  <FED>"
        f"<FeatureCtIdx>{ct_number}</FeatureCtIdx>"
        f"<OffsetX>{x}</OffsetX><OffsetY>{y}</OffsetY>"
        "</FED>"
        for ct_number, x, y in hangars
    )
    (folder / f"FED_{number}.XML").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<FEDRecords>\n{fed_records}\n</FEDRecords>",
        encoding="utf-8",
    )

    pd_records = "\n".join(
        f'  <PD Num="{point_number}">\n'
        f"    <OffsetX>{x}</OffsetX>\n"
        f"    <OffsetY>{y}</OffsetY>\n"
        "    <OffsetZ>0.000</OffsetZ>\n"
        f"    <Type>{point_type}</Type>\n"
        "    <Custom>preserve me</Custom>\n"
        "  </PD>"
        for point_number, point_type, x, y in parking
    )
    pdx_path = folder / f"PDX_{number}.XML"
    pdx_path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!-- formatting must remain -->\n"
        f"<PDRecords>\n{pd_records}\n</PDRecords>",
        encoding="utf-8",
    )

    objective_name = name or f"Objective {number}"
    (folder / f"OCD_{number}.XML").write_text(
        f"<OCDRecords><OCD><Name>{objective_name}</Name></OCD></OCDRecords>",
        encoding="utf-8",
    )
    return folder, pdx_path


def _preview(result) -> ParkingPreview:
    preview = result.metrics["preview"]
    assert isinstance(preview, ParkingPreview)
    return preview


def test_preview_selects_nearest_type_45_hangar_within_radius(
    tmp_path: Path,
) -> None:
    class_table = _class_table(
        tmp_path,
        [(100, 45), (200, 45), (300, 12)],
    )
    folder, pdx_path = _objective(
        tmp_path,
        "00001",
        hangars=[(100, 3, 4), (200, 1, 1), (300, 0, 0)],
        parking=[("7", "11", 0, 0), ("8", "3", 0, 0)],
        name="Nearest Test",
    )

    result = preview_parking(
        ParkingRequest(folder, class_table, radius_feet=10)
    )
    preview = _preview(result)

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["parking_points"] == 1
    assert result.metrics["hangars"] == 2
    assert len(preview.moves) == 1
    move = preview.moves[0]
    assert move.pdx_path == pdx_path
    assert move.objective_name == "Nearest Test"
    assert move.point_number == "7"
    assert move.hangar_ct_number == 200
    assert move.distance_feet == pytest.approx(math.sqrt(2))
    assert (move.new_x, move.new_y) == (1, 1)


def test_selected_ct_numbers_filter_hangar_locations(
    tmp_path: Path,
) -> None:
    class_table = _class_table(tmp_path, [(100, 45), (200, 45)])
    folder, _ = _objective(
        tmp_path,
        "00002",
        hangars=[(100, 50, 50), (200, 2, 2)],
        parking=[("1", "12", 0, 0)],
    )

    result = preview_parking(
        ParkingRequest(
            folder,
            class_table,
            radius_feet=100,
            hangar_ct_numbers=(100,),
        )
    )

    move = _preview(result).moves[0]
    assert move.hangar_ct_number == 100
    assert (move.new_x, move.new_y) == (50, 50)
    assert result.metrics["hangars"] == 1


@pytest.mark.parametrize("selection", [(), (0,), (0, 999)])
def test_blank_or_zero_selection_uses_all_hangars(
    tmp_path: Path,
    selection: tuple[int, ...],
) -> None:
    class_table = _class_table(tmp_path, [(10, 45), (20, 45)])
    folder, _ = _objective(
        tmp_path,
        "00003",
        hangars=[(10, 8, 0), (20, 3, 0)],
        parking=[("1", "11", 0, 0)],
    )

    result = preview_parking(
        ParkingRequest(
            folder,
            class_table,
            radius_feet=10,
            hangar_ct_numbers=selection,
        )
    )

    preview = _preview(result)
    assert preview.selected_hangar_ct_numbers == (10, 20)
    assert preview.moves[0].hangar_ct_number == 20


def test_points_outside_radius_are_not_previewed(tmp_path: Path) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, _ = _objective(
        tmp_path,
        "00004",
        hangars=[(10, 20, 0)],
        parking=[("1", "11", 0, 0)],
    )

    result = preview_parking(
        ParkingRequest(folder, class_table, radius_feet=19.999)
    )

    assert result.status is OperationStatus.WARNING
    assert _preview(result).moves == ()


def test_apply_changes_only_target_coordinate_text(tmp_path: Path) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00005",
        hangars=[(10, 5.5, -2.25)],
        parking=[("1", "11", 0, 0), ("2", "3", 4, 4)],
    )
    before = pdx_path.read_text(encoding="utf-8")

    result = apply_parking(
        ParkingRequest(folder, class_table, radius_feet=10)
    )

    expected = before.replace(
        "<OffsetX>0</OffsetX>",
        "<OffsetX>5.500</OffsetX>",
        1,
    ).replace(
        "<OffsetY>0</OffsetY>",
        "<OffsetY>-2.250</OffsetY>",
        1,
    )
    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["moves"] == 1
    assert pdx_path.read_text(encoding="utf-8") == expected
    assert "<!-- formatting must remain -->" in expected
    assert "<Custom>preserve me</Custom>" in expected


def test_batch_processes_direct_objectives_and_reports_incomplete_one(
    tmp_path: Path,
) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    objective_data = tmp_path / "ObjectiveRelatedData"
    objective_data.mkdir()
    _objective(
        objective_data,
        "00002",
        hangars=[(10, 1, 0)],
        parking=[("1", "11", 0, 0)],
    )
    _objective(
        objective_data,
        "00001",
        hangars=[(10, 2, 0)],
        parking=[("1", "12", 0, 0)],
    )
    incomplete = objective_data / "OCD_00003"
    incomplete.mkdir()
    (incomplete / "PDX_00003.xml").write_text(
        "<PDRecords />",
        encoding="utf-8",
    )

    result = preview_parking(
        ParkingRequest(
            objective_data,
            class_table,
            mode=ParkingMode.BATCH,
            radius_feet=10,
        )
    )
    preview = _preview(result)

    assert result.status is OperationStatus.WARNING
    assert [item.folder.name for item in preview.objectives] == [
        "OCD_00001",
        "OCD_00002",
    ]
    assert result.metrics["objectives"] == 2
    assert result.metrics["errors"] == 1


def test_malformed_parking_coordinate_blocks_that_objective(
    tmp_path: Path,
) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00006",
        hangars=[(10, 1, 1)],
        parking=[("1", "11", 0, 0)],
    )
    malformed = pdx_path.read_text(encoding="utf-8").replace(
        "<OffsetX>0</OffsetX>",
        "<OffsetX>bad</OffsetX>",
        1,
    )
    pdx_path.write_text(malformed, encoding="utf-8")

    result = preview_parking(
        ParkingRequest(folder, class_table, radius_feet=10)
    )

    assert result.status is OperationStatus.FAILED
    assert result.metrics["objectives"] == 0
    assert pdx_path.read_text(encoding="utf-8") == malformed


@pytest.mark.parametrize("radius", [-1.0, math.inf, math.nan])
def test_invalid_radius_is_rejected(tmp_path: Path, radius: float) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, _ = _objective(
        tmp_path,
        "00007",
        hangars=[],
        parking=[],
    )

    result = preview_parking(
        ParkingRequest(folder, class_table, radius_feet=radius)
    )

    assert result.status is OperationStatus.FAILED


def test_atomic_replace_failure_keeps_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00008",
        hangars=[(10, 1, 1)],
        parking=[("1", "11", 0, 0)],
    )
    original = pdx_path.read_bytes()

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(parking_service.os, "replace", fail_replace)

    result = apply_parking(
        ParkingRequest(folder, class_table, radius_feet=10)
    )

    assert result.status is OperationStatus.FAILED
    assert pdx_path.read_bytes() == original


def test_apply_rejects_stale_preview(tmp_path: Path) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00011",
        hangars=[(10, 1, 1)],
        parking=[("1", "11", 0, 0)],
    )
    request = ParkingRequest(folder, class_table, radius_feet=10)
    preview = _preview(preview_parking(request))
    externally_changed = pdx_path.read_text(encoding="utf-8").replace(
        "<OffsetX>0</OffsetX>",
        "<OffsetX>5</OffsetX>",
        1,
    )
    pdx_path.write_text(externally_changed, encoding="utf-8")

    result = apply_parking(
        request,
        expected_preview=preview,
    )

    assert result.status is OperationStatus.FAILED
    assert pdx_path.read_text(encoding="utf-8") == externally_changed
    assert any(
        "changed after Preview" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_cancelled_apply_does_not_write(tmp_path: Path) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00009",
        hangars=[(10, 1, 1)],
        parking=[("1", "11", 0, 0)],
    )
    original = pdx_path.read_bytes()
    token = CancellationToken()
    token.cancel()

    result = apply_parking(
        ParkingRequest(folder, class_table, radius_feet=10),
        OperationContext(cancellation=token),
    )

    assert result.status is OperationStatus.CANCELLED
    assert pdx_path.read_bytes() == original


def test_applied_pdx_remains_valid_xml(tmp_path: Path) -> None:
    class_table = _class_table(tmp_path, [(10, 45)])
    folder, pdx_path = _objective(
        tmp_path,
        "00010",
        hangars=[(10, 1, 1)],
        parking=[("1", "11", 0, 0)],
    )

    result = apply_parking(
        ParkingRequest(folder, class_table, radius_feet=10)
    )

    assert result.status is OperationStatus.SUCCESS
    root = ET.parse(pdx_path).getroot()
    assert root.tag == "PDRecords"

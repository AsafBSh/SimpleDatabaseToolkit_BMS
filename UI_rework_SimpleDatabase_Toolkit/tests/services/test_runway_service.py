from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationContext,
    OperationStatus,
)
from simple_database_toolkit.services import (
    HeadingChoice,
    RunwayCheck,
    RunwayMapComparison,
    RunwayMode,
    RunwayRequest,
    build_crossing_pairs,
    build_runway_dim_boxes,
    build_runway_polygons,
    build_taxi_tree,
    calculate_runway_heading,
    check_runways,
    fix_runways,
    point_in_box,
    runway_segments_intersect,
    segment_polygon_crossings,
    walk_taxi_paths,
)
from simple_database_toolkit.services import runway_service


def _phd_xml(records: list[dict[str, object]]) -> str:
    bodies = []
    for record in records:
        number = record["num"]
        fields = [
            ("Type", record["type"]),
            ("RunwayNumber", record.get("runway", 1)),
            ("FirstPtIdx", record.get("first", 0)),
            ("PointCount", record.get("count", 0)),
            ("Data", record.get("data", "0.000")),
            ("LandingPattern", record.get("landing", 0)),
        ]
        body = "".join(
            f"<{name}>{value}</{name}>" for name, value in fields
        )
        bodies.append(f'<PHD Num="{number}">{body}</PHD>')
    return "<PHDRecords>" + "".join(bodies) + "</PHDRecords>"


def _pdx_xml(records: list[dict[str, object]]) -> str:
    bodies = []
    for record in records:
        fields = [
            ("OffsetX", record.get("x", 0)),
            ("OffsetY", record.get("y", 0)),
            ("Type", record["type"]),
        ]
        if "root" in record:
            fields.append(("RootIdx", record["root"]))
        if "cp" in record:
            fields.append(("CrossingPoint", record["cp"]))
        if "runway" in record:
            fields.append(("RunwayNumber", record["runway"]))
        if "side" in record:
            fields.append(("RunwaySide", record["side"]))
        body = "".join(
            f"<{name}>{value}</{name}>" for name, value in fields
        )
        bodies.append(f'<PD Num="{record["num"]}">{body}</PD>')
    return "<PDRecords>" + "".join(bodies) + "</PDRecords>"


def _objective(
    root: Path,
    number: str,
    phds: list[dict[str, object]],
    pds: list[dict[str, object]] | None,
) -> tuple[Path, Path, Path | None]:
    folder = root / f"OCD_{number}"
    folder.mkdir(parents=True)
    phd_path = folder / f"PHD_{number}.XML"
    phd_path.write_text(_phd_xml(phds), encoding="utf-8")
    pdx_path = None
    if pds is not None:
        pdx_path = folder / f"PDX_{number}.XML"
        pdx_path.write_text(_pdx_xml(pds), encoding="utf-8")
    (folder / f"OCD_{number}.XML").write_text(
        f"<OCDRecords><OCD><Name>Airbase {number}</Name></OCD></OCDRecords>",
        encoding="utf-8",
    )
    return folder, phd_path, pdx_path


def _dim_phd(
    number: int,
    runway: int,
    first: int,
    data: str = "0.000",
) -> dict[str, object]:
    return {
        "num": number,
        "type": 8,
        "runway": runway,
        "first": first,
        "count": 4,
        "data": data,
    }


def test_runway_rejects_source_changed_before_commit(tmp_path: Path, monkeypatch) -> None:
    folder, path, _ = _objective(tmp_path, "00099", [
        {"num": 0, "type": 1, "data": "200.000"},
        {"num": 1, "type": 1, "data": "20.000"},
        {"num": 2, "type": 8, "data": "22.000"},
    ], None)
    external = path.read_bytes().replace(b"22.000", b"45.000")
    context = OperationContext()
    monkeypatch.setattr(context, "backup_files", lambda *_: path.write_bytes(external))
    result = fix_runways(RunwayRequest(folder, checks=frozenset({RunwayCheck.DIM_HEADING})), context)
    assert not result.changed_files
    assert result.metrics["errors"] == 1
    assert path.read_bytes() == external


def _box_points(first: int, center_x: float, center_y: float):
    coordinates = [
        (center_x - 10, center_y - 10),
        (center_x + 10, center_y - 10),
        (center_x + 10, center_y + 10),
        (center_x - 10, center_y + 10),
    ]
    return [
        {"num": first + index, "type": 8, "x": x, "y": y}
        for index, (x, y) in enumerate(coordinates)
    ]


def _field(path: Path, phd_number: str, field_name: str) -> str:
    root = ET.parse(path).getroot()
    phd = next(item for item in root.findall("PHD") if item.get("Num") == phd_number)
    element = phd.find(field_name)
    assert element is not None
    return element.text or ""


def test_heading_calculation_uses_atan2_dx_dy() -> None:
    pdx_root = ET.fromstring(
        _pdx_xml(
            [
                {"num": 10, "type": 1, "x": 100, "y": 0},
                {"num": 11, "type": 2, "x": 0, "y": 0},
            ]
        )
    )
    index = {int(pd.get("Num") or ""): pd for pd in pdx_root.findall("PD")}

    assert calculate_runway_heading(index, 10, 2) == 90.0


def test_check_and_fix_runway_list_heading(tmp_path: Path) -> None:
    phds = [
        {
            "num": 0,
            "type": 1,
            "runway": 1,
            "first": 0,
            "count": 2,
            "data": "0",
        },
        _dim_phd(1, 1, 10),
    ]
    pds = [
        {"num": 0, "type": 1, "x": 100, "y": 0},
        {"num": 1, "type": 2, "x": 0, "y": 0, "root": 0},
        *_box_points(10, 100, 0),
    ]
    folder, phd_path, _ = _objective(tmp_path, "00001", phds, pds)
    request = RunwayRequest(
        folder,
        checks=frozenset({RunwayCheck.LIST_HEADING}),
    )

    checked = check_runways(request)
    fixed = fix_runways(request)

    assert checked.status is OperationStatus.WARNING
    assert checked.metrics["errors"] == 1
    assert fixed.status is OperationStatus.SUCCESS
    assert fixed.metrics["fixed"] == 1
    assert _field(phd_path, "0", "Data") == "90.000"


def test_assignment_uses_runway_dim_bounding_boxes(tmp_path: Path) -> None:
    phds = [
        {
            "num": 0,
            "type": 1,
            "runway": 1,
            "first": 0,
            "count": 2,
        },
        _dim_phd(1, 1, 10),
        _dim_phd(2, 2, 20),
    ]
    pds = [
        {"num": 0, "type": 1, "x": 100, "y": 0},
        {"num": 1, "type": 2, "x": 90, "y": 0, "root": 0},
        *_box_points(10, 0, 0),
        *_box_points(20, 100, 0),
    ]
    folder, phd_path, pdx_path = _objective(
        tmp_path,
        "00002",
        phds,
        pds,
    )
    assert pdx_path is not None
    phd_root = ET.parse(phd_path).getroot()
    pdx_root = ET.parse(pdx_path).getroot()
    index = {int(pd.get("Num") or ""): pd for pd in pdx_root.findall("PD")}
    boxes = build_runway_dim_boxes(phd_root, index)

    assert point_in_box((100, 0), boxes["2"])
    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.DIM_ASSIGNMENT}),
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert _field(phd_path, "0", "RunwayNumber") == "2"


def test_runway_dim_heading_honors_second_choice_without_pdx(
    tmp_path: Path,
) -> None:
    phds = [
        {"num": 0, "type": 1, "runway": 1, "data": "10.000"},
        {"num": 1, "type": 1, "runway": 1, "data": "190.000"},
        _dim_phd(2, 1, 10, data="99.000"),
    ]
    folder, phd_path, _ = _objective(tmp_path, "00003", phds, None)

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.DIM_HEADING}),
            heading_choice=HeadingChoice.SECOND,
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert _field(phd_path, "2", "Data") == "190.000"


@pytest.mark.parametrize(
    ("current", "cone", "force", "expected", "decision"),
    [
        ("020.000", 5, False, "020.000", "unchanged"),
        ("022.500", 5, False, "020.000", "near-match"),
        ("025.000", 5, False, "020.000", "near-match"),
        ("026.000", 5, False, "200.000", "fallback"),
        ("020.000", 5, True, "200.000", "forced"),
        ("20", 5, False, "20", "unchanged"),
    ],
)
def test_dim_heading_preserves_nearest_end_and_force_is_explicit(
    tmp_path: Path, current: str, cone: int, force: bool,
    expected: str, decision: str,
) -> None:
    phds = [
        {"num": 0, "type": 1, "runway": 1, "data": "200.000"},
        {"num": 1, "type": 1, "runway": 1, "data": "020.000"},
        _dim_phd(2, 1, 10, data=current),
    ]
    folder, phd_path, _ = _objective(tmp_path, "00033", phds, None)
    request = RunwayRequest(
        folder, checks=frozenset({RunwayCheck.DIM_HEADING}),
        heading_choice=HeadingChoice.FIRST,
        heading_cone_degrees=cone,
        force_heading_choice=force,
    )
    before = phd_path.read_bytes()
    checked = check_runways(request)
    assert checked.metrics["checks"][RunwayCheck.DIM_HEADING.value]["decisions"][decision] == 1
    assert phd_path.read_bytes() == before
    fixed = fix_runways(request)
    assert _field(phd_path, "2", "Data") == expected
    assert fixed.metrics["checks"][RunwayCheck.DIM_HEADING.value]["decisions"][decision] == 1
    if decision == "unchanged":
        assert phd_path.read_bytes() == before


def test_dim_heading_wrap_tie_and_missing_are_safe() -> None:
    decide = runway_service.decide_dim_heading
    assert decide("359", ["001"], HeadingChoice.FIRST)[0] == "near-match"
    assert decide("0", ["005", "355"], HeadingChoice.FIRST)[0] == "skipped"
    assert decide("", ["200", "020"], HeadingChoice.FIRST)[0] == "skipped"
    assert decide("", ["200", "020"], HeadingChoice.FIRST, force=True)[0] == "forced"
    assert decide("100", ["200"], HeadingChoice.SECOND)[1] == "200"


def test_phd_only_fix_continues_when_selected_pdx_check_cannot_parse(
    tmp_path: Path,
) -> None:
    phds = [
        {"num": 0, "type": 1, "runway": 1, "data": "10.000"},
        {"num": 1, "type": 1, "runway": 1, "data": "190.000"},
        _dim_phd(2, 1, 10, data="99.000"),
    ]
    folder, phd_path, pdx_path = _objective(
        tmp_path,
        "00012",
        phds,
        [],
    )
    assert pdx_path is not None
    pdx_path.write_text("<broken", encoding="utf-8")

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset(
                {
                    RunwayCheck.LIST_HEADING,
                    RunwayCheck.DIM_HEADING,
                }
            ),
            heading_choice=HeadingChoice.SECOND,
        )
    )

    assert result.status is OperationStatus.WARNING
    assert result.metrics["errors"] == 1
    assert _field(phd_path, "2", "Data") == "190.000"


def _valid_path_records() -> list[dict[str, object]]:
    return [
        {"num": 100, "type": 1, "x": 0, "y": 0},
        {"num": 101, "type": 2, "x": 0, "y": -100, "root": 0},
        {"num": 102, "type": 15, "x": 0, "y": -300, "root": 1},
        {"num": 103, "type": 3, "x": 0, "y": -400, "root": 2},
        {"num": 104, "type": 11, "x": 0, "y": -500, "root": 3},
    ]


def test_paths_checker_uses_relative_indices_and_accepts_valid_path(
    tmp_path: Path,
) -> None:
    phds = [
        {
            "num": 0,
            "type": 1,
            "first": 100,
            "count": 5,
        },
        _dim_phd(1, 1, 200),
    ]
    pds = [*_valid_path_records(), *_box_points(200, 0, 0)]
    folder, _, pdx_path = _objective(tmp_path, "00004", phds, pds)
    assert pdx_path is not None
    root = ET.parse(pdx_path).getroot()
    index = {int(pd.get("Num") or ""): pd for pd in root.findall("PD")}
    points, children, tree_root, parents = build_taxi_tree(index, 100, 5)
    paths = walk_taxi_paths(points, children, tree_root)

    assert tree_root == 0
    assert parents == {1: 0, 2: 1, 3: 2, 4: 3}
    assert [relative for _pd, relative in paths[0]] == [4, 3, 2, 1, 0]

    result = check_runways(
        RunwayRequest(folder, checks=frozenset({RunwayCheck.PATHS}))
    )
    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["ok"] == 1


@pytest.mark.parametrize(
    ("parking_y", "expected_errors", "expected_warnings"),
    [(-650, 0, 1), (-850, 1, 0)],
)
def test_paths_distance_severity_uses_twice_limit(
    tmp_path: Path,
    parking_y: float,
    expected_errors: int,
    expected_warnings: int,
) -> None:
    records = _valid_path_records()
    records[-1]["y"] = parking_y
    phds = [
        {"num": 0, "type": 1, "first": 100, "count": 5},
        _dim_phd(1, 1, 200),
    ]
    folder, _, _ = _objective(
        tmp_path,
        "00005",
        phds,
        [*records, *_box_points(200, 0, 0)],
    )

    result = check_runways(
        RunwayRequest(folder, checks=frozenset({RunwayCheck.PATHS}))
    )

    assert result.metrics["errors"] == expected_errors
    assert result.metrics["warnings"] == expected_warnings


def test_paths_checker_flags_nonconverging_parent(tmp_path: Path) -> None:
    records = _valid_path_records()
    records[1]["root"] = 2
    phds = [
        {"num": 0, "type": 1, "first": 100, "count": 5},
        _dim_phd(1, 1, 200),
    ]
    folder, _, _ = _objective(
        tmp_path,
        "00006",
        phds,
        [*records, *_box_points(200, 0, 0)],
    )

    result = check_runways(
        RunwayRequest(folder, checks=frozenset({RunwayCheck.PATHS}))
    )

    assert result.metrics["errors"] >= 1
    assert any(
        "parent index must be lower" in event.message
        for event in result.diagnostics
    )


def test_proper_segment_and_polygon_crossing_geometry() -> None:
    square = ((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))

    assert runway_segments_intersect(
        (-20, 0),
        (20, 0),
        (-10, -10),
        (-10, 10),
    )
    assert segment_polygon_crossings((-20, 0), (20, 0), square) == 2
    assert segment_polygon_crossings((-20, 20), (20, 20), square) == 0


def _crossing_fixture(tmp_path: Path, number: str = "00007"):
    phds = [
        {
            "num": 0,
            "type": 1,
            "runway": 1,
            "first": 0,
            "count": 6,
            "landing": 1,
        },
        _dim_phd(1, 2, 10),
    ]
    pds = [
        {"num": 0, "type": 1, "x": 500, "y": 0},
        {"num": 1, "type": 2, "x": 400, "y": 0, "root": 0},
        {"num": 2, "type": 15, "x": 300, "y": 0, "root": 1},
        {"num": 3, "type": 3, "x": 100, "y": 0, "root": 2},
        {"num": 4, "type": 19, "x": -100, "y": 0, "root": 3},
        {"num": 5, "type": 11, "x": -200, "y": 0, "root": 4},
        *_box_points(10, 0, 0),
    ]
    return _objective(tmp_path, number, phds, pds)


def test_through_crossing_pairs_require_taxi_boundaries(
    tmp_path: Path,
) -> None:
    folder, phd_path, pdx_path = _crossing_fixture(tmp_path)
    assert pdx_path is not None
    phd_root = ET.parse(phd_path).getroot()
    pdx_root = ET.parse(pdx_path).getroot()
    index = {int(pd.get("Num") or ""): pd for pd in pdx_root.findall("PD")}
    points, children, root, _ = build_taxi_tree(index, 0, 6)
    path = walk_taxi_paths(points, children, root)[0]
    polygons = build_runway_polygons(phd_root, index)

    assert build_crossing_pairs(path, polygons) == ((1, 2, "2"),)
    assert folder.name == "OCD_00007"


def test_crossing_fix_sets_markers_metadata_and_map_then_is_idempotent(
    tmp_path: Path,
) -> None:
    folder, _, pdx_path = _crossing_fixture(tmp_path)
    assert pdx_path is not None
    request = RunwayRequest(
        folder,
        checks=frozenset({RunwayCheck.CROSSING}),
    )

    first = fix_runways(request)
    first_bytes = pdx_path.read_bytes()
    second = fix_runways(request)

    root = ET.parse(pdx_path).getroot()
    points = {pd.get("Num"): pd for pd in root.findall("PD")}
    assert points["4"].findtext("CrossingPoint") == "1"
    assert points["3"].findtext("CrossingPoint") == "-1"
    assert points["4"].findtext("RunwayNumber") == "2"
    assert points["3"].findtext("RunwaySide") == "0"
    assert first.metrics["fixed"] == 2
    assert isinstance(first.metrics["map"], RunwayMapComparison)
    assert first.metrics["map"].after is not None
    assert second.metrics["fixed"] == 0
    assert pdx_path.read_bytes() == first_bytes


def test_two_file_runway_transaction_snapshots_both_originals(tmp_path: Path) -> None:
    folder, phd_path, pdx_path = _crossing_fixture(tmp_path, "00040")
    assert pdx_path is not None
    original = {phd_path: phd_path.read_bytes(), pdx_path: pdx_path.read_bytes()}
    context = OperationContext(
        backup_enabled=True,
        backup_root=tmp_path / "backups",
        backup_label="Runway",
    )
    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.LIST_HEADING, RunwayCheck.CROSSING}),
        ),
        context,
    )
    context.finish_backup(result)

    assert result.status in (OperationStatus.SUCCESS, OperationStatus.WARNING)
    assert result.metrics["backup_count"] == 2
    assert set(result.changed_files) == set(original)
    backup = Path(result.metrics["backup_path"])
    for path, data in original.items():
        assert (backup / "restore" / path.name).read_bytes() == data


def test_runway_backup_failure_blocks_transaction(tmp_path: Path) -> None:
    folder, phd_path, pdx_path = _crossing_fixture(tmp_path, "00041")
    assert pdx_path is not None
    original = {phd_path: phd_path.read_bytes(), pdx_path: pdx_path.read_bytes()}
    context = OperationContext(
        backup_enabled=True,
        backup_root=folder / "bad-backup-location",
    )
    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.LIST_HEADING, RunwayCheck.CROSSING}),
        ),
        context,
    )

    assert result.status is OperationStatus.FAILED
    assert not result.changed_files
    assert {path: path.read_bytes() for path in original} == original


def test_crossing_check_reports_stray_marker(tmp_path: Path) -> None:
    folder, _, pdx_path = _crossing_fixture(tmp_path, "00008")
    assert pdx_path is not None
    content = pdx_path.read_text(encoding="utf-8").replace(
        "<Type>11</Type>",
        "<Type>11</Type><CrossingPoint>1</CrossingPoint>",
        1,
    )
    pdx_path.write_text(content, encoding="utf-8")

    result = check_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.CROSSING}),
        )
    )

    assert result.metrics["warnings"] >= 1


def test_crossing_fix_clears_invalid_non_crossing_marker(
    tmp_path: Path,
) -> None:
    folder, _, pdx_path = _crossing_fixture(tmp_path, "00012")
    assert pdx_path is not None
    content = pdx_path.read_text(encoding="utf-8").replace(
        "<Type>11</Type>",
        "<Type>11</Type><CrossingPoint>legacy-invalid</CrossingPoint>",
        1,
    )
    pdx_path.write_text(content, encoding="utf-8")

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.CROSSING}),
        )
    )

    points = {
        pd.get("Num"): pd
        for pd in ET.parse(pdx_path).getroot().findall("PD")
    }
    assert result.status in (
        OperationStatus.SUCCESS,
        OperationStatus.WARNING,
    )
    assert points["5"].findtext("CrossingPoint") == "0"


def test_batch_discovers_objectives_beside_class_table(tmp_path: Path) -> None:
    class_table = tmp_path / "Falcon4_CT.xml"
    class_table.write_text("<CTRecords />", encoding="utf-8")
    objective_data = tmp_path / "ObjectiveRelatedData"
    _crossing_fixture(objective_data, "00001")
    non_airbase_phds = [
        {"num": 0, "type": 1, "first": 0, "count": 0}
    ]
    _objective(objective_data, "00002", non_airbase_phds, [])

    result = check_runways(
        RunwayRequest(
            class_table,
            mode=RunwayMode.BATCH,
            checks=frozenset({RunwayCheck.CROSSING}),
        )
    )

    assert result.metrics["airbases"] == 1
    assert result.metrics["map"] is None


def test_objective_transaction_rolls_back_phd_when_pdx_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder, phd_path, pdx_path = _crossing_fixture(tmp_path, "00009")
    assert pdx_path is not None
    before = {phd_path: phd_path.read_bytes(), pdx_path: pdx_path.read_bytes()}
    real_write = runway_service._atomic_write
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated PDX commit failure")
        real_write(path, content)

    monkeypatch.setattr(runway_service, "_atomic_write", fail_second)

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset(
                {
                    RunwayCheck.LIST_HEADING,
                    RunwayCheck.CROSSING,
                }
            ),
        )
    )

    assert result.status in (OperationStatus.FAILED, OperationStatus.WARNING)
    assert phd_path.read_bytes() == before[phd_path]
    assert pdx_path.read_bytes() == before[pdx_path]


def test_cancelled_fix_writes_nothing(tmp_path: Path) -> None:
    folder, phd_path, pdx_path = _crossing_fixture(tmp_path, "00010")
    assert pdx_path is not None
    before = {phd_path: phd_path.read_bytes(), pdx_path: pdx_path.read_bytes()}
    token = CancellationToken()
    token.cancel()

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.CROSSING}),
        ),
        OperationContext(cancellation=token),
    )

    assert result.status is OperationStatus.CANCELLED
    assert phd_path.read_bytes() == before[phd_path]
    assert pdx_path.read_bytes() == before[pdx_path]


def test_paths_checker_alone_cannot_be_fixed(tmp_path: Path) -> None:
    folder, _, _ = _crossing_fixture(tmp_path, "00011")

    result = fix_runways(
        RunwayRequest(
            folder,
            checks=frozenset({RunwayCheck.PATHS}),
        )
    )

    assert result.status is OperationStatus.FAILED

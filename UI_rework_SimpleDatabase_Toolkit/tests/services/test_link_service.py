from __future__ import annotations

import csv
from pathlib import Path

import pytest

from simple_database_toolkit.domain import (
    CancellationToken,
    OperationContext,
    OperationStatus,
)
from simple_database_toolkit.services import link_service
from simple_database_toolkit.services.link_service import (
    LinkGenerationRequest,
    LinkUpdateRequest,
    Segment,
    extract_distance_cost_lut,
    generate_all_links,
    read_objectives,
    segments_intersect,
    update_changed_links,
)


COSTS = (1, 2, 3, 4, 5, 6, 7, 8)
HEADER = [
    "Name",
    "Type",
    "Subtype",
    "ID",
    "X",
    "Y",
    "Owner",
    "Priority",
    "LCount",
    "Links",
]


def _row(
    name: str,
    objective_id: int,
    x: float,
    y: float,
    links: list[tuple[tuple[int, ...], int]],
) -> list[object]:
    values: list[object] = [
        name,
        "Scenery",
        "",
        objective_id,
        x,
        y,
        "",
        10,
        len(links),
    ]
    for costs, node_id in links:
        values.extend((*costs, node_id))
    return values


def _write_csv(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file, delimiter=";", lineterminator="\n")
        writer.writerow(["Falcon objective export"])
        writer.writerow(HEADER)
        writer.writerows(rows)


def _linked_dataset(path: Path, moved_x: float = 20.0) -> None:
    _write_csv(
        path,
        [
            _row("Zero", 0, 0, 0, [(COSTS, 1)]),
            _row("One", 1, 10, 0, [(COSTS, 0), (COSTS, 2)]),
            _row("Two", 2, moved_x, 0, [(COSTS, 1)]),
        ],
    )


def test_parser_preserves_zero_node_and_rail_cost(tmp_path: Path) -> None:
    source = tmp_path / "dataset.csv"
    zero_rail = (1, 2, 3, 4, 5, 6, 7, 0)
    _write_csv(
        source,
        [
            _row("Zero", 0, 0, 0, []),
            _row("One", 1, 10, 0, [(zero_rail, 0)]),
        ],
    )

    objectives = read_objectives(source)

    assert objectives[1].links[0].node_id == 0
    assert objectives[1].links[0].costs[-1] == 0


def test_extracts_distance_cost_lut(tmp_path: Path) -> None:
    source = tmp_path / "dataset.csv"
    _linked_dataset(source)

    lut = extract_distance_cost_lut(read_objectives(source))

    assert len(lut) == 1
    assert lut[0].costs == COSTS
    assert lut[0].count == 4
    assert lut[0].upper_km == float("inf")


def test_detects_crossing_but_allows_shared_endpoints() -> None:
    horizontal = Segment(1, 2, 0, 0, 10, 0)
    crossing = Segment(3, 4, 5, -5, 5, 5)
    shared = Segment(2, 5, 10, 0, 15, 5)

    assert segments_intersect(horizontal, crossing)
    assert not segments_intersect(horizontal, shared)


def test_generates_links_for_every_objective_without_self_links(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dataset.csv"
    output = tmp_path / "generated.csv"
    _linked_dataset(source)
    progress = []

    result = generate_all_links(
        LinkGenerationRequest(
            source,
            output,
            radius_km=100,
            allow_intersections=True,
        ),
        OperationContext(on_progress=progress.append),
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["objectives"] == 3
    assert result.metrics["targets"] == 3
    assert result.metrics["links"] == 3
    generated = read_objectives(output)
    assert all(
        link.node_id != objective.id
        for objective in generated.values()
        for link in objective.links
    )
    assert progress[-1].percent == 100


def test_generate_retains_source_row_order_for_intersection_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "shuffled.csv"
    output = tmp_path / "generated.csv"
    _write_csv(
        source,
        [
            _row("Nine", 9, 0, 0, [(COSTS, 2)]),
            _row("Two", 2, 10, 0, [(COSTS, 9)]),
            _row("Seven", 7, 20, 0, [(COSTS, 2)]),
        ],
    )
    captured: list[int] = []
    original_generate = link_service._generate_links

    def capture_order(**kwargs):
        captured.extend(kwargs["target_ids"])
        return original_generate(**kwargs)

    monkeypatch.setattr(link_service, "_generate_links", capture_order)

    result = generate_all_links(
        LinkGenerationRequest(source, output, allow_intersections=False)
    )

    assert result.status is OperationStatus.SUCCESS
    assert captured == [9, 2, 7]


def test_generation_can_atomically_replace_its_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dataset.csv"
    _linked_dataset(source)

    result = generate_all_links(
        LinkGenerationRequest(
            source,
            source,
            radius_km=100,
            allow_intersections=True,
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert len(read_objectives(source)) == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_update_recalculates_moved_and_neighbor_nodes(
    tmp_path: Path,
) -> None:
    old_csv = tmp_path / "old.csv"
    new_csv = tmp_path / "new.csv"
    output = tmp_path / "updated.csv"
    _linked_dataset(old_csv)
    _linked_dataset(new_csv, moved_x=25.0)

    result = update_changed_links(
        LinkUpdateRequest(
            old_csv,
            new_csv,
            output,
            radius_km=100,
            allow_intersections=True,
        )
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.metrics["moved"] == 1
    assert result.metrics["neighbors"] == 1
    assert result.metrics["targets"] == 2
    updated = read_objectives(output)
    for objective_id in (1, 2):
        assert all(
            link.node_id != objective_id
            for link in updated[objective_id].links
        )


def test_update_with_no_changes_does_not_require_a_lut(
    tmp_path: Path,
) -> None:
    old_csv = tmp_path / "old.csv"
    new_csv = tmp_path / "new.csv"
    output = tmp_path / "updated.csv"
    rows = [_row("Only", 1, 0, 0, [])]
    _write_csv(old_csv, rows)
    _write_csv(new_csv, rows)

    result = update_changed_links(
        LinkUpdateRequest(old_csv, new_csv, output)
    )

    assert result.status is OperationStatus.WARNING
    assert result.metrics["targets"] == 0
    assert output.is_file()


def test_failed_atomic_replace_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "dataset.csv"
    output = tmp_path / "output.csv"
    _linked_dataset(source)
    output.write_text("keep me", encoding="utf-8")

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(link_service.os, "replace", fail_replace)
    result = generate_all_links(
        LinkGenerationRequest(
            source,
            output,
            radius_km=100,
            allow_intersections=True,
        )
    )

    assert result.status is OperationStatus.FAILED
    assert output.read_text(encoding="utf-8") == "keep me"
    assert not list(tmp_path.glob("*.tmp"))


def test_pre_cancelled_generation_writes_no_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "dataset.csv"
    output = tmp_path / "output.csv"
    _linked_dataset(source)
    cancellation = CancellationToken()
    cancellation.cancel()

    result = generate_all_links(
        LinkGenerationRequest(source, output),
        OperationContext(cancellation=cancellation),
    )

    assert result.status is OperationStatus.CANCELLED
    assert not output.exists()


@pytest.mark.parametrize("radius", [0, -1, float("inf")])
def test_rejects_invalid_radius(tmp_path: Path, radius: float) -> None:
    source = tmp_path / "dataset.csv"
    _linked_dataset(source)

    result = generate_all_links(
        LinkGenerationRequest(
            source,
            tmp_path / "output.csv",
            radius_km=radius,
        )
    )

    assert result.status is OperationStatus.FAILED

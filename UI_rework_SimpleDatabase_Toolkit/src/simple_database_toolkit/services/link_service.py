"""Objective link generation and update services."""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from simple_database_toolkit.domain import (
    DiagnosticEvent,
    DiagnosticSeverity,
    OperationCancelled,
    OperationContext,
    OperationResult,
    OperationStatus,
    ProgressUpdate,
)


CostTuple = tuple[int, int, int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class Link:
    costs: CostTuple
    node_id: int


@dataclass(slots=True)
class Objective:
    id: int
    name: str
    type: str
    subtype: str
    x: float
    y: float
    owner: int | None
    priority: int | None
    links: list[Link]


@dataclass(frozen=True, slots=True)
class Segment:
    id_a: int
    id_b: int
    ax: float
    ay: float
    bx: float
    by: float


@dataclass(frozen=True, slots=True)
class CostBand:
    costs: CostTuple
    count: int
    min_km: float
    max_km: float
    mean_km: float
    upper_km: float


@dataclass(frozen=True, slots=True)
class LinkGenerationRequest:
    source_csv: Path
    output_csv: Path
    lut_json: Path | None = None
    radius_km: float = 120.0
    allow_intersections: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_csv", Path(self.source_csv))
        object.__setattr__(self, "output_csv", Path(self.output_csv))
        if self.lut_json is not None:
            object.__setattr__(self, "lut_json", Path(self.lut_json))


@dataclass(frozen=True, slots=True)
class LinkUpdateRequest:
    old_csv: Path
    new_csv: Path
    output_csv: Path
    lut_json: Path | None = None
    radius_km: float = 120.0
    move_epsilon: float = 1e-6
    allow_intersections: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "old_csv", Path(self.old_csv))
        object.__setattr__(self, "new_csv", Path(self.new_csv))
        object.__setattr__(self, "output_csv", Path(self.output_csv))
        if self.lut_json is not None:
            object.__setattr__(self, "lut_json", Path(self.lut_json))


DEFAULT_K_BY_TYPE: dict[str, int] = {
    "Scenery": 1,
    "Bridge": 1,
    "Intersection": 3,
    "Village": 2,
    "Town": 3,
    "City": 3,
    "Port": 3,
    "Factory": 2,
    "Depot": 2,
    "Power Plant": 2,
    "Chemical": 2,
    "Nuclear": 2,
    "ArmyBase": 2,
    "Airbase": 2,
}


def generate_all_links(
    request: LinkGenerationRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    error = _validate_common_request(
        input_paths=[request.source_csv],
        output_path=request.output_csv,
        lut_path=request.lut_json,
        radius_km=request.radius_km,
    )
    if error is not None:
        report(DiagnosticSeverity.ERROR, error)
        return _failed_result(error, diagnostics)

    try:
        objectives = read_objectives(request.source_csv)
        if not objectives:
            raise ValueError("The dataset contains no valid objectives.")
        lut = _load_or_derive_lut(request.lut_json, objectives)
        report(
            DiagnosticSeverity.INFO,
            f"Loaded {len(objectives)} objectives and {len(lut)} LUT bins.",
            request.source_csv,
        )
        generated = _generate_links(
            objectives=objectives,
            # Link intersection avoidance is sequential, so retain the source
            # CSV row order used by the legacy application.
            target_ids=list(objectives),
            lut=lut,
            radius_km=request.radius_km,
            avoid_intersections=not request.allow_intersections,
            rebuild_all=True,
            context=context,
        )
        total_links = sum(len(links) for links in generated.values())
        _rewrite_links_atomic(
            request.source_csv,
            request.output_csv,
            generated,
            context,
        )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Generation cancelled before the output was replaced.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Link generation cancelled",
            diagnostics=diagnostics,
            metrics={"objectives": 0, "targets": 0, "links": 0},
        )
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        report(
            DiagnosticSeverity.ERROR,
            f"Link generation failed: {exc}",
            request.source_csv,
        )
        return _failed_result("Link generation failed", diagnostics)

    report(
        DiagnosticSeverity.SUCCESS,
        f"Wrote {total_links} generated links.",
        request.output_csv,
    )
    return OperationResult(
        status=OperationStatus.SUCCESS,
        summary=(
            f"Rebuilt links for {len(generated)} objectives; "
            f"{total_links} links written"
        ),
        diagnostics=diagnostics,
        changed_files=[request.output_csv],
        metrics={
            "objectives": len(objectives),
            "targets": len(generated),
            "links": total_links,
            "lut_bins": len(lut),
        },
    )


def update_changed_links(
    request: LinkUpdateRequest,
    context: OperationContext | None = None,
) -> OperationResult:
    context = context or OperationContext()
    diagnostics: list[DiagnosticEvent] = []
    report = _reporter(context, diagnostics)
    error = _validate_common_request(
        input_paths=[request.old_csv, request.new_csv],
        output_path=request.output_csv,
        lut_path=request.lut_json,
        radius_km=request.radius_km,
    )
    if request.move_epsilon < 0 or not math.isfinite(request.move_epsilon):
        error = "Movement epsilon must be a finite value >= 0."
    if error is not None:
        report(DiagnosticSeverity.ERROR, error)
        return _failed_result(error, diagnostics)

    try:
        old_objectives = read_objectives(request.old_csv)
        new_objectives = read_objectives(request.new_csv)
        if not new_objectives:
            raise ValueError("The new dataset contains no valid objectives.")

        new_ids, moved_ids, neighbor_ids = _update_target_ids(
            old_objectives,
            new_objectives,
            request.move_epsilon,
        )
        target_ids = sorted(new_ids | moved_ids | neighbor_ids)
        lut = (
            _load_or_derive_lut(request.lut_json, new_objectives)
            if target_ids
            else []
        )
        report(
            DiagnosticSeverity.INFO,
            f"Selected {len(target_ids)} objectives: {len(new_ids)} new, "
            f"{len(moved_ids)} moved, {len(neighbor_ids)} neighboring.",
            request.new_csv,
        )

        generated = _generate_links(
            objectives=new_objectives,
            target_ids=target_ids,
            lut=lut,
            radius_km=request.radius_km,
            avoid_intersections=not request.allow_intersections,
            rebuild_all=False,
            context=context,
        )
        total_links = sum(len(links) for links in generated.values())
        _rewrite_links_atomic(
            request.new_csv,
            request.output_csv,
            generated,
            context,
        )
    except OperationCancelled:
        report(
            DiagnosticSeverity.WARNING,
            "Update cancelled before the output was replaced.",
        )
        return OperationResult(
            status=OperationStatus.CANCELLED,
            summary="Link update cancelled",
            diagnostics=diagnostics,
            metrics={"objectives": 0, "targets": 0, "links": 0},
        )
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as exc:
        report(
            DiagnosticSeverity.ERROR,
            f"Link update failed: {exc}",
            request.new_csv,
        )
        return _failed_result("Link update failed", diagnostics)

    status = (
        OperationStatus.SUCCESS
        if target_ids
        else OperationStatus.WARNING
    )
    if target_ids:
        report(
            DiagnosticSeverity.SUCCESS,
            f"Wrote recalculated links for {len(target_ids)} objectives.",
            request.output_csv,
        )
    else:
        report(
            DiagnosticSeverity.WARNING,
            "No new, moved, or neighboring objectives required recalculation.",
            request.output_csv,
        )
    return OperationResult(
        status=status,
        summary=(
            f"Recalculated {len(target_ids)} objectives; "
            f"{total_links} links written"
        ),
        diagnostics=diagnostics,
        changed_files=[request.output_csv],
        metrics={
            "objectives": len(new_objectives),
            "targets": len(target_ids),
            "links": total_links,
            "lut_bins": len(lut),
            "new": len(new_ids),
            "moved": len(moved_ids),
            "neighbors": len(neighbor_ids),
        },
    )


def read_objectives(csv_path: Path) -> dict[int, Objective]:
    rows = _read_csv_rows(csv_path)
    header_index, header = _find_header(rows)
    indices = {name: header.index(name) for name in _required_headers()}
    owner_index = header.index("Owner") if "Owner" in header else None
    priority_index = header.index("Priority") if "Priority" in header else None

    objectives: dict[int, Objective] = {}
    for raw_row in rows[header_index + 1 :]:
        row = [cell.strip() for cell in raw_row]
        if not row or not any(row):
            continue
        objective_id = _cell_int(row, indices["ID"])
        if objective_id is None:
            continue

        link_count = _cell_int(row, indices["LCount"], 0) or 0
        links_index = indices["Links"]
        available_groups = max(0, (len(row) - links_index) // 9)
        links: list[Link] = []
        for group in range(min(max(0, link_count), available_groups)):
            base = links_index + group * 9
            cost_values = tuple(
                _to_int(row[base + offset], 255 if offset == 7 else 0)
                for offset in range(8)
            )
            node_id = _to_int(row[base + 8], None)
            if node_id is None:
                continue
            links.append(
                Link(
                    costs=cost_values,  # type: ignore[arg-type]
                    node_id=node_id,
                )
            )

        name_index = indices["Name"]
        type_index = indices["Type"]
        subtype_index = indices["Subtype"]
        objectives[objective_id] = Objective(
            id=objective_id,
            name=_cell(row, name_index, str(objective_id)),
            type=_cell(row, type_index),
            subtype=_cell(row, subtype_index),
            x=_cell_float(row, indices["X"], 0.0),
            y=_cell_float(row, indices["Y"], 0.0),
            owner=(
                _cell_int(row, owner_index)
                if owner_index is not None
                else None
            ),
            priority=(
                _cell_int(row, priority_index)
                if priority_index is not None
                else None
            ),
            links=links,
        )
    return objectives


def extract_distance_cost_lut(
    objectives: dict[int, Objective],
) -> list[CostBand]:
    distances: dict[CostTuple, list[float]] = {}
    for source in objectives.values():
        for link in source.links:
            destination = objectives.get(link.node_id)
            if destination is None:
                continue
            distances.setdefault(link.costs, []).append(
                distance_km(source, destination)
            )

    ordered = sorted(
        (
            (
                costs,
                values,
                sum(values) / len(values),
            )
            for costs, values in distances.items()
            if values
        ),
        key=lambda item: (item[2], min(item[1])),
    )
    bands: list[CostBand] = []
    for index, (costs, values, mean) in enumerate(ordered):
        if index + 1 < len(ordered):
            next_mean = ordered[index + 1][2]
            upper = (mean + next_mean) / 2.0
        else:
            upper = math.inf
        bands.append(
            CostBand(
                costs=costs,
                count=len(values),
                min_km=min(values),
                max_km=max(values),
                mean_km=mean,
                upper_km=upper,
            )
        )
    return bands


def load_lut(path: Path) -> list[CostBand]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError("LUT JSON must contain a list of cost bins.")

    bands: list[CostBand] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"LUT bin {index} is not an object.")
        costs_raw = item.get("costs")
        if not isinstance(costs_raw, list) or len(costs_raw) != 8:
            raise ValueError(f"LUT bin {index} requires exactly 8 costs.")
        costs = tuple(int(value) for value in costs_raw)
        bands.append(
            CostBand(
                costs=costs,  # type: ignore[arg-type]
                count=int(item.get("count", 0)),
                min_km=float(item.get("min_km", 0.0)),
                max_km=float(item.get("max_km", 0.0)),
                mean_km=float(item.get("mean_km", 0.0)),
                upper_km=float(item.get("upper_km", math.inf)),
            )
        )
    bands.sort(key=lambda band: (band.mean_km, band.min_km))
    if not bands:
        raise ValueError("LUT JSON contains no cost bins.")
    return bands


def distance_km(first: Objective, second: Objective) -> float:
    return math.hypot(first.x - second.x, first.y - second.y)


def segments_intersect(first: Segment, second: Segment) -> bool:
    if len({first.id_a, first.id_b, second.id_a, second.id_b}) < 4:
        return False
    first_a = (first.ax, first.ay)
    first_b = (first.bx, first.by)
    second_a = (second.ax, second.ay)
    second_b = (second.bx, second.by)
    orientations = (
        _orientation(*first_a, *first_b, *second_a),
        _orientation(*first_a, *first_b, *second_b),
        _orientation(*second_a, *second_b, *first_a),
        _orientation(*second_a, *second_b, *first_b),
    )
    first_one, first_two, second_one, second_two = orientations
    if (
        (first_one > 0) != (first_two > 0)
        and (second_one > 0) != (second_two > 0)
    ):
        return True
    return (
        (first_one == 0 and _on_segment(*first_a, *second_a, *first_b))
        or (first_two == 0 and _on_segment(*first_a, *second_b, *first_b))
        or (second_one == 0 and _on_segment(*second_a, *first_a, *second_b))
        or (second_two == 0 and _on_segment(*second_a, *first_b, *second_b))
    )


def _generate_links(
    *,
    objectives: dict[int, Objective],
    target_ids: list[int],
    lut: list[CostBand],
    radius_km: float,
    avoid_intersections: bool,
    rebuild_all: bool,
    context: OperationContext,
) -> dict[int, list[Link]]:
    existing_segments = (
        [] if rebuild_all else _collect_existing_segments(objectives)
    )
    generated: dict[int, list[Link]] = {}
    all_objectives = list(objectives.values())
    for index, objective_id in enumerate(target_ids, start=1):
        context.check_cancelled()
        node = objectives[objective_id]
        candidates = [
            (other, distance_km(node, other))
            for other in all_objectives
            if other.id != node.id
        ]
        candidates = [
            candidate
            for candidate in candidates
            if candidate[1] <= radius_km
        ]
        candidates.sort(
            key=lambda item: (
                item[1],
                -(item[0].priority or 0),
                item[0].id,
            )
        )
        neighbor_count = DEFAULT_K_BY_TYPE.get(node.type.strip(), 3)
        links: list[Link] = []
        for other, distance in candidates[:neighbor_count]:
            link = Link(
                costs=_costs_for_distance(lut, distance),
                node_id=other.id,
            )
            candidate_segment = Segment(
                min(node.id, other.id),
                max(node.id, other.id),
                node.x,
                node.y,
                other.x,
                other.y,
            )
            if avoid_intersections and any(
                segments_intersect(candidate_segment, segment)
                for segment in existing_segments
            ):
                continue
            links.append(link)
            if avoid_intersections:
                existing_segments.append(candidate_segment)
        generated[node.id] = links
        context.report_progress(
            ProgressUpdate(
                current=index,
                total=len(target_ids),
                message=f"Generated links for {node.name}",
            )
        )
    return generated


def _update_target_ids(
    old_objectives: dict[int, Objective],
    new_objectives: dict[int, Objective],
    move_epsilon: float,
) -> tuple[set[int], set[int], set[int]]:
    new_ids: set[int] = set()
    moved_ids: set[int] = set()
    for objective_id, objective in new_objectives.items():
        previous = old_objectives.get(objective_id)
        if previous is None:
            new_ids.add(objective_id)
        elif (
            abs(objective.x - previous.x) > move_epsilon
            or abs(objective.y - previous.y) > move_epsilon
        ):
            moved_ids.add(objective_id)

    changed_ids = new_ids | moved_ids
    neighbor_ids: set[int] = set()
    for collection in (new_objectives, old_objectives):
        for objective in collection.values():
            if objective.id in changed_ids or objective.id not in new_objectives:
                continue
            if any(link.node_id in changed_ids for link in objective.links):
                neighbor_ids.add(objective.id)
    return new_ids, moved_ids, neighbor_ids


def _collect_existing_segments(
    objectives: dict[int, Objective],
) -> list[Segment]:
    segments: list[Segment] = []
    for source in objectives.values():
        for link in source.links:
            destination = objectives.get(link.node_id)
            if destination is None or source.id >= destination.id:
                continue
            segments.append(
                Segment(
                    source.id,
                    destination.id,
                    source.x,
                    source.y,
                    destination.x,
                    destination.y,
                )
            )
    return segments


def _load_or_derive_lut(
    lut_path: Path | None,
    objectives: dict[int, Objective],
) -> list[CostBand]:
    lut = (
        load_lut(lut_path)
        if lut_path is not None
        else extract_distance_cost_lut(objectives)
    )
    if not lut:
        raise ValueError(
            "No LUT could be derived because the dataset has no valid links."
        )
    return lut


def _costs_for_distance(
    lut: list[CostBand],
    distance: float,
) -> CostTuple:
    for band in lut:
        if distance <= band.upper_km:
            return band.costs
    return lut[-1].costs


def _rewrite_links_atomic(
    source: Path,
    destination: Path,
    generated: dict[int, list[Link]],
    context: OperationContext,
) -> None:
    rows = _read_csv_rows(source)
    header_index, header = _find_header(rows)
    id_index = header.index("ID")
    count_index = header.index("LCount")
    links_index = header.index("Links")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            writer = csv.writer(
                temporary_file,
                delimiter=";",
                lineterminator="\n",
            )
            for row_index, row in enumerate(rows):
                if row_index <= header_index:
                    writer.writerow(row)
                    continue
                context.check_cancelled()
                objective_id = _cell_int(row, id_index)
                if objective_id is None or objective_id not in generated:
                    writer.writerow(row)
                    continue

                old_count = _cell_int(row, count_index, 0) or 0
                old_end = min(len(row), links_index + old_count * 9)
                prefix = list(row[:links_index])
                while len(prefix) <= count_index:
                    prefix.append("")
                prefix[count_index] = str(len(generated[objective_id]))
                flattened = [
                    str(value)
                    for link in generated[objective_id]
                    for value in (*link.costs, link.node_id)
                ]
                writer.writerow(prefix + flattened + row[old_end:])
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        mode_source = destination if destination.exists() else source
        shutil.copymode(mode_source, temporary_path)
        context.backup_files([destination], destination.parent)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.reader(csv_file, delimiter=";", skipinitialspace=True))


def _find_header(
    rows: list[list[str]],
) -> tuple[int, list[str]]:
    required = set(_required_headers())
    for index, row in enumerate(rows):
        stripped = [cell.strip() for cell in row]
        if required.issubset(stripped):
            return index, stripped
    raise ValueError(
        "Could not find CSV header with Name, Type, Subtype, ID, X, Y, "
        "LCount, and Links."
    )


def _required_headers() -> tuple[str, ...]:
    return ("Name", "Type", "Subtype", "ID", "X", "Y", "LCount", "Links")


def _validate_common_request(
    *,
    input_paths: list[Path],
    output_path: Path,
    lut_path: Path | None,
    radius_km: float,
) -> str | None:
    for path in input_paths:
        if not path.is_file():
            return f"Input CSV does not exist: {path}"
    if output_path.suffix.casefold() != ".csv":
        return "Output path must use the .csv extension."
    if not output_path.parent.is_dir():
        return "Output directory does not exist."
    if lut_path is not None and not lut_path.is_file():
        return f"LUT JSON does not exist: {lut_path}"
    if radius_km <= 0 or not math.isfinite(radius_km):
        return "Radius must be a finite value greater than zero."
    return None


def _cell(row: list[str], index: int, default: str = "") -> str:
    return row[index].strip() if index < len(row) else default


def _cell_int(
    row: list[str],
    index: int,
    default: int | None = None,
) -> int | None:
    return _to_int(_cell(row, index), default)


def _cell_float(
    row: list[str],
    index: int,
    default: float,
) -> float:
    try:
        return float(_cell(row, index))
    except (TypeError, ValueError):
        return default


def _to_int(value: str, default: int | None) -> int | None:
    try:
        if value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _orientation(
    px: float,
    py: float,
    qx: float,
    qy: float,
    rx: float,
    ry: float,
) -> float:
    return (qx - px) * (ry - py) - (qy - py) * (rx - px)


def _on_segment(
    px: float,
    py: float,
    qx: float,
    qy: float,
    rx: float,
    ry: float,
) -> bool:
    return (
        min(px, rx) <= qx <= max(px, rx)
        and min(py, ry) <= qy <= max(py, ry)
    )


def _reporter(
    context: OperationContext,
    diagnostics: list[DiagnosticEvent],
):
    def report(
        severity: DiagnosticSeverity,
        message: str,
        target: Path | None = None,
    ) -> None:
        event = DiagnosticEvent(
            severity=severity,
            module="Links Generator",
            message=message,
            target=str(target) if target is not None else "",
        )
        diagnostics.append(event)
        context.report_diagnostic(event)

    return report


def _failed_result(
    summary: str,
    diagnostics: list[DiagnosticEvent],
) -> OperationResult:
    return OperationResult(
        status=OperationStatus.FAILED,
        summary=summary,
        diagnostics=diagnostics,
        metrics={
            "objectives": 0,
            "targets": 0,
            "links": 0,
            "lut_bins": 0,
        },
    )

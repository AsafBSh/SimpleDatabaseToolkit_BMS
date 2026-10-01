"""Opt-in format/restore acceptance tests using installed XML as read-only input."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simple_database_toolkit.domain import OperationContext, OperationStatus
from simple_database_toolkit.services import (
    HeadingChoice, RunwayCheck, RunwayRequest, check_runways, fix_runways,
    OffsetAdjustment, OffsetOperation, OffsetRequest, apply_offset,
    ReplaceFeatureRequest, replace_features,
    ParkingRequest, ParkingPreview, preview_parking, apply_parking,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _heading_case(root: ET.Element):
    available: dict[str, list[str]] = {}
    for phd in root.findall("PHD"):
        if phd.findtext("Type") == "1":
            available.setdefault(phd.findtext("RunwayNumber", ""), []).append(phd.findtext("Data", ""))
    for dim in root.findall("PHD"):
        candidates = available.get(dim.findtext("RunwayNumber", ""), [])
        if dim.findtext("Type") == "8" and len(candidates) >= 2:
            if abs(((float(candidates[0]) - float(candidates[1]) + 180) % 360) - 180) > 10:
                return dim.get("Num"), candidates
    return None


@pytest.fixture(scope="session")
def source_folder(theater_root: Path) -> Path:
    assert (theater_root / "Falcon4_CT.xml").is_file()
    objective_root = theater_root / "ObjectiveRelatedData"
    preferred = objective_root / "OCD_00667"
    folders = [preferred, *sorted(objective_root.glob("OCD_*"))]
    for folder in folders:
        phd = folder / f"PHD_{folder.name[4:]}.xml"
        if phd.is_file() and _heading_case(ET.parse(phd).getroot()):
            return folder
    pytest.fail("No representative airbase with both runway-end headings found")


@pytest.fixture
def copied_objective(tmp_path: Path, source_folder: Path, theater_root: Path, record_property):
    sources = list(source_folder.glob("*.xml")) + [theater_root / "Falcon4_CT.xml"]
    original_hashes = {path: _sha(path) for path in sources}
    folder = tmp_path / source_folder.name
    folder.mkdir()
    for source in sources:
        target = tmp_path / source.name if source.name.casefold() == "falcon4_ct.xml" else folder / source.name
        shutil.copy2(source, target)
    record_property("read_only_source", str(source_folder))
    try:
        yield folder
    finally:
        assert {path: _sha(path) for path in sources} == original_hashes


def _path(folder: Path, prefix: str) -> Path:
    return folder / f"{prefix}_{folder.name[4:]}.xml"


def _context(folder: Path) -> OperationContext:
    return OperationContext(backup_enabled=True, backup_root=folder.parent / "backups", backup_label="Acceptance")


def _restore(context: OperationContext, result, originals: dict[Path, bytes]) -> None:
    assert result.status in (OperationStatus.SUCCESS, OperationStatus.WARNING), result.summary
    context.finish_backup(result)
    assert result.changed_files
    assert result.metrics["backup_count"] == len(result.changed_files)
    snapshot = context.backup_session
    assert snapshot is not None
    for entry in snapshot.entries:
        target = Path(entry["original"])
        assert target in originals
        backup = Path(entry["backup"])
        assert backup.read_bytes() == originals[target]
        shutil.copy2(backup, target)
    assert {path: path.read_bytes() for path in originals} == originals


def _fidelity(before: bytes, after: bytes, fields: tuple[str, ...]) -> None:
    def mask(data: bytes) -> bytes:
        for field in fields:
            tag = field.encode()
            pattern = rb"(<" + tag + rb"\b[^>]*>)[^<]*(</" + tag + rb"\s*>)"
            data = re.sub(pattern, lambda match: match[1] + b"VALUE" + match[2], data)
        return data
    assert mask(before) == mask(after), "Writer changed XML bytes outside the requested values (declaration/CRLF/layout)."


def test_check_only_keeps_copied_xml_unchanged(copied_objective: Path) -> None:
    originals = {path: path.read_bytes() for path in copied_objective.glob("*.xml")}
    result = check_runways(RunwayRequest(copied_objective, checks=frozenset(RunwayCheck)))
    assert result.metrics["airbases"] == 1
    assert not any("Could not process objective" in event.message for event in result.diagnostics)
    assert not result.changed_files
    assert {path: path.read_bytes() for path in originals} == originals


def test_all_runway_repairs_parse_and_restore(copied_objective: Path) -> None:
    originals = {path: path.read_bytes() for path in copied_objective.glob("*.xml")}
    context = _context(copied_objective)
    result = fix_runways(RunwayRequest(copied_objective, checks=frozenset(RunwayCheck)), context)
    assert result.metrics["airbases"] == 1
    assert not any("Could not process objective" in event.message for event in result.diagnostics)
    for path in result.changed_files:
        before = ET.fromstring(originals[path])
        after = ET.fromstring(path.read_bytes())
        assert before.tag == after.tag
        assert [record.get("Num") for record in before] == [record.get("Num") for record in after]
        assert b"\r\n" in path.read_bytes()
    if result.changed_files:
        _restore(context, result, {path: originals[path] for path in result.changed_files})
    else:
        assert context.backup_session is None
    assert {path: path.read_bytes() for path in originals} == originals


@pytest.mark.parametrize("operation", list(OffsetOperation))
def test_offset_format_and_restore(copied_objective: Path, operation: OffsetOperation) -> None:
    path = _path(copied_objective, "FED")
    before = path.read_bytes()
    root = ET.fromstring(before)
    fields = {
        OffsetOperation.XY: ("OffsetX", "OffsetY"),
        OffsetOperation.ROTATE: ("Heading",),
        OffsetOperation.SET_HEADING: ("Heading",),
        OffsetOperation.SET_Z: ("OffsetZ",),
        OffsetOperation.SET_VALUE: ("Value",),
    }[operation]
    selected = next(fed for fed in root.findall("FED") if all(fed.findtext(field) is not None for field in fields))
    feature = int(selected.findtext("FeatureCtIdx"))
    value = 67 if operation is OffsetOperation.SET_VALUE else 12.5
    context = _context(copied_objective)
    result = apply_offset(OffsetRequest(copied_objective, feature, OffsetAdjustment(operation, x=1, y=-2, value=value)), context)
    after = path.read_bytes()
    updated = ET.fromstring(after)
    assert len(updated.findall("FED")) == len(root.findall("FED"))
    edited = next(fed for fed in updated.findall("FED") if fed.get("Num") == selected.get("Num"))
    if operation is OffsetOperation.XY:
        heading = math.radians(float(selected.findtext("Heading")))
        assert float(edited.findtext("OffsetX")) == pytest.approx(float(selected.findtext("OffsetX")) + math.sin(heading) - 2 * math.cos(heading), abs=0.001)
        assert float(edited.findtext("OffsetY")) == pytest.approx(float(selected.findtext("OffsetY")) + math.cos(heading) + 2 * math.sin(heading), abs=0.001)
    elif operation is OffsetOperation.ROTATE:
        assert float(edited.findtext("Heading")) == pytest.approx((float(selected.findtext("Heading")) + value) % 360, abs=0.051)
    else:
        assert float(edited.findtext(fields[0])) == value
    for fed in updated.findall("FED"):
        for field in fields:
            value_text = fed.findtext(field)
            if value_text is not None:
                assert math.isfinite(float(value_text))
    _restore(context, result, {path: before})
    _fidelity(before, after, fields)


def test_replacement_format_and_restore(copied_objective: Path) -> None:
    path = _path(copied_objective, "FED")
    before = path.read_bytes()
    features = [int(fed.findtext("FeatureCtIdx")) for fed in ET.fromstring(before).findall("FED")]
    old = features[0]
    new = next(value for value in features if value != old)
    context = _context(copied_objective)
    result = replace_features(ReplaceFeatureRequest(copied_objective, old, new), context)
    after = path.read_bytes()
    assert old not in [int(fed.findtext("FeatureCtIdx")) for fed in ET.fromstring(after).findall("FED")]
    _restore(context, result, {path: before})
    _fidelity(before, after, ("FeatureCtIdx",))


@pytest.mark.parametrize("mode", ["valid-opposite", "near-opposite", "force-first"])
def test_runway_heading_policy_format_and_restore(copied_objective: Path, mode: str) -> None:
    path = _path(copied_objective, "PHD")
    number, candidates = _heading_case(ET.parse(path).getroot())
    current = candidates[1] if mode != "near-opposite" else f"{(float(candidates[1]) + 2.5) % 360:.3f}"
    text = path.read_bytes()
    block = rb"(<PHD\b[^>]*\bNum=\"" + number.encode() + rb"\"[^>]*>)(.*?)(</PHD>)"
    text, count = re.subn(block, lambda match: match[1] + re.sub(rb"(<Data>)[^<]*(</Data>)", lambda field: field[1] + current.encode() + field[2], match[2]) + match[3], text, flags=re.DOTALL)
    assert count == 1
    path.write_bytes(text)  # Deliberately alter only the temporary test copy.
    before = path.read_bytes()
    context = _context(copied_objective)
    request = RunwayRequest(copied_objective, checks=frozenset({RunwayCheck.DIM_HEADING}), heading_choice=HeadingChoice.FIRST, force_heading_choice=mode == "force-first")
    result = fix_runways(request, context)
    after = path.read_bytes()
    dim = next(item for item in ET.fromstring(after).findall("PHD") if item.get("Num") == number)
    expected = candidates[0] if mode == "force-first" else candidates[1]
    assert float(dim.findtext("Data")) == float(expected)
    if mode == "valid-opposite":
        assert before == after
        assert not result.changed_files
    else:
        repeated = fix_runways(request)
        assert not repeated.changed_files
        assert path.read_bytes() == after
        _restore(context, result, {path: before})
        _fidelity(before, after, ("Data",))


def test_parking_preview_apply_format_and_restore(copied_objective: Path) -> None:
    path = _path(copied_objective, "PDX")
    before = path.read_bytes()
    # Wide radius exercises actual installed coordinates on copies, not a repair recommendation.
    request = ParkingRequest(copied_objective, copied_objective.parent / "Falcon4_CT.xml", radius_feet=100000)
    preview_result = preview_parking(request)
    preview = preview_result.metrics.get("preview")
    assert isinstance(preview, ParkingPreview), preview_result.summary
    assert preview.moves, "Selected airbase has no parking-to-hangar moves"
    assert path.read_bytes() == before
    context = _context(copied_objective)
    result = apply_parking(request, context, expected_preview=preview)
    after = path.read_bytes()
    ET.fromstring(after)
    _restore(context, result, {path: before})
    _fidelity(before, after, ("OffsetX", "OffsetY"))

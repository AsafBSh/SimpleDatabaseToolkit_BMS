from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from simple_database_toolkit.domain.backups import BackupSession
from simple_database_toolkit.domain import OperationContext, OperationStatus
from simple_database_toolkit.services.replace_service import (
    ReplaceFeatureRequest, replace_features,
)


def test_backup_snapshot_restores_original_bytes_and_names(tmp_path: Path) -> None:
    source = tmp_path / "model"
    nested = source / "nested"
    nested.mkdir(parents=True)
    bml = source / "aircraft.bml"
    sidecar = nested / "Parent.dat"
    bml.write_bytes(b"\x00\xffBML\x00")
    sidecar.write_bytes(b"\xef\xbb\xbfTextureSets=1\r\n")
    original = {bml: bml.read_bytes(), sidecar: sidecar.read_bytes()}

    session = BackupSession(tmp_path / "backups", "BML", source)
    session.capture([bml, sidecar])
    session.finish("success")
    bml.write_bytes(b"changed")
    sidecar.write_bytes(b"changed")

    for path in original:
        shutil.copy2(session.folder / "restore" / path.relative_to(source), path)
    assert {path: path.read_bytes() for path in original} == original
    manifest = json.loads((session.folder / "manifest.json").read_text())
    assert manifest["status"] == "success"
    assert len(manifest["files"]) == 2
    assert all(entry["sha256"] for entry in manifest["files"])
    assert "copy the contents of restore/" in (session.folder / "RESTORE.txt").read_text()


def test_backup_root_inside_target_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "model"
    source.mkdir()
    with pytest.raises(ValueError, match="outside"):
        BackupSession(source / "backups", "BML", source)


def test_backup_session_is_collision_safe(tmp_path: Path) -> None:
    source = tmp_path / "model"
    source.mkdir()
    first = BackupSession(tmp_path / "backups", "Runway", source)
    second = BackupSession(tmp_path / "backups", "Runway", source)
    assert first.folder != second.folder


def test_replace_service_snapshots_before_edit(tmp_path: Path) -> None:
    folder = tmp_path / "OCD_00001"
    folder.mkdir()
    fed = folder / "FED_00001.xml"
    original = b"\xef\xbb\xbf<FEDRecords><FED><FeatureCtIdx>1</FeatureCtIdx></FED></FEDRecords>"
    fed.write_bytes(original)
    context = OperationContext(
        backup_enabled=True,
        backup_root=tmp_path / "backups",
        backup_label="Replace",
    )
    result = replace_features(ReplaceFeatureRequest(folder, 1, 2), context)
    context.finish_backup(result)

    assert result.status is OperationStatus.SUCCESS
    assert b"FeatureCtIdx>2" in fed.read_bytes()
    assert result.metrics["backup_count"] == 1
    backup = Path(result.metrics["backup_path"])
    assert (backup / "restore" / fed.name).read_bytes() == original


def test_disabled_backup_does_not_create_snapshot(tmp_path: Path) -> None:
    folder = tmp_path / "OCD_00002"
    folder.mkdir()
    fed = folder / "FED_00002.xml"
    fed.write_text("<FEDRecords><FED><FeatureCtIdx>1</FeatureCtIdx></FED></FEDRecords>")
    context = OperationContext(
        backup_enabled=False, backup_root=tmp_path / "backups"
    )
    result = replace_features(ReplaceFeatureRequest(folder, 1, 2), context)
    context.finish_backup(result)
    assert result.status is OperationStatus.SUCCESS
    assert "backup_path" not in result.metrics
    assert not (tmp_path / "backups").exists()

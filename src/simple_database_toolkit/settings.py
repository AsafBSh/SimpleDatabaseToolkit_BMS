"""Machine-local preferences, separate from legacy and development settings."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QSysInfo

from simple_database_toolkit.build_profile import BML_EDITOR_ENABLED


def create_settings(
    *, local_data_root: Path | None = None, owner_id: str | None = None,
) -> QSettings:
    """Use a clean settings scope; never import the old shared registry store."""
    root = local_data_root or Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    ))
    runtime = "release" if getattr(sys, "frozen", False) else "development"
    edition = "full" if BML_EDITOR_ENABLED else "source"
    directory = root / "settings-v2" / f"{runtime}-{edition}"
    directory.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(directory / "settings.ini"), QSettings.Format.IniFormat)
    settings.setFallbacksEnabled(False)
    if owner_id is None:
        machine = bytes(QSysInfo.machineUniqueId()) or QSysInfo.machineHostName().encode()
        owner_id = hashlib.sha256(machine + b"\0" + str(root.resolve()).encode()).hexdigest()
    if settings.value("settings/owner") != owner_id:
        # A copied profile can include foreign paths and backup destinations.
        settings.clear()
        settings.setValue("settings/owner", owner_id)
        settings.sync()
    return settings

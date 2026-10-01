"""Product naming and legacy media discovery."""

from __future__ import annotations

import sys
from pathlib import Path

from simple_database_toolkit.version import __version__


PRODUCT_NAME = "Simple Database Toolkit"
PRODUCT_SUBTITLE = "FALCON BMS DATABASE TOOLS"
APPLICATION_TITLE = f"{PRODUCT_NAME} v{__version__}"


def find_media_asset(filename: str) -> Path | None:
    """Locate media in development and future packaged layouts."""
    source_root = Path(__file__).resolve().parents[4]
    executable_root = Path(sys.executable).resolve().parent
    bundle_root = Path(getattr(sys, "_MEIPASS", executable_root))

    candidates = (
        bundle_root / "Media" / filename,
        executable_root / "Media" / filename,
        source_root / "Media" / filename,
        Path.cwd() / "Media" / filename,
        Path.cwd().parent / "Media" / filename,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None

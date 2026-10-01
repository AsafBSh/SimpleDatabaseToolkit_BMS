"""Technical Console theme loading."""

from __future__ import annotations

import re
from enum import Enum
from importlib.resources import files

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


class ThemeName(str, Enum):
    WHITE = "white"
    GREY = "grey"
    BLACK = "black"


THEME_LABELS = {
    ThemeName.WHITE: "White",
    ThemeName.GREY: "Grey",
    ThemeName.BLACK: "Black",
}


PALETTES: dict[ThemeName, dict[str, str]] = {
    ThemeName.WHITE: {
        "WINDOW": "#f4f6f8",
        "WINDOW_START": "#e7f4ff",
        "WINDOW_END": "#fbfdff",
        "CHROME": "#ffffff",
        "CHROME_START": "#f2f9ff",
        "CHROME_END": "#ffffff",
        "NAV_START": "#ffffff",
        "NAV_END": "#e7f3fc",
        "HERO_START": "#ffffff",
        "HERO_END": "#e5f3ff",
        "PANEL": "#ffffff",
        "PANEL_ALT": "#eef1f4",
        "FIELD": "#ffffff",
        "ALT_ROW": "#f7f9fb",
        "READONLY": "#f0f2f4",
        "BORDER": "#d0d7de",
        "BORDER_STRONG": "#aeb7c2",
        "TEXT": "#24292f",
        "TEXT_BRIGHT": "#111827",
        "MUTED": "#57606a",
        "QUIET": "#6e7781",
        "BUTTON": "#f3f4f6",
        "BUTTON_HOVER": "#e5e7eb",
        "ACCENT": "#0969da",
        "ACCENT_END": "#00a9d6",
        "ACCENT_HOVER": "#075bbf",
        "ON_ACCENT": "#ffffff",
        "SELECTION": "#cfe3fa",
    },
    ThemeName.GREY: {
        "WINDOW": "#cfd4da",
        "WINDOW_START": "#e8edf2",
        "WINDOW_END": "#bcc7d2",
        "CHROME": "#bbc2ca",
        "CHROME_START": "#dde4ea",
        "CHROME_END": "#c5ced7",
        "NAV_START": "#dce3e9",
        "NAV_END": "#b8c5d0",
        "HERO_START": "#e9edf1",
        "HERO_END": "#bdcad5",
        "PANEL": "#dfe3e7",
        "PANEL_ALT": "#c5cbd2",
        "FIELD": "#eef0f2",
        "ALT_ROW": "#e4e7ea",
        "READONLY": "#d5dae0",
        "BORDER": "#9ba4ae",
        "BORDER_STRONG": "#747f8b",
        "TEXT": "#23282f",
        "TEXT_BRIGHT": "#111418",
        "MUTED": "#4e5863",
        "QUIET": "#66717d",
        "BUTTON": "#c8ced5",
        "BUTTON_HOVER": "#b8c0c9",
        "ACCENT": "#245f9e",
        "ACCENT_END": "#268fad",
        "ACCENT_HOVER": "#1d4f85",
        "ON_ACCENT": "#ffffff",
        "SELECTION": "#a9c7e8",
    },
    ThemeName.BLACK: {
        "WINDOW": "#0d1117",
        "WINDOW_START": "#172334",
        "WINDOW_END": "#070a0f",
        "CHROME": "#161b22",
        "CHROME_START": "#182535",
        "CHROME_END": "#11161d",
        "NAV_START": "#172230",
        "NAV_END": "#0c1118",
        "HERO_START": "#1a2737",
        "HERO_END": "#101720",
        "PANEL": "#161b22",
        "PANEL_ALT": "#1f2630",
        "FIELD": "#0d1117",
        "ALT_ROW": "#111820",
        "READONLY": "#161b22",
        "BORDER": "#30363d",
        "BORDER_STRONG": "#48515e",
        "TEXT": "#d8dee9",
        "TEXT_BRIGHT": "#f0f3f6",
        "MUTED": "#9aa4b0",
        "QUIET": "#7d8793",
        "BUTTON": "#21262d",
        "BUTTON_HOVER": "#30363d",
        "ACCENT": "#2f81f7",
        "ACCENT_END": "#00b8d9",
        "ACCENT_HOVER": "#58a6ff",
        "ON_ACCENT": "#ffffff",
        "SELECTION": "#1f3a5b",
    },
}


def normalize_theme(value: object) -> ThemeName:
    if isinstance(value, ThemeName):
        return value
    try:
        return ThemeName(str(value).lower())
    except ValueError:
        return ThemeName.WHITE


def apply_theme(
    application: QApplication,
    theme: ThemeName | str,
) -> ThemeName:
    selected = normalize_theme(theme)
    stylesheet_template = (
        files("simple_database_toolkit.ui")
        .joinpath("styles", "theme_template.qss")
        .read_text(encoding="utf-8")
    )
    stylesheet = stylesheet_template
    for token, color in PALETTES[selected].items():
        stylesheet = stylesheet.replace(f"@{token}@", color)

    unresolved = sorted(set(re.findall(r"@[A-Z_]+@", stylesheet)))
    if unresolved:
        raise ValueError(
            f"Theme contains unresolved tokens: {', '.join(unresolved)}"
        )

    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI", 10))
    application.setStyleSheet(stylesheet)
    application.setProperty("sdt_theme", selected.value)
    return selected


def apply_technical_console_theme(application: QApplication) -> None:
    """Compatibility wrapper for callers that still request the old theme."""
    apply_theme(application, ThemeName.BLACK)

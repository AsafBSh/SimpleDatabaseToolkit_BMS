from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from simple_database_toolkit.ui.theme import (
    PALETTES,
    ThemeName,
    apply_theme,
    normalize_theme,
)


def _application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(["theme-test"])


def test_invalid_theme_falls_back_to_white() -> None:
    assert normalize_theme("not-a-theme") is ThemeName.WHITE
    assert normalize_theme(None) is ThemeName.WHITE


def test_all_theme_palettes_are_complete() -> None:
    expected_tokens = set(PALETTES[ThemeName.WHITE])

    assert expected_tokens
    assert all(set(palette) == expected_tokens for palette in PALETTES.values())


def test_each_theme_resolves_and_applies_all_tokens() -> None:
    application = _application()

    for theme in ThemeName:
        selected = apply_theme(application, theme)

        assert selected is theme
        assert application.property("sdt_theme") == theme.value
        assert "@WINDOW@" not in application.styleSheet()
        assert "@ACCENT@" not in application.styleSheet()
        assert "qlineargradient" in application.styleSheet()

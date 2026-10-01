"""Application bootstrap for Simple Database Toolkit."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from simple_database_toolkit.ui import MainWindow
from simple_database_toolkit.ui.branding import (
    APPLICATION_TITLE,
    PRODUCT_NAME,
    find_media_asset,
)
from simple_database_toolkit.ui.theme import ThemeName, apply_theme
from simple_database_toolkit.version import __version__


def create_application(
    arguments: Sequence[str] | None = None,
) -> tuple[QApplication, MainWindow]:
    args = list(arguments) if arguments is not None else list(sys.argv)
    application = QApplication(args)
    application.setOrganizationName("Falcon BMS")
    application.setOrganizationDomain("falcon-bms.local")
    application.setApplicationName(PRODUCT_NAME)
    application.setApplicationDisplayName(APPLICATION_TITLE)
    application.setApplicationVersion(__version__)
    icon_path = find_media_asset("128_Icon.ico")
    if icon_path is not None:
        application.setWindowIcon(QIcon(str(icon_path)))

    settings = QSettings()
    selected_theme = settings.value(
        "appearance/theme",
        ThemeName.WHITE.value,
    )
    apply_theme(application, str(selected_theme))

    window = MainWindow(settings)
    return application, window


def main(arguments: Sequence[str] | None = None) -> int:
    application, window = create_application(arguments)
    window.show()
    return application.exec()

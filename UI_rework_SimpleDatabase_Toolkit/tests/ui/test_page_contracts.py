from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QSize
from PySide6.QtWidgets import QApplication

from simple_database_toolkit.services import (
    HeadingChoice,
    OffsetMode,
    OffsetOperation,
    ParkingMode,
    ParentMode,
    ReplaceMode,
    RunwayMode,
)
from simple_database_toolkit.ui.components import (
    PathPicker,
    PathSelectionMode,
)
from simple_database_toolkit.ui.main_window import (
    MainWindow,
    recommended_window_size,
)
from simple_database_toolkit.ui.pages import (
    BmlPage,
    DashboardPage,
    FolderCreatorPage,
    LinksPage,
    OffsetPage,
    ParkingPage,
    ParentsPage,
    ReplacePage,
    RunwayPage,
    TutorialPage,
)
from simple_database_toolkit.ui.theme import ThemeName, apply_theme


def _application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(["page-contract-test"])


ALL_PAGE_TYPES = tuple(page_type for page_type in (
    DashboardPage,
    ReplacePage,
    OffsetPage,
    RunwayPage,
    ParkingPage,
    FolderCreatorPage,
    ParentsPage,
    LinksPage,
    BmlPage,
    TutorialPage,
) if page_type is not None)


@pytest.mark.parametrize("page_type", ALL_PAGE_TYPES)
def test_every_page_constructs_with_sanitized_defaults(page_type) -> None:
    _application()
    page = page_type()

    for picker in page.findChildren(PathPicker):
        assert picker.path is None
        assert picker.path_edit.text() == ""
        assert picker.path_edit.placeholderText()
        assert "C:\\Users\\" not in picker.path_edit.placeholderText()

    page.close()
    page.deleteLater()


@pytest.mark.parametrize("theme", tuple(ThemeName))
def test_every_page_renders_under_each_theme(
    tmp_path: Path,
    theme: ThemeName,
) -> None:
    application = _application()
    apply_theme(application, theme)
    settings = QSettings(
        str(tmp_path / f"{theme.value}.ini"),
        QSettings.Format.IniFormat,
    )
    settings.setValue("appearance/theme", theme.value)
    window = MainWindow(settings)

    for page_id, scroll_area in window._pages.items():
        window.show_page(page_id)
        application.processEvents()
        assert window.page_stack.currentWidget() is scroll_area
        assert scroll_area.widget() is not None

    window.close()
    window.deleteLater()


@pytest.mark.parametrize(
    ("page_type", "contracts"),
    (
        (
            ReplacePage,
            (
                (
                    PathSelectionMode.DIRECTORY,
                    "Single OCD objective folder",
                    "OCD_XXXXX containing FED_XXXXX.xml",
                    "Only the matching FED XML",
                ),
                (
                    PathSelectionMode.XML_FILE,
                    "Theater Class Table XML",
                    "beside ObjectiveRelatedData",
                    "ObjectiveRelatedData",
                ),
            ),
        ),
        (
            OffsetPage,
            (
                (
                    PathSelectionMode.DIRECTORY,
                    "Single OCD objective folder",
                    "OCD_XXXXX containing FED_XXXXX.xml",
                    "Only the matching FED XML",
                ),
                (
                    PathSelectionMode.XML_FILE,
                    "Theater Class Table XML",
                    "beside ObjectiveRelatedData",
                    "ObjectiveRelatedData/OCD_*",
                ),
            ),
        ),
        (
            ParentsPage,
            (
                (
                    PathSelectionMode.DAT_FILE,
                    "Exact Parent.dat file",
                    "one exact Parent.dat file",
                    "Only this Parent.dat",
                ),
                (
                    PathSelectionMode.DIRECTORY,
                    "Root folder to search recursively",
                    "every nested Parent.dat",
                    "all subfolders are searched recursively",
                ),
            ),
        ),
        (
            ParkingPage,
            (
                (
                    PathSelectionMode.DIRECTORY,
                    "Single OCD objective folder",
                    "FED_XXXXX.xml and PDX_XXXXX.xml",
                    "Only this objective",
                ),
                (
                    PathSelectionMode.DIRECTORY,
                    "ObjectiveRelatedData folder",
                    "containing OCD_* folders",
                    "immediate OCD_* child folder",
                ),
            ),
        ),
        (
            RunwayPage,
            (
                (
                    PathSelectionMode.DIRECTORY,
                    "Single airbase OCD objective folder",
                    "containing PHD_XXXXX.xml",
                    "Only this objective",
                ),
                (
                    PathSelectionMode.XML_FILE,
                    "Theater Class Table XML",
                    "beside ObjectiveRelatedData",
                    "ObjectiveRelatedData",
                ),
            ),
        ),
    ),
)
def test_mode_selection_updates_the_visible_target_contract(
    page_type,
    contracts,
) -> None:
    application = _application()
    page = page_type()

    for index, (
        expected_mode,
        expected_label,
        expected_placeholder,
        expected_help,
    ) in enumerate(contracts):
        page.mode_combo.setCurrentIndex(index)
        application.processEvents()
        picker = page.target_picker
        assert picker.mode is expected_mode
        assert picker._label_widget.text() == expected_label
        assert expected_placeholder in picker.path_edit.placeholderText()
        assert expected_help in picker._help_widget.text()
        assert not picker._help_widget.isHidden()

    page.close()
    page.deleteLater()


def test_fixed_pickers_explain_exact_inputs_and_outputs() -> None:
    _application()
    pages = [FolderCreatorPage(), LinksPage(), ParkingPage()]
    if BmlPage is not None:
        pages.append(BmlPage())
    combined = "\n".join(
        "\n".join(
            (
                picker._label_widget.text(),
                picker.path_edit.placeholderText(),
                picker._help_widget.text(),
            )
        )
        for page in pages
        for picker in page.findChildren(PathPicker)
    )

    assert "numbered child folders directly inside" in combined
    if BmlPage is not None:
        assert "one model folder containing .bml files" in combined
    assert "Name, Type, Subtype, ID, X, Y, LCount, Links" in combined
    assert "Type 45 hangar records" in combined

    for page in pages:
        page.close()
        page.deleteLater()


def test_all_string_backed_combo_values_round_trip_to_enums() -> None:
    _application()
    pages = (
        ReplacePage(),
        OffsetPage(),
        ParentsPage(),
        ParkingPage(),
        RunwayPage(),
    )
    mode_contracts = (
        (pages[0], (ReplaceMode.SINGLE, ReplaceMode.BATCH)),
        (pages[1], (OffsetMode.SINGLE, OffsetMode.BATCH)),
        (pages[2], (ParentMode.SINGLE, ParentMode.BATCH)),
        (pages[3], (ParkingMode.SINGLE, ParkingMode.BATCH)),
        (pages[4], (RunwayMode.SINGLE, RunwayMode.BATCH)),
    )

    for page, expected_modes in mode_contracts:
        for index, expected in enumerate(expected_modes):
            page.mode_combo.setCurrentIndex(index)
            assert page._selected_mode() is expected

    offset_page = pages[1]
    for index, expected in enumerate(OffsetOperation):
        offset_page.operation_combo.setCurrentIndex(index)
        assert offset_page._selected_operation() is expected

    runway_page = pages[4]
    for index, expected in enumerate(HeadingChoice):
        runway_page.heading_choice_combo.setCurrentIndex(index)
        assert runway_page._selected_choice() is expected

    for page in pages:
        page.close()
        page.deleteLater()


def test_recommended_window_size_is_larger_but_screen_bounded() -> None:
    assert recommended_window_size(QSize(1920, 1080)) == QSize(1400, 900)
    assert recommended_window_size(QSize(1024, 768)) == QSize(992, 736)
    assert recommended_window_size(QSize(800, 600)) == QSize(768, 568)

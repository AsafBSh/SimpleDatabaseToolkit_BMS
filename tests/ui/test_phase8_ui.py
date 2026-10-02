from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLabel

from simple_database_toolkit.ui.branding import APPLICATION_TITLE, PRODUCT_NAME
from simple_database_toolkit.ui.command_palette import CommandPalette
from simple_database_toolkit.ui.main_window import (
    MainWindow,
    normalize_recent_paths,
)
from simple_database_toolkit.ui.pages import DashboardPage, TutorialPage
from simple_database_toolkit.ui.tutorial_content import TUTORIAL_TOPICS
from simple_database_toolkit.version import __version__
from simple_database_toolkit.build_profile import BML_EDITOR_ENABLED


def _application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(["phase8-ui-test"])


def test_tutorial_content_covers_all_operational_pages() -> None:
    count = 9 if BML_EDITOR_ENABLED else 8
    assert len(TUTORIAL_TOPICS) == count
    expected = {
        "overview",
        "replace",
        "offset",
        "runway",
        "parking",
        "folder",
        "parents",
        "links",
        "bml",
    }
    if not BML_EDITOR_ENABLED:
        expected.remove("bml")
    assert {topic.page_id for topic in TUTORIAL_TOPICS} == expected
    assert len({topic.topic_id for topic in TUTORIAL_TOPICS}) == count


def test_tutorial_starts_with_beginner_guide_and_numbered_steps() -> None:
    _application()
    page = TutorialPage()
    assert page._current_topic_id() == "getting-started"
    text = page.document_browser.toPlainText()
    assert "A Class Table is" in text
    assert "RESTORE.txt" in text
    assert "<ol>" in TUTORIAL_TOPICS[0].to_html()
    assert page.open_tool_button.text() == "OPEN OVERVIEW"
    page.search_edit.setText("move an object")
    assert page._current_topic_id() == "offset-fixer"
    page.search_edit.setText("fix a runway")
    assert page._current_topic_id() == "runway-dimension-fixer"


def test_tutorial_search_filters_and_renders_matching_topic() -> None:
    _application()
    page = TutorialPage()

    page.search_edit.setText("CrossingPoint")

    assert page.topic_list.count() == 1
    assert page._current_topic_id() == "runway-dimension-fixer"
    assert "CrossingPoint" in page.document_browser.toPlainText()
    assert "1 topic matched" in page.search_status.text()


def test_tutorial_open_tool_emits_page_destination() -> None:
    _application()
    page = TutorialPage()
    destinations: list[str] = []
    page.navigate_requested.connect(destinations.append)
    assert page.select_topic("parking-fixer")

    page.open_tool_button.click()

    assert destinations == ["parking"]


def test_offset_tutorial_embeds_legacy_alignment_diagram() -> None:
    _application()
    page = TutorialPage()

    assert page.select_topic("offset-fixer")

    assert "tut_1.png" in page.document_browser.toHtml()
    assert "model-center alignment example" in (
        page.document_browser.toPlainText()
    )


def test_command_palette_filters_keywords_and_activates_page() -> None:
    _application()
    palette = CommandPalette()
    destinations: list[str] = []
    palette.page_requested.connect(destinations.append)

    palette.search_edit.setText("texture")

    if not BML_EDITOR_ENABLED:
        assert palette.result_list.count() == 0
        return

    assert palette.result_list.count() == 1
    item = palette.result_list.item(0)
    assert item.data(Qt.ItemDataRole.UserRole) == "bml"
    palette._activate_current()
    assert destinations == ["bml"]


def test_recent_paths_are_trimmed_deduplicated_and_bounded() -> None:
    assert normalize_recent_paths(
        [" A ", "a", "B", "", "C", "D", "E", "F"]
    ) == ("A", "B", "C", "D", "E")
    assert normalize_recent_paths(" single ") == ("single",)
    assert normalize_recent_paths(None) == ()


def test_dashboard_recent_path_empty_and_populated_states() -> None:
    _application()
    page = DashboardPage()

    assert page.recent_list.count() == 1
    assert not page.copy_recent_button.isEnabled()

    page.set_recent_paths(("C:/Falcon/OCD_00001", "C:/Falcon/Parent.dat"))

    assert page.recent_list.count() == 2
    assert page.copy_recent_button.isEnabled()
    assert page.clear_recent_button.isEnabled()


def test_main_window_registers_help_shortcuts_and_always_opens_overview(
    tmp_path: Path,
) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    settings.setValue("navigation/last_page", "runway")

    window = MainWindow(settings)

    assert len(window._pages) == (10 if BML_EDITOR_ENABLED else 9)
    assert window.page_stack.currentWidget() is window._pages["overview"]
    assert len(window._shortcuts) == (11 if BML_EDITOR_ENABLED else 10)
    assert isinstance(window._pages["tutorial"].widget(), TutorialPage)
    window.close()


def test_backup_setting_synchronizes_and_bml_stays_separate(tmp_path: Path) -> None:
    _application()
    settings = QSettings(str(tmp_path / "backups.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings)
    replace_page = window._pages["replace"].widget()
    runway_page = window._pages["runway"].widget()
    bml_page = window._pages["bml"].widget() if BML_EDITOR_ENABLED else None

    assert all(box.isChecked() for box in window._backup_checkboxes)
    window._backup_checkboxes[0].setChecked(False)
    assert not any(box.isChecked() for box in window._backup_checkboxes)
    assert not replace_page.task_controller.backup_enabled
    assert not runway_page.task_controller.backup_enabled
    if bml_page is not None:
        assert not bml_page.backup_checkbox.isChecked()
    assert settings.value("backup/enabled", type=bool) is False
    window.close()


def test_second_page_cannot_start_while_another_page_owns_task(tmp_path: Path) -> None:
    _application()
    settings = QSettings(str(tmp_path / "tasks.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings)
    first = window._pages["replace"].widget()
    second = window._pages["offset"].widget()
    window._active_task_page = first

    assert not second.task_controller.start("Other task", lambda _context: None)
    assert not second.task_controller.is_running
    window._on_task_finished(second)
    assert window._active_task_page is first
    window._active_task_page = None
    window.close()


def test_version_title_context_spacing_and_navigation_footer(
    tmp_path: Path,
) -> None:
    application = _application()
    settings = QSettings(
        str(tmp_path / "branding.ini"),
        QSettings.Format.IniFormat,
    )
    window = MainWindow(settings)
    window.resize(1400, 900)
    window.show()
    application.processEvents()

    assert __version__ == "2.2"
    assert APPLICATION_TITLE == "Simple Database Toolkit v2.2"
    assert window.windowTitle() == APPLICATION_TITLE
    assert "BUILD: 2.2" in {
        label.text() for label in window.findChildren(QLabel)
    }
    assert not any(
        label.text().startswith("BUILD")
        for label in window.navigation.findChildren(QLabel)
    )

    labels = {
        label.text(): label
        for label in window.findChildren(QLabel)
    }
    product = labels[PRODUCT_NAME.upper()]
    profile = labels["PROFILE: DEFAULT"]
    target = labels["TARGET: NOT SELECTED"]
    assert profile.x() - (product.x() + product.width()) >= 28
    assert target.x() - (profile.x() + profile.width()) >= 28
    window.close()

"""Release preferences must not inherit developer or foreign-machine history."""

import sys

from simple_database_toolkit.settings import create_settings


def test_release_starts_clean_and_keeps_its_own_history(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    development = create_settings(local_data_root=tmp_path, owner_id="this-pc")
    development.setValue("recent/target_paths", ["C:/developer/private/model"])
    development.setValue("navigation/last_page", "runway")
    development.setValue("appearance/theme", "Black")
    development.sync()
    monkeypatch.setattr(sys, "frozen", True)
    release = create_settings(local_data_root=tmp_path, owner_id="this-pc")
    assert release.fileName() != development.fileName()
    assert release.value("recent/target_paths", []) == []
    assert release.value("navigation/last_page") is None
    assert release.value("appearance/theme", "White") == "White"
    release.setValue("recent/target_paths", ["C:/user/own/model"])
    release.sync()
    reopened = create_settings(local_data_root=tmp_path, owner_id="this-pc")
    assert reopened.value("recent/target_paths") == ["C:/user/own/model"]


def test_copied_preferences_reset_foreign_paths_and_backup_destination(tmp_path):
    foreign = create_settings(local_data_root=tmp_path, owner_id="other-pc")
    foreign.setValue("recent/target_paths", ["C:/other-pc/model"])
    foreign.setValue("backup/root", "D:/other-pc/backups")
    foreign.setValue("appearance/theme", "Black")
    foreign.sync()
    current = create_settings(local_data_root=tmp_path, owner_id="this-pc")
    assert current.value("recent/target_paths", []) == []
    assert current.value("backup/root") is None
    assert current.value("appearance/theme", "White") == "White"


def test_settings_do_not_read_legacy_registry_fallbacks(tmp_path):
    settings = create_settings(local_data_root=tmp_path, owner_id="this-pc")
    assert not settings.fallbacksEnabled()
    assert settings.format() == settings.Format.IniFormat

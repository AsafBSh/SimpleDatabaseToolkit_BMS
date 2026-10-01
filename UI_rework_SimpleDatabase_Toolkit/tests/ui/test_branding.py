from simple_database_toolkit.ui.branding import (
    PRODUCT_NAME,
    find_media_asset,
)


def test_product_name_is_consistent() -> None:
    assert PRODUCT_NAME == "Simple Database Toolkit"


def test_legacy_home_and_icon_assets_are_available() -> None:
    assert find_media_asset("Main.png") is not None
    assert find_media_asset("128_Icon.ico") is not None
    assert find_media_asset("tut_1.png") is not None

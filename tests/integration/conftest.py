from pathlib import Path

import pytest


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--bms-objects", action="append", default=[],
        help="Installed Objects folder to read; service writes use tmp_path copies.",
    )


def pytest_generate_tests(metafunc) -> None:
    if "theater_root" not in metafunc.fixturenames:
        return
    paths = metafunc.config.getoption("--bms-objects")
    parameters = [Path(value).resolve() for value in paths] or [
        pytest.param(None, marks=pytest.mark.skip(reason="Supply --bms-objects for installed-data tests"))
    ]
    metafunc.parametrize("theater_root", parameters, scope="session")

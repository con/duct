import logging
import os
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_config() -> Generator:
    # set DUCT_SAMPLE_INTERVAL and DUCT_REPORT_INTERVAL to small values
    # to speed up testing etc. Those could be overridden by a specific
    # invocation of .from_args() in a test.
    orig_environ = os.environ.copy()
    os.environ["DUCT_SAMPLE_INTERVAL"] = "0.01"
    os.environ["DUCT_REPORT_INTERVAL"] = "0.1"
    yield
    # May be not even needed, but should not hurt to cleanup.
    # it is not just a dict, so let's explicitly reset it
    for k, v in os.environ.items():
        if k in orig_environ:
            os.environ[k] = v
        else:
            del os.environ[k]


@pytest.fixture(autouse=True)
def reset_logger_state() -> Generator:
    """Automatically reset logger state after each test.

    The execute() function can disable the logger globally when quiet=True
    or log_level="NONE", which affects subsequent tests. This fixture ensures
    the logger is reset to default state after each test.
    """
    import con_duct.duct_main as main_module

    yield

    main_module.lgr.disabled = False
    main_module.lgr.setLevel(logging.INFO)


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> str:
    # Append path separator so that value is recognized as a directory when
    # passed to `output_prefix`
    return str(tmp_path) + os.sep


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Provide a clean environment for testing .env file loading.

    Clears all DUCT_* and TEST_* environment variables to avoid test pollution.
    Returns the monkeypatch instance for setting new env vars in tests.
    """
    for key in list(os.environ.keys()):
        if key.startswith("DUCT_") or key.startswith("TEST_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch

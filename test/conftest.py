import logging
import os
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_config() -> Generator:
    """Set DUCT_CONFIG_PATHS to use fast test config by default.

    Tests that need to opt-out (e.g., config precedence tests) can use
    the no_test_config fixture.
    """
    orig_environ = os.environ.copy()
    test_config = str(Path(__file__).parent / "fixtures" / "test-config.yaml")
    os.environ["DUCT_CONFIG_PATHS"] = test_config
    yield
    # Restore original environment
    for k in list(os.environ.keys()):
        if k in orig_environ:
            os.environ[k] = orig_environ[k]
        else:
            del os.environ[k]


@pytest.fixture
def no_test_config() -> Generator:
    """Opt-out fixture: temporarily remove DUCT_CONFIG_PATHS for tests that need clean config."""
    original_config_paths = os.environ.pop("DUCT_CONFIG_PATHS", None)
    yield
    if original_config_paths is not None:
        os.environ["DUCT_CONFIG_PATHS"] = original_config_paths


@pytest.fixture(autouse=True)
def reset_logger_state() -> Generator:
    """Automatically reset logger state after each test.

    The execute() function can disable the logger globally when quiet=True
    or log_level="NONE", which affects subsequent tests. This fixture ensures
    the logger is reset to default state after each test.
    """
    import con_duct.__main__ as main_module

    yield

    main_module.lgr.disabled = False
    main_module.lgr.setLevel(logging.INFO)


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> str:
    # Append path separator so that value is recognized as a directory when
    # passed to `output_prefix`
    return str(tmp_path) + os.sep

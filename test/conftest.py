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


@pytest.fixture(scope="session", autouse=True)
def disable_drop_young_pids_for_tests() -> Generator:
    """Disable the DROP_YOUNG_PIDS sampler filter for in-process
    tests. Affects only the test process's interpreter; subprocess
    tests (e.g. test_e2e.py) inherit the production default and
    must use commands that outlive ps's 1-second etime quantum.
    """
    import con_duct._sampling as sampling_module

    orig = sampling_module.DROP_YOUNG_PIDS
    sampling_module.DROP_YOUNG_PIDS = False
    yield
    sampling_module.DROP_YOUNG_PIDS = orig


@pytest.fixture
def enable_drop_young_pids(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt back into the production DROP_YOUNG_PIDS filter for a
    single in-process test (used by unit tests in test_sampling.py
    that specifically exercise the drop behavior).

    Only effective for tests that exercise duct via in-process
    Python imports (e.g. test_sampling.py with mocked ps,
    test_execution.py via run_duct_command). Has no effect on
    subprocess-based tests (test_e2e.py), which spawn fresh Python
    interpreters that read DROP_YOUNG_PIDS from _constants.py
    directly. Subprocess tests must instead use workloads that
    outlive ps's 1-second etime quantum if they assert on
    observability under the production default.
    """
    monkeypatch.setattr("con_duct._sampling.DROP_YOUNG_PIDS", True)


@pytest.fixture(autouse=True)
def reset_logger_state() -> Generator:
    """Automatically reset logger state after each test.

    The execute() function can disable the logger globally when quiet=True
    or log_level="NONE", which affects subsequent tests. This fixture ensures
    the logger is reset to default state after each test.
    """
    import con_duct._duct_main as main_module

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

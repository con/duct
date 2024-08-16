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


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> str:
    # Append path separator so that value is recognized as a directory when
    # passed to `output_prefix`
    return str(tmp_path) + os.sep

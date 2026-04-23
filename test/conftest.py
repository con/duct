import json
import logging
import os
from pathlib import Path
from typing import Any, Generator
import pytest

SAMPLER_MATRIX_RESULTS = Path(__file__).parent.parent / ".sampler_matrix_results.jsonl"


def pytest_sessionstart() -> None:
    """Clear stale sampler-matrix results from a previous run."""
    SAMPLER_MATRIX_RESULTS.unlink(missing_ok=True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply xfail(strict=True) to matrix tests marked expected='fail'.

    Sampler-matrix tests express *known limitations* of a sampler against
    a workload/property. Rather than making CI red for those known cells,
    we mark them as expected failures; pytest still runs them (so we
    notice if a sampler improves) but the overall suite stays green.
    """
    for item in items:
        marker = item.get_closest_marker("sampler_matrix")
        if marker is None:
            continue
        if marker.kwargs.get("expected") == "fail":
            item.add_marker(
                pytest.mark.xfail(
                    strict=True,
                    reason="expected sampler/workload limitation",
                )
            )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[Any]
) -> Generator[None, Any, None]:
    """Record each sampler_matrix-marked test's actual outcome to JSONL.

    The *actual* cell value is derived from the raw assertion outcome
    (call.excinfo), not from pytest's post-xfail interpretation: we want
    the CSV to reflect what the sampler actually did, independent of
    whether that matched our committed expectation.

    scripts/gen_sampler_matrix.py pivots the JSONL into one CSV per
    sampler (rows=workload, columns=property, cells=pass|fail|n/a).
    """
    yield
    if call.when != "call":
        return
    marker = item.get_closest_marker("sampler_matrix")
    if marker is None:
        return
    actual = "pass" if call.excinfo is None else "fail"
    record = {
        "sampler": marker.kwargs.get("sampler"),
        "workload": marker.kwargs.get("workload"),
        "property": marker.kwargs.get("property"),
        "expected": marker.kwargs.get("expected"),
        "actual": actual,
        "nodeid": item.nodeid,
    }
    with SAMPLER_MATRIX_RESULTS.open("a") as f:
        f.write(json.dumps(record) + "\n")


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

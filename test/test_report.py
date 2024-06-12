from __future__ import annotations
import subprocess
from unittest.mock import MagicMock, patch
from duct.__main__ import ProcessStats, Report, Sample

stat0 = ProcessStats(
    pcpu=0.0, pmem=0, rss=0, vsz=0, timestamp="2024-06-11T10:09:37-04:00"
)

stat1 = ProcessStats(
    pcpu=1.0, pmem=0, rss=0, vsz=0, timestamp="2024-06-11T10:13:23-04:00"
)


def test_sample_max_initial_values_one_pid() -> None:
    maxes = Sample()
    ex0 = Sample()
    ex0.add(1, stat0)
    maxes = maxes.max(ex0)
    assert maxes.stats == {1: stat0}


def test_sample_max_one_pid() -> None:
    maxes = Sample()
    maxes.add(1, stat0)
    ex1 = Sample()
    ex1.add(1, stat1)
    maxes = maxes.max(ex1)
    assert maxes.stats == {1: stat1}


def test_sample_max_initial_values_two_pids() -> None:
    maxes = Sample()
    ex0 = Sample()
    ex0.add(1, stat0)
    ex0.add(2, stat0)
    maxes = maxes.max(ex0)
    assert maxes.stats == {1: stat0, 2: stat0}


def test_sample_maxtwo_pids() -> None:
    maxes = Sample()
    maxes.add(1, stat0)
    maxes.add(2, stat0)
    ex1 = Sample()
    ex1.add(1, stat1)
    maxes = maxes.max(ex1)
    ex2 = Sample()
    ex2.add(2, stat1)
    maxes = maxes.max(ex2)
    assert maxes.stats == {1: stat1, 2: stat1}


@patch("builtins.open", new_callable=MagicMock)
@patch("duct.__main__.Sample", spec=Sample)
@patch("duct.__main__.clobber_or_clear")
@patch("duct.__main__.subprocess.Popen", spec=subprocess.Popen)
def test_write_pid_samples_set_first_run_only(
    mock_popen: MagicMock,
    mock_clob_or_clear: MagicMock,
    mock_sample: MagicMock,
    mock_open: MagicMock,
    temp_output_dir: str,
) -> None:
    report = Report(
        "mock_cmd",
        ["mock_arg"],
        None,
        temp_output_dir,
        mock_popen,
        "mock_dt",
        clobber=False,
    )
    report._sample = mock_sample
    report._sample.for_json.return_value = {"valid": "dict"}
    assert report._resource_stats_log_path is None
    report.write_pid_samples()
    assert report._resource_stats_log_path is not None
    # mypy says unreachable which is a lie. (_resource_stats_log_path set as side effect of write_pid_samples)
    mock_open.assert_called_once_with(f"{temp_output_dir}usage.json", "a")  # type: ignore
    mock_clob_or_clear.reset_mock()
    report.write_pid_samples()
    mock_clob_or_clear.assert_not_called()

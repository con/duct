from __future__ import annotations
import os
import subprocess
from unittest import mock
from con_duct._duct_main import EXECUTION_SUMMARY_FORMAT
from con_duct._tracker import Report


@mock.patch("con_duct._tracker.LogPaths")
def test_system_info_sanity(mock_log_paths: mock.MagicMock) -> None:
    mock_log_paths.prefix = "mock_prefix"
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, cwd, clobber=False
    )
    report.get_system_info()
    assert report.system_info is not None
    assert report.system_info.hostname
    assert report.system_info.cpu_total
    assert report.system_info.memory_total > 10
    assert report.system_info.uid == os.getuid()
    assert report.system_info.user == os.environ.get("USER")


def test_execution_summary_keys_stable_without_run() -> None:
    """Even with no monitoring, the measurement summary keys are present (None)
    so info.json schema is environment-independent."""
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock.MagicMock(), EXECUTION_SUMMARY_FORMAT, cwd, clobber=False
    )
    summary = report.execution_summary
    for key in (
        "peak_ps_rss_total",
        "ave_ps_rss_total",
        "ps_cpu_seconds",
        "peak_cgroup_rss_peak",
        "peak_psutil_pss_total",
    ):
        assert key in summary
        assert summary[key] is None
    assert summary["num_samples"] == 0
    assert summary["num_reports"] == 0


@mock.patch("con_duct._tracker.shutil.which")
@mock.patch("con_duct._tracker.subprocess.check_output")
@mock.patch("con_duct._tracker.LogPaths")
def test_gpu_parsing_green(
    mock_log_paths: mock.MagicMock, mock_sp: mock.MagicMock, _mock_which: mock.MagicMock
) -> None:
    mock_sp.return_value = (
        "index, name, pci.bus_id, driver_version, memory.total [MiB], compute_mode\n"
        "0, NVIDIA RTX A5500 Laptop GPU, 00000000:01:00.0, 535.183.01, 16384 MiB, Default"
    ).encode("utf-8")
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, cwd, clobber=False
    )
    report.get_system_info()
    assert report.gpus is not None
    assert report.gpus == [
        {
            "index": "0",
            "name": "NVIDIA RTX A5500 Laptop GPU",
            "bus_id": "00000000:01:00.0",
            "driver_version": "535.183.01",
            "memory.total": "16384 MiB",
            "compute_mode": "Default",
        }
    ]


@mock.patch("con_duct._tracker.lgr")
@mock.patch("con_duct._tracker.shutil.which")
@mock.patch("con_duct._tracker.subprocess.check_output")
@mock.patch("con_duct._tracker.LogPaths")
def test_gpu_call_error(
    mock_log_paths: mock.MagicMock,
    mock_sp: mock.MagicMock,
    _mock_which: mock.MagicMock,
    mlgr: mock.MagicMock,
) -> None:
    mock_sp.side_effect = subprocess.CalledProcessError(1, "errrr")
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, cwd, clobber=False
    )
    report.get_system_info()
    assert report.gpus is None
    mlgr.warning.assert_called_once()


@mock.patch("con_duct._tracker.lgr")
@mock.patch("con_duct._tracker.shutil.which")
@mock.patch("con_duct._tracker.subprocess.check_output")
@mock.patch("con_duct._tracker.LogPaths")
def test_gpu_parse_error(
    mock_log_paths: mock.MagicMock,
    mock_sp: mock.MagicMock,
    _mock_which: mock.MagicMock,
    mlgr: mock.MagicMock,
) -> None:
    mock_sp.return_value = (
        "index, name, pci.bus_id, driver_version, memory.total [MiB], compute_mode\n"
        "not-enough-values, 535.183.01, 16384 MiB, Default"
    ).encode("utf-8")
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, cwd, clobber=False
    )
    report.get_system_info()
    assert report.gpus is None
    mlgr.warning.assert_called_once()

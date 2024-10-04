from __future__ import annotations
from collections import Counter
from copy import deepcopy
from datetime import datetime
import os
import subprocess
from unittest import mock
import pytest
from con_duct.__main__ import (
    EXECUTION_SUMMARY_FORMAT,
    Averages,
    ProcessStats,
    Report,
    Sample,
)

stat0 = ProcessStats(
    pcpu=0.0,
    pmem=0,
    rss=0,
    vsz=0,
    timestamp="2024-06-11T10:09:37-04:00",
    etime="00:00",
    cmd="cmd 1",
    stat=Counter(["stat0"]),
)

stat1 = ProcessStats(
    pcpu=1.0,
    pmem=0,
    rss=0,
    vsz=0,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 1",
    stat=Counter(["stat1"]),
)

stat2 = ProcessStats(
    pcpu=1.1,
    pmem=1.1,
    rss=11,
    vsz=11,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 1",
    stat=Counter(["stat2"]),
)


def test_sample_max_initial_values_one_pid() -> None:
    maxes = Sample()
    ex0 = Sample()
    ex0.add_pid(1, deepcopy(stat0))
    maxes = maxes.aggregate(ex0)
    assert maxes.stats == {1: stat0}


def test_sample_max_one_pid() -> None:
    maxes = Sample()
    maxes.add_pid(1, deepcopy(stat0))
    ex1 = Sample()
    ex1.add_pid(1, deepcopy(stat1))
    maxes = maxes.aggregate(ex1)
    assert maxes.stats[1].rss == stat1.rss
    assert maxes.stats[1].vsz == stat1.vsz
    assert maxes.stats[1].pmem == stat1.pmem
    assert maxes.stats[1].pcpu == stat1.pcpu


def test_sample_max_initial_values_two_pids() -> None:
    maxes = Sample()
    ex0 = Sample()
    ex0.add_pid(1, deepcopy(stat0))
    ex0.add_pid(2, deepcopy(stat0))
    maxes = maxes.aggregate(ex0)
    assert maxes.stats == {1: stat0, 2: stat0}
    assert maxes.stats == {1: stat0, 2: stat0}


def test_sample_aggregate_two_pids() -> None:
    maxes = Sample()
    maxes.add_pid(1, deepcopy(stat0))
    maxes.add_pid(2, deepcopy(stat0))
    assert maxes.stats[1].stat["stat0"] == 1
    assert maxes.stats[2].stat["stat0"] == 1
    assert maxes.stats[1].stat["stat1"] == 0
    assert maxes.stats[2].stat["stat1"] == 0
    ex1 = Sample()
    ex1.add_pid(1, deepcopy(stat1))
    maxes = maxes.aggregate(ex1)
    assert maxes.stats[1].stat["stat0"] == 1
    assert maxes.stats[2].stat["stat0"] == 1
    assert maxes.stats[1].stat["stat1"] == 1
    assert maxes.stats[2].stat["stat1"] == 0
    ex2 = Sample()
    ex2.add_pid(2, deepcopy(stat1))
    maxes = maxes.aggregate(ex2)
    # Check the `stat` counts one of each for both pids
    assert maxes.stats[1].stat["stat0"] == 1
    assert maxes.stats[2].stat["stat0"] == 1
    assert maxes.stats[1].stat["stat1"] == 1
    assert maxes.stats[2].stat["stat1"] == 1

    # Each stat1 value > stat0 value
    assert maxes.stats[1].pcpu == stat1.pcpu
    assert maxes.stats[1].pmem == stat1.pmem
    assert maxes.stats[1].rss == stat1.rss
    assert maxes.stats[1].vsz == stat1.vsz
    assert maxes.stats[2].pcpu == stat1.pcpu
    assert maxes.stats[2].pmem == stat1.pmem
    assert maxes.stats[2].rss == stat1.rss
    assert maxes.stats[2].vsz == stat1.vsz


def test_average_no_samples() -> None:
    averages = Averages()
    assert averages.num_samples == 0
    sample = Sample()
    sample.averages = averages
    serialized = sample.for_json()
    assert "averages" in serialized
    assert not serialized["averages"]


def test_averages_one_sample() -> None:
    sample = Sample()
    sample.add_pid(1, deepcopy(stat0))
    averages = Averages.from_sample(sample)
    assert averages.rss == sample.total_rss
    assert averages.vsz == sample.total_vsz
    assert averages.pmem == sample.total_pmem
    assert averages.pcpu == sample.total_pcpu
    assert averages.num_samples == 1


def test_averages_two_samples() -> None:
    sample = Sample()
    sample.add_pid(1, deepcopy(stat0))
    averages = Averages.from_sample(sample)
    sample2 = Sample()
    sample2.add_pid(2, deepcopy(stat1))
    averages.update(sample2)
    assert averages.pcpu == (stat0.pcpu + stat1.pcpu) / 2


def test_averages_three_samples() -> None:
    sample = Sample()
    sample.add_pid(1, deepcopy(stat0))
    averages = Averages.from_sample(sample)
    sample2 = Sample()
    sample2.add_pid(2, deepcopy(stat1))
    averages.update(sample2)
    averages.update(sample2)
    assert averages.pcpu == (stat0.pcpu + (2 * stat1.pcpu)) / 3


def test_sample_totals() -> None:
    sample = Sample()
    sample.add_pid(1, deepcopy(stat2))
    sample.add_pid(2, deepcopy(stat2))
    assert sample.total_rss == stat2.rss * 2
    assert sample.total_vsz == stat2.vsz * 2
    assert sample.total_pmem == stat2.pmem * 2
    assert sample.total_pcpu == stat2.pcpu * 2


@pytest.mark.parametrize(
    "pcpu, pmem, rss, vsz, etime, cmd",
    [
        (1.0, 1.1, 1024, 1025, "00:00", "cmd"),
        (0.5, 0.7, 20.48, 40.96, "00:01", "any"),
        (1, 2, 3, 4, "100:1000", "string"),
        (0, 0.0, 0, 0.0, "999:999:999", "can have spaces"),
        (2.5, 3.5, 8192, 16384, "any", "for --this --kind of thing"),
        (100.0, 99.9, 65536, 131072, "string", "cmd"),
    ],
)
def test_process_stats_green(
    pcpu: float, pmem: float, rss: int, vsz: int, etime: str, cmd: str
) -> None:
    # Assert does not raise
    ProcessStats(
        pcpu=pcpu,
        pmem=pmem,
        rss=rss,
        vsz=vsz,
        timestamp=datetime.now().astimezone().isoformat(),
        etime=etime,
        cmd=cmd,
        stat=Counter(["stat0"]),
    )


@pytest.mark.parametrize(
    "pcpu, pmem, rss, vsz, etime, cmd",
    [
        ("only", 1.1, 1024, 1025, "etime", "cmd"),
        (0.5, "takes", 20.48, 40.96, "some", "str"),
        (1, 2, "one", 4, "anything", "accepted"),
        (1, 2, 3, "value", "etime", "cmd"),
        ("2", "fail", "or", "more", "etime", "cmd"),
    ],
)
def test_process_stats_red(
    pcpu: float, pmem: float, rss: int, vsz: int, etime: str, cmd: str
) -> None:
    with pytest.raises(AssertionError):
        ProcessStats(
            pcpu=pcpu,
            pmem=pmem,
            rss=rss,
            vsz=vsz,
            timestamp=datetime.now().astimezone().isoformat(),
            etime=etime,
            cmd=cmd,
            stat=Counter(["stat0"]),
        )


@mock.patch("con_duct.__main__.LogPaths")
def test_system_info_sanity(mock_log_paths: mock.MagicMock) -> None:
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    report.get_system_info()
    assert report.system_info is not None
    assert report.system_info.hostname
    assert report.system_info.cpu_total
    assert report.system_info.memory_total > 10
    assert report.system_info.uid == os.getuid()
    assert report.system_info.user == os.environ.get("USER")


@mock.patch("con_duct.__main__.shutil.which")
@mock.patch("con_duct.__main__.subprocess.check_output")
@mock.patch("con_duct.__main__.LogPaths")
def test_gpu_parsing_green(
    mock_log_paths: mock.MagicMock, mock_sp: mock.MagicMock, _mock_which: mock.MagicMock
) -> None:
    mock_sp.return_value = (
        "index, name, pci.bus_id, driver_version, memory.total [MiB], compute_mode\n"
        "0, NVIDIA RTX A5500 Laptop GPU, 00000000:01:00.0, 535.183.01, 16384 MiB, Default"
    ).encode("utf-8")
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
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


@mock.patch("con_duct.__main__.lgr")
@mock.patch("con_duct.__main__.shutil.which")
@mock.patch("con_duct.__main__.subprocess.check_output")
@mock.patch("con_duct.__main__.LogPaths")
def test_gpu_call_error(
    mock_log_paths: mock.MagicMock,
    mock_sp: mock.MagicMock,
    _mock_which: mock.MagicMock,
    mlgr: mock.MagicMock,
) -> None:
    mock_sp.side_effect = subprocess.CalledProcessError(1, "errrr")
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    report.get_system_info()
    assert report.gpus is None
    mlgr.warning.assert_called_once()


@mock.patch("con_duct.__main__.lgr")
@mock.patch("con_duct.__main__.shutil.which")
@mock.patch("con_duct.__main__.subprocess.check_output")
@mock.patch("con_duct.__main__.LogPaths")
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
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    report.get_system_info()
    assert report.gpus is None
    mlgr.warning.assert_called_once()

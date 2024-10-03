from collections import Counter
from copy import deepcopy
from typing import cast
from unittest import mock
import pytest
from con_duct.__main__ import EXECUTION_SUMMARY_FORMAT, ProcessStats, Report, Sample

stat0 = ProcessStats(
    pcpu=0.0,
    pmem=0,
    rss=0,
    vsz=0,
    timestamp="2024-06-11T10:09:37-04:00",
    etime="00:00",
    cmd="cmd 0",
    stat=Counter(["stat0"]),
)

stat1 = ProcessStats(
    pcpu=1.0,
    pmem=1.0,
    rss=1,
    vsz=1,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 1",
    stat=Counter(["stat1"]),
)

stat2 = ProcessStats(
    pcpu=2.0,
    pmem=2.0,
    rss=2,
    vsz=2,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 2",
    stat=Counter(["stat2"]),
)

stat100 = ProcessStats(
    pcpu=100.0,
    pmem=100.0,
    rss=2,
    vsz=2,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 100",
    stat=Counter(["stat100"]),
)
stat_big = ProcessStats(
    pcpu=20000.0,
    pmem=21234234.0,
    rss=43645634562,
    vsz=2345234523452342,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 2",
    stat=Counter(["statbig"]),
)


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_num_samples_increment(mock_log_paths: mock.MagicMock) -> None:
    ex0 = Sample()
    ex0.add_pid(1, deepcopy(stat1))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.current_sample.averages.num_samples == 1
    assert report.full_run_stats.averages.num_samples == 1
    report.update_from_sample(ex0)
    assert report.current_sample.averages.num_samples == 2
    assert report.full_run_stats.averages.num_samples == 2
    report.update_from_sample(ex0)
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 3


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_single_sample_sanity(mock_log_paths: mock.MagicMock) -> None:
    ex0 = Sample()
    ex0.add_pid(0, deepcopy(stat0))
    ex0.add_pid(1, deepcopy(stat1))
    ex0.add_pid(2, deepcopy(stat2))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
    # 3 pids in a single sample should still be "1" sample
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.full_run_stats is not None
    assert report.current_sample.averages.num_samples == 1
    assert report.full_run_stats.averages.num_samples == 1

    # assert totals sanity
    assert report.current_sample.total_rss == stat0.rss + stat1.rss + stat2.rss
    assert report.current_sample.total_vsz == stat0.vsz + stat1.vsz + stat2.vsz
    assert report.current_sample.total_pmem == stat0.pmem + stat1.pmem + stat2.pmem
    assert report.current_sample.total_pcpu == stat0.pcpu + stat1.pcpu + stat2.pcpu

    # With one sample averages should be equal to totals
    assert report.current_sample.averages.rss == report.current_sample.averages.rss
    assert report.current_sample.averages.vsz == report.current_sample.averages.vsz
    assert report.current_sample.averages.pmem == report.current_sample.averages.pmem
    assert report.current_sample.averages.pcpu == report.current_sample.averages.pcpu


@pytest.mark.parametrize("stat", [stat0, stat1, stat2, stat_big])
@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_single_stat_multiple_samples_sanity(
    mock_log_paths: mock.MagicMock, stat: ProcessStats
) -> None:
    ex0 = Sample()
    ex0.add_pid(1, deepcopy(stat))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
    report.update_from_sample(ex0)
    report.update_from_sample(ex0)
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 3

    # With 3 identical samples, totals should be identical to 1 sample
    assert report.current_sample.total_rss == stat.rss
    assert report.current_sample.total_vsz == stat.vsz
    assert report.current_sample.total_pmem == stat.pmem
    assert report.current_sample.total_pcpu == stat.pcpu

    # Without resetting the current sample, full_run_stats should equal current_sample
    assert report.full_run_stats.total_rss == report.current_sample.total_rss
    assert report.full_run_stats.total_vsz == report.current_sample.total_vsz
    assert report.full_run_stats.total_pmem == report.current_sample.total_pmem
    assert report.full_run_stats.total_pcpu == report.current_sample.total_pcpu
    # Averages too
    assert report.current_sample.averages.rss == report.full_run_stats.averages.rss
    assert report.current_sample.averages.vsz == report.full_run_stats.averages.vsz
    assert report.current_sample.averages.pmem == report.full_run_stats.averages.pmem
    assert report.current_sample.averages.pcpu == report.full_run_stats.averages.pcpu

    # With 3 identical samples, averages should be identical to 1 sample
    assert report.current_sample.averages.rss == report.current_sample.total_rss
    assert report.current_sample.averages.vsz == report.current_sample.total_vsz
    assert report.current_sample.averages.pmem == report.current_sample.total_pmem
    assert report.current_sample.averages.pcpu == report.current_sample.total_pcpu


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_averages(mock_log_paths: mock.MagicMock) -> None:
    sample0 = Sample()
    sample0.add_pid(1, deepcopy(stat0))
    sample1 = Sample()
    sample1.add_pid(1, deepcopy(stat1))
    sample2 = Sample()
    sample2.add_pid(1, deepcopy(stat2))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(sample0)
    report.update_from_sample(sample1)
    report.update_from_sample(sample2)
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 3

    # Assert that average calculation works as expected
    assert (
        report.current_sample.averages.rss == (stat0.rss + stat1.rss + stat2.rss) / 3.0
    )
    assert (
        report.current_sample.averages.vsz == (stat0.vsz + stat1.vsz + stat2.vsz) / 3.0
    )
    assert (
        report.current_sample.averages.pmem
        == (stat0.pmem + stat1.pmem + stat2.pmem) / 3.0
    )
    assert (
        report.current_sample.averages.pcpu
        == (stat0.pcpu + stat1.pcpu + stat2.pcpu) / 3.0
    )
    # And full_run_stats.averages is still identical
    assert report.current_sample.averages.rss == report.full_run_stats.averages.rss
    assert report.current_sample.averages.vsz == report.full_run_stats.averages.vsz
    assert report.current_sample.averages.pmem == report.full_run_stats.averages.pmem
    assert report.current_sample.averages.pcpu == report.full_run_stats.averages.pcpu

    # Lets make the arithmetic a little less round
    report.update_from_sample(sample2)
    report.update_from_sample(sample2)
    report.update_from_sample(sample2)
    assert report.current_sample.averages.num_samples == 6
    assert report.full_run_stats.averages.num_samples == 6
    assert (
        report.current_sample.averages.rss
        == (stat0.rss + stat1.rss + stat2.rss * 4) / 6.0
    )
    assert (
        report.current_sample.averages.vsz
        == (stat0.vsz + stat1.vsz + stat2.vsz * 4) / 6.0
    )
    assert (
        report.current_sample.averages.pmem
        == (stat0.pmem + stat1.pmem + stat2.pmem * 4) / 6.0
    )
    assert (
        report.current_sample.averages.pcpu
        == (stat0.pcpu + stat1.pcpu + stat2.pcpu * 4) / 6.0
    )


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_current_ave_diverges_from_total_ave(
    mock_log_paths: mock.MagicMock,
) -> None:
    sample0 = Sample()
    sample0.add_pid(1, deepcopy(stat0))
    sample1 = Sample()
    sample1.add_pid(1, deepcopy(stat1))
    sample2 = Sample()
    sample2.add_pid(1, deepcopy(stat2))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(sample0)
    report.update_from_sample(sample1)
    report.update_from_sample(sample2)
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 3
    # full_run_stats.averages is still identical to current_sample
    assert report.current_sample.averages.rss == report.full_run_stats.averages.rss
    assert report.current_sample.averages.vsz == report.full_run_stats.averages.vsz
    assert report.current_sample.averages.pmem == report.full_run_stats.averages.pmem
    assert report.current_sample.averages.pcpu == report.full_run_stats.averages.pcpu

    # Reset current_sample so averages will diverge from full_run_stats.averages
    report.current_sample = None
    report.update_from_sample(sample2)
    report.update_from_sample(sample2)
    report.update_from_sample(sample2)
    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 6

    # Current sample should only contain sample2
    assert report.current_sample.averages.rss == sample2.total_rss
    assert report.current_sample.averages.vsz == sample2.total_vsz
    assert report.current_sample.averages.pmem == sample2.total_pmem
    assert report.current_sample.averages.pcpu == sample2.total_pcpu

    # Full sample average should == (samples_sum/num_samples)
    assert (
        report.full_run_stats.averages.rss
        == (stat0.rss + stat1.rss + stat2.rss * 4) / 6.0
    )
    assert (
        report.full_run_stats.averages.vsz
        == (stat0.vsz + stat1.vsz + stat2.vsz * 4) / 6.0
    )
    assert (
        report.full_run_stats.averages.pmem
        == (stat0.pmem + stat1.pmem + stat2.pmem * 4) / 6.0
    )
    assert (
        report.full_run_stats.averages.pcpu
        == (stat0.pcpu + stat1.pcpu + stat2.pcpu * 4) / 6.0
    )


@pytest.mark.parametrize("stat", [stat0, stat1, stat2, stat_big])
@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_many_samples(
    mock_log_paths: mock.MagicMock, stat: ProcessStats
) -> None:
    sample1 = Sample()
    pid = 1
    sample1.add_pid(pid, deepcopy(stat))
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0

    # Ensure nothing strange happens after many updates
    for _ in range(100):
        report.update_from_sample(sample1)

    report.current_sample = cast(
        Sample, report.current_sample
    )  # So mypy is convcinced it is not None
    assert report.current_sample is not None
    # Assert that there is exactly 1 ProcessStat.stat count per update
    assert (
        sum(report.current_sample.stats[pid].stat.values())
        == report.full_run_stats.averages.num_samples
        == 100
    )
    assert report.full_run_stats.averages.rss == (stat.rss * 100) / 100.0
    assert report.full_run_stats.averages.vsz == (stat.vsz * 100) / 100.0
    assert report.full_run_stats.averages.pmem == (stat.pmem * 100) / 100.0
    assert report.full_run_stats.averages.pcpu == (stat.pcpu * 100) / 100.0

    # Add a stat that is not 0 and check that the average is still correct
    sample2 = Sample()
    sample2.add_pid(1, deepcopy(stat2))
    report.update_from_sample(sample2)
    assert report.full_run_stats.averages.num_samples == 101
    assert report.full_run_stats.averages.rss == (stat.rss * 100 + stat2.rss) / 101.0
    assert report.full_run_stats.averages.vsz == (stat.vsz * 100 + stat2.vsz) / 101.0
    assert report.full_run_stats.averages.pmem == (stat.pmem * 100 + stat2.pmem) / 101.0
    assert report.full_run_stats.averages.pcpu == (stat.pcpu * 100 + stat2.pcpu) / 101.0


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_sample_no_pids(mock_log_paths: mock.MagicMock) -> None:
    sample0 = Sample()
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    # When there are no pids, finalization should be triggered because the exe is finished,
    # so a Sample with no PIDs should never be passed to update_from_sample.
    with pytest.raises(AssertionError):
        report.update_from_sample(sample0)


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_no_false_peak(mock_log_paths: mock.MagicMock) -> None:
    sample1 = Sample()
    sample2 = Sample()
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    sample1.add_pid(1, deepcopy(stat100))
    sample1.add_pid(2, deepcopy(stat0))
    report.update_from_sample(sample1)
    sample2.add_pid(1, deepcopy(stat0))
    sample2.add_pid(2, deepcopy(stat100))
    report.update_from_sample(sample2)
    assert report.current_sample is not None
    assert report.current_sample.total_pcpu == 100

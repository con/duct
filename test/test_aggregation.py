from unittest import mock
from con_duct.__main__ import EXECUTION_SUMMARY_FORMAT, ProcessStats, Report, Sample

stat0 = ProcessStats(
    pcpu=0.0,
    pmem=0,
    rss=0,
    vsz=0,
    timestamp="2024-06-11T10:09:37-04:00",
    etime="00:00",
    cmd="cmd 0",
    stat="stat0",
)

stat1 = ProcessStats(
    pcpu=1.0,
    pmem=1.0,
    rss=1,
    vsz=1,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 1",
    stat="stat1",
)

stat2 = ProcessStats(
    pcpu=2.0,
    pmem=2.0,
    rss=2,
    vsz=2,
    timestamp="2024-06-11T10:13:23-04:00",
    etime="00:02",
    cmd="cmd 2",
    stat="stat2",
)


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_num_samples_increment(mock_log_paths: mock.MagicMock) -> None:
    ex0 = Sample()
    ex0.add_pid(1, stat1)
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
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
    ex0.add_pid(0, stat0)
    ex0.add_pid(1, stat1)
    ex0.add_pid(2, stat2)
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
    # 3 pids in a single sample should still be "1" sample
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


@mock.patch("con_duct.__main__.LogPaths")
def test_aggregation_multiple_samples_sanity(mock_log_paths: mock.MagicMock) -> None:
    ex0 = Sample()
    ex0.add_pid(1, stat1)
    mock_log_paths.prefix = "mock_prefix"
    report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
    assert report.current_sample is None
    assert report.full_run_stats.averages.num_samples == 0
    report.update_from_sample(ex0)
    report.update_from_sample(ex0)
    report.update_from_sample(ex0)
    assert report.current_sample.averages.num_samples == 3
    assert report.full_run_stats.averages.num_samples == 3

    # With 3 identical samples, totals should be identical to 1 sample
    assert report.current_sample.total_rss == stat1.rss
    assert report.current_sample.total_vsz == stat1.vsz
    assert report.current_sample.total_pmem == stat1.pmem
    assert report.current_sample.total_pcpu == stat1.pcpu

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

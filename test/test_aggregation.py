# from unittest import mock
# from con_duct.__main__ import EXECUTION_SUMMARY_FORMAT, Report, Sample
#
# sample1 = S
#
#
# @mock.patch("con_duct.__main__.Report.collect_sample")
# @mock.patch("con_duct.__main__.LogPaths")
# def test_aggregation_sanity(
#     mock_log_paths: mock.MagicMock, mock_sample_collect
# ) -> None:
#     mock_sample_collect.side_effect = ["a", "b", "c", "d"]
#     mock_log_paths.prefix = "mock_prefix"
#     report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
#     for _ in range(4):
#         print(report.collect_sample())

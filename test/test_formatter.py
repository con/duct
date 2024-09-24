# from con_duct.__main__ import SUFFIXES, Arguments, Outputs, execute, Report, EXECUTION_SUMMARY_FORMAT
from con_duct.__main__ import SummaryFormatter

# @mock.patch("con_duct.__main__.LogPaths")
# @mock.patch("con_duct.__main__.subprocess.Popen")
# def test_execution_summary_formatted_e2e(
#     mock_popen: mock.MagicMock, mock_log_paths: mock.MagicMock
# ) -> None:
#     mock_log_paths.prefix = "mock_prefix"
#     report = Report("_cmd", [], mock_log_paths, EXECUTION_SUMMARY_FORMAT, clobber=False)
#     # It should not crash and it would render even where no wallclock time yet
#     assert report.execution_summary_formatted is not None
#     import ipdb; ipdb.set_trace()
#     assert "wall clock time: nan" in report.execution_summary_formatted.lower()
#
#     # Test with process
#     report.process = mock_popen
#     report.process.returncode = 0
#     output = report.execution_summary_formatted
#     assert "None" not in output
#     assert "unknown" in output
#     # Process did not finish, we didn't set start_time, so remains nan but there
#     assert "wall clock time: nan" in report.execution_summary_formatted.lower()


def test_summary_formatter_no_vars() -> None:
    not_really_format_string = "test"
    no_args = {}
    formatter = SummaryFormatter()
    out = formatter.format(not_really_format_string, **no_args)
    assert out == not_really_format_string


def test_summary_formatter_vars_provided_no_vars_in_format_string() -> None:
    not_really_format_string = "test"
    one_arg = {"ok": "pass"}
    formatter = SummaryFormatter()
    out = formatter.format(not_really_format_string, **one_arg)
    assert out == not_really_format_string


def test_summary_formatter_one_var() -> None:
    valid_format_string = "test {ok}"
    one_arg = {"ok": "pass"}
    formatter = SummaryFormatter()
    out = formatter.format(valid_format_string, **one_arg)
    assert out == "test pass"


def test_summary_formatter_many_vars() -> None:
    valid_format_string = "{one} {two} {three} {four} {five}"
    many_args = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
    formatter = SummaryFormatter()
    out = formatter.format(valid_format_string, **many_args)
    assert out == "1 2 3 4 5"


def test_summary_formatter_missing_vars() -> None:
    # assert False
    assert True


def test_summary_formatter_none_replacement() -> None:
    valid_format_string = "test {none}"
    one_arg = {"none": None}
    formatter = SummaryFormatter()
    out = formatter.format(valid_format_string, **one_arg)
    assert out == "test -"


def test_summary_formatter_S_e2e() -> None:
    formatter = SummaryFormatter()
    one_arg = {"big_num": 100000}

    valid_format_string = "test {big_num}"
    no_s_applied = formatter.format(valid_format_string, **one_arg)
    assert no_s_applied == "test 100000"

    s_format_string = "test {big_num!S}"
    s_applied = formatter.format(s_format_string, **one_arg)
    assert s_applied == "test 100.0 kB"

    none_applied = formatter.format(s_format_string, **{"big_num": None})
    assert none_applied == "test -"


def test_summary_formatter_S_e2e_colors() -> None:
    formatter = SummaryFormatter(enable_colors=True)
    s_format_string = "test {big_num!S}"
    GREEN_START = formatter.COLOR_SEQ % formatter.GREEN
    # RED_START = formatter.COLOR_SEQ % formatter.RED

    zero_applied = formatter.format(s_format_string, **{"big_num": 0})
    assert zero_applied != "test 0 Bytes"
    expected = f"test {GREEN_START}0 Bytes{formatter.RESET_SEQ}"
    assert expected == zero_applied

    ten_5 = formatter.format(s_format_string, **{"big_num": 100000})
    expected = f"test {GREEN_START}100.0 kB{formatter.RESET_SEQ}"
    assert expected == ten_5
    #
    # num_applied_c = formatter.format(s_format_string, **one_arg)
    # assert "test 100.0 kB" in num_applied_c
    #
    # zero_applied_c = formatter.format(s_format_string, **{"big_num": 0})
    # assert "test 0 Bytes" zero_applied_c ==

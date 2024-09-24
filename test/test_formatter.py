# from con_duct.__main__ import SUFFIXES, Arguments, Outputs, execute, Report, EXECUTION_SUMMARY_FORMAT
import pytest
from con_duct.__main__ import SummaryFormatter

GREEN_START = SummaryFormatter.COLOR_SEQ % SummaryFormatter.GREEN
RED_START = SummaryFormatter.COLOR_SEQ % SummaryFormatter.RED

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
    valid_format_string = "{one}"
    formatter = SummaryFormatter()
    with pytest.raises(KeyError):
        formatter.format(valid_format_string, **{})

    valid_format_string = "{one} {two}"
    formatter = SummaryFormatter()
    with pytest.raises(KeyError):
        formatter.format(valid_format_string, **{"one": 1})


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

    zero_applied = formatter.format(s_format_string, **{"big_num": 0})
    assert zero_applied != "test 0 Bytes"
    expected = f"test {GREEN_START}0 Bytes{formatter.RESET_SEQ}"
    assert expected == zero_applied

    ten_5 = formatter.format(s_format_string, **{"big_num": 100000})
    expected = f"test {GREEN_START}100.0 kB{formatter.RESET_SEQ}"
    assert expected == ten_5

    zero_applied_c = formatter.format(s_format_string, **{"big_num": 0})
    expected = f"test {GREEN_START}0 Bytes{formatter.RESET_SEQ}"
    assert expected == zero_applied_c

    none_applied_c = formatter.format(s_format_string, **{"big_num": None})
    expected = f"test {RED_START}-{formatter.RESET_SEQ}"
    assert expected == none_applied_c


def test_summary_formatter_E_e2e() -> None:
    formatter = SummaryFormatter()

    valid_format_string = "test {e}"
    no_e_applied = formatter.format(valid_format_string, **{"e": 1})
    assert no_e_applied == "test 1"

    e_format_string = "test {e!E}"
    e_applied = formatter.format(e_format_string, **{"e": 1})
    assert e_applied == "test 1"

    e_format_string = "test {e!E}"
    e_zero_applied = formatter.format(e_format_string, **{"e": 0})
    assert e_zero_applied == "test 0"


def test_summary_formatter_E_e2e_colors() -> None:
    formatter = SummaryFormatter(enable_colors=True)

    valid_format_string = "test {e}"
    no_e_applied = formatter.format(valid_format_string, **{"e": 1})
    assert no_e_applied == "test 1"

    e_format_string = "test {e!E}"

    # Test Red truthy
    e_applied = formatter.format(e_format_string, **{"e": 1})
    assert e_applied == f"test {RED_START}1{formatter.RESET_SEQ}"

    # Test Green falsey
    e_zero_applied = formatter.format(e_format_string, **{"e": 0})
    assert e_zero_applied == f"test {GREEN_START}0{formatter.RESET_SEQ}"


def test_summary_formatter_X_e2e() -> None:
    formatter = SummaryFormatter()

    valid_format_string = "test {x}"
    no_x_applied = formatter.format(valid_format_string, **{"x": 1})
    assert no_x_applied == "test 1"

    x_format_string = "test {x!X}"

    x_applied = formatter.format(x_format_string, **{"x": 1})
    assert x_applied == "test 1"

    x_zero_applied = formatter.format(x_format_string, **{"x": 0})
    assert x_zero_applied == "test 0"


def test_summary_formatter_X_e2e_colors() -> None:
    formatter = SummaryFormatter(enable_colors=True)

    valid_format_string = "test {x}"
    no_x_applied = formatter.format(valid_format_string, **{"x": 1})
    assert no_x_applied == "test 1"

    x_format_string = "test {x!X}"

    # Test Green truthy
    x_applied = formatter.format(x_format_string, **{"x": 1})
    assert x_applied == f"test {GREEN_START}1{formatter.RESET_SEQ}"

    # Test Red falsey
    x_zero_applied = formatter.format(x_format_string, **{"x": 0})
    assert x_zero_applied == f"test {RED_START}0{formatter.RESET_SEQ}"

    # Test Red None
    x_zero_applied = formatter.format(x_format_string, **{"x": None})
    assert x_zero_applied == f"test {RED_START}-{formatter.RESET_SEQ}"

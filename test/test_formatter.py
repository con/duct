from unittest import mock
import pytest
from con_duct.__main__ import Report, SummaryFormatter

GREEN_START = SummaryFormatter.COLOR_SEQ % SummaryFormatter.GREEN
RED_START = SummaryFormatter.COLOR_SEQ % SummaryFormatter.RED


@mock.patch("con_duct.__main__.LogPaths")
@mock.patch("con_duct.__main__.subprocess.Popen")
def test_execution_summary_formatted_wall_clock_time_nan(
    mock_popen: mock.MagicMock, mock_log_paths: mock.MagicMock
) -> None:
    mock_log_paths.prefix = "mock_prefix"
    wall_clock_format_string = "Wall Clock Time: {wall_clock_time:.3f} sec\n"
    report = Report("_cmd", [], mock_log_paths, wall_clock_format_string, clobber=False)
    # It should not crash and it would render even where no wallclock time yet
    assert report.execution_summary_formatted is not None
    assert "wall clock time: nan" in report.execution_summary_formatted.lower()

    # Test with process
    report.process = mock_popen
    report.process.returncode = 0
    output = report.execution_summary_formatted
    assert "None" not in output
    # Process did not finish, we didn't set start_time, so remains nan but there
    assert "wall clock time: nan" in report.execution_summary_formatted.lower()


@mock.patch("con_duct.__main__.LogPaths")
@mock.patch("con_duct.__main__.subprocess.Popen")
def test_execution_summary_formatted_wall_clock_time_rounded(
    mock_popen: mock.MagicMock, mock_log_paths: mock.MagicMock
) -> None:
    mock_log_paths.prefix = "mock_prefix"
    wall_clock_format_string = "{wall_clock_time:.3f}"
    report = Report("_cmd", [], mock_log_paths, wall_clock_format_string, clobber=False)
    report.process = mock_popen
    report.process.returncode = 0
    report.start_time = 1727221840.0486171
    report.end_time = report.start_time + 1.111111111
    assert "1.111" == report.execution_summary_formatted


def test_summary_formatter_no_vars() -> None:
    not_really_format_string = "test"
    formatter = SummaryFormatter()
    out = formatter.format(not_really_format_string, **{})
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


# YB -> ZB rollover https://github.com/python-humanize/humanize/issues/205
@pytest.mark.parametrize(
    "num,expected",
    [
        [1, "1 Byte"],
        [10, "10 Bytes"],
        [100, "100 Bytes"],
        [1000, "1.0 kB"],
        [10000, "10.0 kB"],
        [100000, "100.0 kB"],
        [1000000, "1.0 MB"],
        [10000000, "10.0 MB"],
        [100000000, "100.0 MB"],
        [1000000000, "1.0 GB"],
        [10000000000, "10.0 GB"],
        [100000000000, "100.0 GB"],
        [1000000000000, "1.0 TB"],
        [10000000000000, "10.0 TB"],
        [100000000000000, "100.0 TB"],
        [1000000000000000, "1.0 PB"],
        [10000000000000000, "10.0 PB"],
        [100000000000000000, "100.0 PB"],
        [1000000000000000000, "1.0 EB"],
        [10000000000000000000, "10.0 EB"],
        [100000000000000000000, "100.0 EB"],
        [1000000000000000000000, "1.0 ZB"],
        [10000000000000000000000, "10.0 ZB"],
        [100000000000000000000000, "100.0 ZB"],
        [1000000000000900000000000, "1.0 YB"],  # see issue above
        [10000000000000000000000000, "10.0 YB"],
        [100000000000000000000000000, "100.0 YB"],
        [1000000000000000000000000000, "1000.0 YB"],
    ],
)
def test_summary_formatter_S_sizes(num: int, expected: str) -> None:
    formatter = SummaryFormatter()
    format_string = "{num!S}"
    actual = formatter.format(format_string, **{"num": num})
    assert actual == expected


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

    # # Test Red None
    e_none_applied = formatter.format(e_format_string, **{"e": None})
    assert e_none_applied == f"test {RED_START}-{formatter.RESET_SEQ}"


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

    x_none_applied = formatter.format(x_format_string, **{"x": None})
    assert x_none_applied == "test -"


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


def test_summary_formatter_N_e2e() -> None:
    formatter = SummaryFormatter()

    valid_format_string = "test {n}"
    no_n_applied = formatter.format(valid_format_string, **{"n": 1})
    assert no_n_applied == "test 1"

    n_format_string = "test {n!N}"

    n_applied = formatter.format(n_format_string, **{"n": 1})
    assert n_applied == "test 1"

    n_zero_applied = formatter.format(n_format_string, **{"n": 0})
    assert n_zero_applied == "test 0"

    n_none_applied = formatter.format(n_format_string, **{"n": None})
    assert n_none_applied == "test -"


def test_summary_formatter_N_e2e_colors() -> None:
    formatter = SummaryFormatter(enable_colors=True)

    valid_format_string = "test {n}"
    no_n_applied = formatter.format(valid_format_string, **{"n": 1})
    assert no_n_applied == "test 1"

    no_n_applied = formatter.format(valid_format_string, **{"n": None})
    assert no_n_applied == "test -"

    n_format_string = "test {n!N}"

    # Test Green truthy
    n_applied = formatter.format(n_format_string, **{"n": 1})
    assert n_applied == f"test {GREEN_START}1{formatter.RESET_SEQ}"

    # Test Green falsey
    n_zero_applied = formatter.format(n_format_string, **{"n": 0})
    assert n_zero_applied == f"test {GREEN_START}0{formatter.RESET_SEQ}"

    # Test Red None
    n_zero_applied = formatter.format(n_format_string, **{"n": None})
    assert n_zero_applied == f"test {RED_START}-{formatter.RESET_SEQ}"


@mock.patch("con_duct.__main__.LogPaths")
@mock.patch("con_duct.__main__.subprocess.Popen")
def test_execution_summary_formatted_wall_clock_time_invalid(
    mock_popen: mock.MagicMock, mock_log_paths: mock.MagicMock
) -> None:
    mock_log_paths.prefix = "mock_prefix"
    wall_clock_format_string = "Invalid rounding of string: {wall_clock_time:.3f!X}"
    report = Report("_cmd", [], mock_log_paths, wall_clock_format_string, clobber=False)
    # It should not crash and it would render even where no wallclock time yet
    report.process = mock_popen
    report.process.returncode = 0
    report.start_time = 1727221840.0486171
    report.end_time = report.start_time + 1.111111111

    # Assert ValueError not raised
    assert (
        "Invalid rounding of string: 1.1111111640930176"
        == report.execution_summary_formatted
    )

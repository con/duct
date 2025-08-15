import os
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
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, wall_clock_format_string, cwd, clobber=False
    )
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
    cwd = os.getcwd()
    report = Report(
        "_cmd", [], mock_log_paths, wall_clock_format_string, cwd, clobber=False
    )
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
@pytest.mark.parametrize("colors", [True, False])
def test_execution_summary_formatted_wall_clock_time_nowvalid(
    mock_popen: mock.MagicMock, mock_log_paths: mock.MagicMock, colors: bool
) -> None:
    mock_log_paths.prefix = "mock_prefix"
    wall_clock_format_string = "Rendering: {wall_clock_time:.3f!X}"
    cwd = os.getcwd()
    report = Report(
        "_cmd",
        [],
        mock_log_paths,
        wall_clock_format_string,
        cwd,
        clobber=False,
        colors=colors,
    )
    report.process = mock_popen
    report.process.returncode = 0
    report.start_time = 1727221840.0486171
    report.end_time = report.start_time + 1.111111111

    if colors:
        GREEN, STOP = GREEN_START, SummaryFormatter.RESET_SEQ
    else:
        GREEN, STOP = "", ""

    # Assert ValueError not raised
    assert f"Rendering: {GREEN}1.111{STOP}" == report.execution_summary_formatted

    # It should not crash and it would render even where no wallclock time yet
    report = Report(
        "_cmd",
        [],
        mock_log_paths,
        wall_clock_format_string,
        cwd,
        clobber=False,
        colors=colors,
    )
    assert f"Rendering: {GREEN}nan{STOP}" == report.execution_summary_formatted

    # or if we really provide bad formatting, e.g. the opposite order of conversion and formatting
    report = Report(
        "_cmd",
        [],
        mock_log_paths,
        "Rendering: {wall_clock_time!X:.3f}",
        cwd,
        clobber=False,
        colors=colors,
    )
    assert f"Rendering: {GREEN}nan{STOP}" == report.execution_summary_formatted


def test_summary_formatter_P_e2e() -> None:
    """Test percentage conversion (!P)"""
    formatter = SummaryFormatter()

    # Test without conversion
    valid_format_string = "test {cpu}"
    no_p_applied = formatter.format(valid_format_string, **{"cpu": 85.567})
    assert no_p_applied == "test 85.567"

    # Test with !P conversion
    p_format_string = "test {cpu!P}"
    p_applied = formatter.format(p_format_string, **{"cpu": 85.567})
    assert p_applied == "test 85.57%"

    # Test with integer
    p_int_applied = formatter.format(p_format_string, **{"cpu": 100})
    assert p_int_applied == "test 100.00%"

    # Test with None
    p_none_applied = formatter.format(p_format_string, **{"cpu": None})
    assert p_none_applied == "test -"


def test_summary_formatter_P_e2e_colors() -> None:
    """Test percentage conversion (!P) with colors"""
    formatter = SummaryFormatter(enable_colors=True)

    p_format_string = "test {cpu!P}"

    # Test normal value (no color for P conversion)
    p_applied = formatter.format(p_format_string, **{"cpu": 85.567})
    assert p_applied == "test 85.57%"

    # Test None (should be red)
    p_none_applied = formatter.format(p_format_string, **{"cpu": None})
    assert p_none_applied == f"test {RED_START}-{formatter.RESET_SEQ}"


def test_summary_formatter_T_e2e() -> None:
    """Test time duration conversion (!T)"""
    formatter = SummaryFormatter()

    # Test without conversion
    valid_format_string = "test {duration}"
    no_t_applied = formatter.format(valid_format_string, **{"duration": 3661.5})
    assert no_t_applied == "test 3661.5"

    # Test with !T conversion - hours
    t_format_string = "test {duration!T}"
    t_hours_applied = formatter.format(t_format_string, **{"duration": 3661.5})
    assert t_hours_applied == "test 1h 1m 1.5s"

    # Test minutes
    t_minutes_applied = formatter.format(t_format_string, **{"duration": 150.75})
    assert t_minutes_applied == "test 2m 30.8s"

    # Test seconds only
    t_seconds_applied = formatter.format(t_format_string, **{"duration": 45.123})
    assert t_seconds_applied == "test 45.12s"

    # Test with None
    t_none_applied = formatter.format(t_format_string, **{"duration": None})
    assert t_none_applied == "test -"


def test_summary_formatter_T_e2e_colors() -> None:
    """Test time duration conversion (!T) with colors"""
    formatter = SummaryFormatter(enable_colors=True)

    t_format_string = "test {duration!T}"

    # Test normal value (no color for T conversion)
    t_applied = formatter.format(t_format_string, **{"duration": 3661.5})
    assert t_applied == "test 1h 1m 1.5s"

    # Test None (should be red)
    t_none_applied = formatter.format(t_format_string, **{"duration": None})
    assert t_none_applied == f"test {RED_START}-{formatter.RESET_SEQ}"


def test_summary_formatter_D_e2e() -> None:
    """Test datetime conversion (!D)"""
    formatter = SummaryFormatter()

    # Test without conversion
    valid_format_string = "test {timestamp}"
    no_d_applied = formatter.format(valid_format_string, **{"timestamp": 1625400000})
    assert no_d_applied == "test 1625400000"

    # Test with !D conversion - use July 4, 2021 12:00 PM UTC (safe from timezone edge cases)
    d_format_string = "test {timestamp!D}"
    # This timestamp represents July 4, 2021 12:00:00 UTC
    result = formatter.format(d_format_string, **{"timestamp": 1625400000})
    assert "Jul" in result and "2021" in result and ":" in result

    # Test with invalid timestamp (should return as string)
    d_invalid_applied = formatter.format(d_format_string, **{"timestamp": "invalid"})
    assert "test invalid" == d_invalid_applied

    # Test with None
    d_none_applied = formatter.format(d_format_string, **{"timestamp": None})
    assert d_none_applied == "test -"


def test_summary_formatter_D_e2e_colors() -> None:
    """Test datetime conversion (!D) with colors"""
    formatter = SummaryFormatter(enable_colors=True)

    d_format_string = "test {timestamp!D}"

    # Test normal value (no color for D conversion)
    result = formatter.format(d_format_string, **{"timestamp": 1625400000})
    assert "Jul" in result and "2021" in result

    # Test None (should be red)
    d_none_applied = formatter.format(d_format_string, **{"timestamp": None})
    assert d_none_applied == f"test {RED_START}-{formatter.RESET_SEQ}"


@pytest.mark.parametrize(
    "duration,expected",
    [
        (0.5, "0.50s"),
        (30, "30.00s"),
        (90, "1m 30.0s"),
        (3600, "1h 0m 0.0s"),
        (3661.27, "1h 1m 1.3s"),
        (7323.75, "2h 2m 3.8s"),
    ],
)
def test_summary_formatter_T_duration_formats(duration: float, expected: str) -> None:
    """Test various duration formatting scenarios"""
    formatter = SummaryFormatter()
    result = formatter.format("{duration!T}", duration=duration)
    assert result == expected

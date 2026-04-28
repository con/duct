"""Tests for utility functions in _duct_main.py"""

import pytest
from con_duct._utils import assert_num, etime_to_etimes, instantaneous_pcpu


@pytest.mark.parametrize("input_value", [0, 1, 2, -1, 100, 0.001, -1.68])
def test_assert_num_green(input_value: int) -> None:
    assert_num(input_value)


@pytest.mark.parametrize("input_value", ["hi", "0", "one"])
def test_assert_num_red(input_value: int) -> None:
    with pytest.raises(AssertionError):
        assert_num(input_value)


@pytest.mark.parametrize(
    "etime,expected",
    [
        ("00:42", 42.0),
        ("01:30", 90.0),
        ("01:00:00", 3600.0),
        ("12:34:56", 12 * 3600 + 34 * 60 + 56),
        ("02-03:04:05", 2 * 86400 + 3 * 3600 + 4 * 60 + 5),
        ("100-00:00:00", 100 * 86400.0),
    ],
)
def test_etime_to_etimes_green(etime: str, expected: float) -> None:
    assert etime_to_etimes(etime) == expected


@pytest.mark.parametrize("etime", ["", "garbage", "12", "1:2:3:4", "ab:cd"])
def test_etime_to_etimes_red(etime: str) -> None:
    with pytest.raises(ValueError):
        etime_to_etimes(etime)


@pytest.mark.parametrize(
    "prev_pcpu,prev_etimes,curr_pcpu,curr_etimes,expected",
    [
        # Motivating con/duct#399 case: 100% for 60s then idle for 60s.
        # Lifetime pcpu still reads 50% at t=120 (60 cputime / 120
        # etime), but the corrected instantaneous reading is 0%.
        (100.0, 60.0, 50.0, 120.0, 0.0),
        # Constant 84% load across a 10s interval.
        (80.0, 10.0, 82.0, 20.0, 84.0),
        # Pid that ramps from 50% lifetime to 75% lifetime over 100s
        # of new wall time -> 100% during the new interval.
        (50.0, 100.0, 75.0, 200.0, 100.0),
    ],
)
def test_instantaneous_pcpu_green(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
    expected: float,
) -> None:
    assert (
        instantaneous_pcpu(prev_pcpu, prev_etimes, curr_pcpu, curr_etimes) == expected
    )


@pytest.mark.parametrize(
    "prev_pcpu,prev_etimes,curr_pcpu,curr_etimes,expected",
    [
        # etimes regressed -> suspected pid reuse; fall back to curr.
        (80.0, 100.0, 10.0, 2.0, 10.0),
        # Same instant -> interval is zero, no rate definable; fall
        # back to curr.
        (50.0, 100.0, 50.0, 100.0, 50.0),
    ],
)
def test_instantaneous_pcpu_falls_back_to_curr(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
    expected: float,
) -> None:
    assert (
        instantaneous_pcpu(prev_pcpu, prev_etimes, curr_pcpu, curr_etimes) == expected
    )

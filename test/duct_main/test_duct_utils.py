"""Tests for utility functions in _duct_main.py"""

import pytest
from con_duct._utils import (
    assert_num,
    etime_to_etimes,
    is_same_pid,
    pdcpu_from_pcpu,
)


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
        # etime), but the corrected reading is 0%.
        (100.0, 60.0, 50.0, 120.0, 0.0),
        # Constant 84% load across a 10s interval.
        (80.0, 10.0, 82.0, 20.0, 84.0),
        # Pid that ramps from 50% lifetime to 75% lifetime over 100s
        # of new wall time -> 100% during the new interval.
        (50.0, 100.0, 75.0, 200.0, 100.0),
    ],
)
def test_pdcpu_from_pcpu_green(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
    expected: float,
) -> None:
    assert pdcpu_from_pcpu(prev_pcpu, prev_etimes, curr_pcpu, curr_etimes) == expected


@pytest.mark.parametrize(
    "prev_pcpu,prev_etimes,curr_pcpu,curr_etimes",
    [
        # etimes regressed -> suspected pid reuse; defensive guard.
        (80.0, 100.0, 10.0, 2.0),
        # Same instant -> interval is zero, no rate definable.
        (50.0, 100.0, 50.0, 100.0),
    ],
)
def test_pdcpu_from_pcpu_returns_none_when_no_interval(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
) -> None:
    assert pdcpu_from_pcpu(prev_pcpu, prev_etimes, curr_pcpu, curr_etimes) is None


@pytest.mark.parametrize(
    "prev_pcpu,prev_etimes,curr_pcpu,curr_etimes",
    [
        # Aggregation-timing skew: max pcpu in prev was captured early in
        # the prev interval (pcpu_max=400 on a 4-core box, then idle).
        # Curr's max happens late, so curr's pcpu*etime estimate of cputime
        # is much smaller than prev's. Δcputime goes negative even though
        # the pid is continuous (Δetime ≈ Δwall).
        (400.0, 59.0, 100.0, 119.0),
        # Smaller version of the same effect.
        (50.0, 60.0, 5.0, 120.0),
    ],
)
def test_pdcpu_from_pcpu_returns_none_on_negative_result(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
) -> None:
    """Negative pdcpu == aggregation-timing artifact (not pid reuse).

    See is_same_pid for identity; this clamp catches the residual case
    where identity holds but the max-vs-end-etime mismatch in duct's
    aggregated records produces a spurious negative delta.
    """
    assert pdcpu_from_pcpu(prev_pcpu, prev_etimes, curr_pcpu, curr_etimes) is None


@pytest.mark.parametrize(
    "prev_etimes,curr_etimes,wall_delta,expected",
    [
        # Continuous pid: Δetime exactly matches Δwall.
        (50.0, 110.0, 60.0, True),
        # 1-second slack from ps integer rounding -- still same pid.
        (50.0, 109.0, 60.0, True),
        # 2-second slack at the tolerance boundary -- still same pid.
        (50.0, 108.0, 60.0, True),
        # Concrete con/duct#399 case: pid 3323259 went 49->54 over 60s of
        # wall time. 5 << 58. Definitely a different physical process.
        (49.0, 54.0, 60.0, False),
        # etime regressed -- obvious reuse.
        (100.0, 5.0, 60.0, False),
        # Sub-quantum: same instant, no time elapsed for either etime or
        # wall -- treat as continuous (no reuse signal).
        (50.0, 50.0, 0.0, True),
    ],
)
def test_is_same_pid(
    prev_etimes: float,
    curr_etimes: float,
    wall_delta: float,
    expected: bool,
) -> None:
    assert is_same_pid(prev_etimes, curr_etimes, wall_delta) is expected


def test_is_same_pid_tolerance_kwarg() -> None:
    # 5s gap inside default tolerance? No (default is 2s).
    assert not is_same_pid(50.0, 105.0, 60.0)
    # ...but it is inside a 6s tolerance.
    assert is_same_pid(50.0, 105.0, 60.0, tolerance=6.0)

"""Tests for utility functions in _duct_main.py"""

import pytest
from con_duct._utils import assert_num, etime_to_etimes


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

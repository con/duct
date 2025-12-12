"""Tests for utility functions in duct_main.py"""

import pytest
from con_duct.duct_main import assert_num


@pytest.mark.parametrize("input_value", [0, 1, 2, -1, 100, 0.001, -1.68])
def test_assert_num_green(input_value: int) -> None:
    assert_num(input_value)


@pytest.mark.parametrize("input_value", ["hi", "0", "one"])
def test_assert_num_red(input_value: int) -> None:
    with pytest.raises(AssertionError):
        assert_num(input_value)

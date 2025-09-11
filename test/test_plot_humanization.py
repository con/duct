"""Tests for plot axis humanization features."""

from typing import Any, List, Tuple
from unittest.mock import Mock
import pytest
from con_duct.suite import plot


@pytest.mark.parametrize(
    "min_ratio,span_seconds,expected_unit",
    [
        # min_ratio=-1: always use base unit
        (-1, 2, "s"),  # Small value
        (-1, 3700, "s"),  # More than 1 hour - still base unit
        (-1, 3 * 60 * 60 * 24, "s"),  # 3 days - still base unit
        # min_ratio=1.5: switch units more aggressively
        (1.5, 90, "min"),  # 1.5 minutes meets threshold
        (1.5, 90 * 60, "h"),  # 1.5 hours meets threshold
        (1.5, 36 * 60 * 60, "d"),  # 1.5 days meets threshold
        # min_ratio=3.0: standard threshold
        (3.0, 2, "s"),  # 2 seconds - stays in base unit
        (3.0, 3 * 60, "min"),  # 3 minutes - meets min_ratio for minutes
        (3.0, 3 * 60 * 60, "h"),  # 3 hours - meets min_ratio for hours
        (3.0, 3 * 60 * 60 * 24, "d"),  # 3 days - meets min_ratio for days
        # min_ratio=5.0: more conservative switching
        (5.0, 4 * 60, "s"),  # 4 minutes - doesn't meet threshold, stays seconds
        (5.0, 5 * 60, "min"),  # 5 minutes - meets threshold
        (5.0, 4 * 60 * 60, "min"),  # 4 hours - doesn't meet hour threshold
        (5.0, 5 * 60 * 60, "h"),  # 5 hours - meets hour threshold
    ],
)
def test_pick_unit_with_varying_ratios(
    min_ratio: float, span_seconds: float, expected_unit: str
) -> None:
    """Test pick_unit selects appropriate unit based on min_ratio."""
    formatter: Any = plot.HumanizedAxisFormatter(
        min_ratio=min_ratio, units=plot._TIME_UNITS
    )
    unit_name, _ = formatter.pick_unit(span_seconds)
    assert unit_name == expected_unit


@pytest.mark.parametrize(
    "units,axis_range,value,expected",
    [
        # Time formatting tests
        (plot._TIME_UNITS, (0, 30), 15, "15.0s"),
        (plot._TIME_UNITS, (0, 300), 2.3 * 60, "2.3min"),
        (plot._TIME_UNITS, (0, 11000), 7.8 * 60 * 60, "7.8h"),
        (plot._TIME_UNITS, (0, 260000), 3.2 * 60 * 60 * 24, "3.2d"),
        # Memory formatting tests
        (plot._MEMORY_UNITS, (0, 5 * 1024), 2.6 * 1024, "2.6KB"),
        (plot._MEMORY_UNITS, (0, 4 * 1024**2), 1.5 * (1024**2), "1.5MB"),
        (plot._MEMORY_UNITS, (0, 3 * 1024**3), 8.3 * 1024**3, "8.3GB"),
        (plot._MEMORY_UNITS, (0, 3 * 1024**4), 1.3 * 1024**4, "1.3TB"),
        (plot._MEMORY_UNITS, (0, 3.1 * 1024**5), 6.5 * 1024**5, "6.5PB"),
    ],
)
def test_formatter_output(
    units: List[Tuple[str, float]],
    axis_range: Tuple[float, float],
    value: float,
    expected: str,
) -> None:
    """Test HumanizedAxisFormatter formats values correctly for time and memory units."""
    formatter: Any = plot.HumanizedAxisFormatter(min_ratio=3.0, units=units)
    formatter.axis = Mock()
    formatter.axis.get_view_interval.return_value = axis_range
    result = formatter(value, 0)
    assert result == expected

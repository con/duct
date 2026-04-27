"""Utility functions for con-duct."""

from __future__ import annotations
from typing import Any


def assert_num(*values: Any) -> None:
    for value in values:
        assert isinstance(value, (float, int))


# TODO: consider asking ps for `etimes` (seconds) directly via
# `-o etimes` instead of parsing `etime`. Even if we switch, this
# parser is worth keeping for backwards compatibility with existing
# usage.jsonl logs that persist `etime` as a string.
def etime_to_etimes(etime: str) -> float:
    """Parse a ps ``etime`` string into seconds.

    ps's ``etime`` format is ``[[DD-]HH:]MM:SS``: ``MM:SS`` always,
    with ``HH:`` prepended after one hour and ``DD-`` prepended after
    one day.

    :param etime: elapsed-time string from ``ps -o etime``.
    :returns: elapsed time in seconds.
    :raises ValueError: if ``etime`` does not match the expected shape.
    """
    if "-" in etime:
        days_str, rest = etime.split("-", 1)
        days = int(days_str)
    else:
        days = 0
        rest = etime
    parts = rest.split(":")
    if len(parts) == 2:
        hours, minutes, seconds = 0, int(parts[0]), int(parts[1])
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(f"Unparsable etime: {etime!r}")
    return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def parse_version(version_str: str) -> tuple[int, int, int]:
    x_y_z = version_str.split(".")
    if len(x_y_z) != 3:
        raise ValueError(
            f"Invalid version format: {version_str}. Expected 'x.y.z' format."
        )

    x, y, z = map(int, x_y_z)  # Unpacking forces exactly 3 elements
    return (x, y, z)

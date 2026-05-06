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


def instantaneous_pcpu(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
) -> float:
    """Instantaneous %CPU between two ps samples of the same pid.

    Inverts the procps identity ``pcpu = cputime / etime * 100`` to
    recover cputime at each sample, takes the cputime delta, and
    divides by the elapsed interval. The ``/100`` and ``*100``
    cancel, so the result is in the same units as ``pcpu``.

    Linux-only: assumes ``pcpu`` is the cumulative ``cputime/etime``
    ratio. Invalid on Darwin (decayed EWMA).

    Precision floor: ps reports ``etime`` at 1-second resolution, so
    at sample intervals near 1s this function frequently falls back
    to ``curr_pcpu`` (see PROBLEMS.md in the resource-measurement
    notebook).

    :param prev_pcpu: %CPU from the earlier sample.
    :param prev_etimes: elapsed seconds at the earlier sample.
    :param curr_pcpu: %CPU from the later sample.
    :param curr_etimes: elapsed seconds at the later sample.
    :returns: instantaneous %CPU over the interval. Falls back to
        ``curr_pcpu`` when the interval is non-positive (etimes did
        not advance, or regressed -- suspected pid reuse). The
        fallback keeps the value honest about "something is here"
        rather than emitting a silent zero; a sophisticated consumer
        can detect fallback by comparing against ``pcpu_raw``.
    """
    interval = curr_etimes - prev_etimes
    if interval <= 0:
        return curr_pcpu
    return (curr_pcpu * curr_etimes - prev_pcpu * prev_etimes) / interval


def parse_version(version_str: str) -> tuple[int, int, int]:
    x_y_z = version_str.split(".")
    if len(x_y_z) != 3:
        raise ValueError(
            f"Invalid version format: {version_str}. Expected 'x.y.z' format."
        )

    x, y, z = map(int, x_y_z)  # Unpacking forces exactly 3 elements
    return (x, y, z)

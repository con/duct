"""Utility functions for con-duct."""

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


def is_same_pid(
    prev_etimes: float,
    curr_etimes: float,
    wall_delta: float,
    *,
    tolerance: float = 2.0,
) -> bool:
    """Decide whether two consecutive observations of the same pid number
    correspond to the same physical process (vs kernel pid reuse).

    A continuously-existing pid's ``etime`` grows by exactly the
    wall-clock time between two samples (etime is wall-since-fork,
    not cputime). ps reports ``etime`` at integer-second resolution,
    so the only slack is rounding plus small clock drift.

    A stricter ``etime_2 < etime_1`` check would miss reuses where
    the new pid's etime crept above the old pid's last reading by
    less than the sample interval. Comparing ``Δetime`` against
    ``Δwall`` catches those too.

    :param prev_etimes: elapsed seconds at the earlier sample.
    :param curr_etimes: elapsed seconds at the later sample.
    :param wall_delta: wall-clock seconds between the two samples.
    :param tolerance: slack (seconds) absorbed by ps's integer-second
        ``etime`` plus clock drift. 2 seconds is plenty in practice.
    :returns: ``True`` iff ``Δetime`` is close enough to ``Δwall``
        to be the same continuous process.
    """
    return curr_etimes - prev_etimes >= wall_delta - tolerance


def pdcpu_from_pcpu(
    prev_pcpu: float,
    prev_etimes: float,
    curr_pcpu: float,
    curr_etimes: float,
) -> float | None:
    """Delta-corrected %CPU between two ps samples of the same pid.

    Inverts the procps identity ``pcpu = cputime / etime * 100`` to
    recover cputime at each sample, takes the cputime delta, and
    divides by the elapsed interval. The ``/100`` and ``*100``
    cancel, so the result is in the same units as ``pcpu``.

    Linux-only: assumes ``pcpu`` is the cumulative ``cputime/etime``
    ratio. Invalid on Darwin (decayed EWMA).

    Identity is the caller's responsibility: invoke ``is_same_pid``
    first. If the inputs satisfy that precondition, ``Δetime`` is
    positive and the math is well-defined.

    :param prev_pcpu: %CPU from the earlier sample.
    :param prev_etimes: elapsed seconds at the earlier sample.
    :param curr_pcpu: %CPU from the later sample.
    :param curr_etimes: elapsed seconds at the later sample.
    :returns: delta-corrected %CPU over the interval, or ``None``
        in two "no measurement" cases:

        - ``Δetime <= 0`` -- defensive guard for callers that
          skipped ``is_same_pid``; covers sub-quantum and obvious
          pid-reuse.
        - Computed ``pdcpu < 0`` -- aggregation-timing artifact.
          When duct's per-pid ``pcpu`` is max-across-samples while
          ``etime`` is from the last sample, a spike-then-idle
          pattern earlier in the run inflates ``prev_pcpu *
          prev_etimes`` enough that the cputime "delta" goes
          negative. The pid is the same; the math is just noisy.
          A small minus dip is honestly null, not zero.
    """
    interval = curr_etimes - prev_etimes
    if interval <= 0:
        return None
    pdcpu = (curr_pcpu * curr_etimes - prev_pcpu * prev_etimes) / interval
    if pdcpu < 0:
        return None
    return pdcpu


def parse_version(version_str: str) -> tuple[int, int, int]:
    x_y_z = version_str.split(".")
    if len(x_y_z) != 3:
        raise ValueError(
            f"Invalid version format: {version_str}. Expected 'x.y.z' format."
        )

    x, y, z = map(int, x_y_z)  # Unpacking forces exactly 3 elements
    return (x, y, z)

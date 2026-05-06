"""Tests for the platform-specific samplers in _sampling.py."""

from __future__ import annotations
from unittest import mock
import pytest
from con_duct._sampling import _get_sample_linux

_HEADER = "  PID %CPU %MEM   RSS   VSZ ELAPSED STAT CMD\n"


@pytest.mark.usefixtures("enable_drop_young_pids")
@mock.patch("con_duct._sampling.subprocess.check_output")
def test_get_sample_linux_threads_prev_state(
    mock_check_output: mock.MagicMock,
) -> None:
    """Three successive calls round-trip the prev-state dict.

    Call 1: no prior -> pcpu falls back to pcpu_raw.
    Call 2: prior present -> pcpu computed via instantaneous_pcpu.
    Call 3: pid 1234 vanishes, pid 5678 appears -> new_prev is
    rebuilt fresh, dropping stale entries automatically.
    """
    out_1 = _HEADER + " 1234 80.0  1.0  1024  2048   00:10 R    cmd\n"
    # pcpu=82 at etimes=20 against pcpu=80 at etimes=10 yields a
    # constant 84% load across the 10s interval (mirrors one of the
    # test_instantaneous_pcpu_green parameterized cases).
    out_2 = _HEADER + " 1234 82.0  1.0  1024  2048   00:20 R    cmd\n"
    # 9999 has etime "00:00" -> dropped per DROP_YOUNG_PIDS;
    # 5678 first-observed with non-zero etime -> fallback path.
    out_3 = (
        _HEADER
        + " 5678 50.0  1.0   512  1024   00:05 R    other\n"
        + " 9999 99.0  1.0   256   512   00:00 R    young\n"
    )
    mock_check_output.side_effect = [out_1, out_2, out_3]

    sample1, prev1 = _get_sample_linux(session_id=42, prev={})
    assert sample1 is not None
    assert prev1 == {1234: (80.0, 10.0)}
    stats1 = sample1.stats[1234]
    assert stats1.pcpu == 80.0
    assert stats1.pcpu_raw == 80.0
    assert stats1.etimes == 10.0
    assert stats1.rss == 1024 * 1024  # KiB -> bytes
    assert stats1.vsz == 2048 * 1024

    sample2, prev2 = _get_sample_linux(session_id=42, prev=prev1)
    assert sample2 is not None
    assert prev2 == {1234: (82.0, 20.0)}
    stats2 = sample2.stats[1234]
    assert stats2.pcpu_raw == 82.0
    assert stats2.etimes == 20.0
    assert stats2.pcpu == 84.0

    sample3, prev3 = _get_sample_linux(session_id=42, prev=prev2)
    assert sample3 is not None
    assert prev3 == {5678: (50.0, 5.0)}
    assert 1234 not in sample3.stats
    # First observation of 5678 -> fallback to pcpu_raw.
    assert sample3.stats[5678].pcpu == 50.0
    # 9999 had etime="00:00" -> dropped from sample and prev.
    assert 9999 not in sample3.stats
    assert 9999 not in prev3


@pytest.mark.usefixtures("enable_drop_young_pids")
@mock.patch("con_duct._sampling.subprocess.check_output")
def test_get_sample_linux_returns_none_when_all_dropped(
    mock_check_output: mock.MagicMock,
) -> None:
    """When every pid in ps output is filtered (e.g. all young),
    return (None, new_prev) instead of an empty Sample. Matches
    _get_sample_mac's no-pids path; lets the monitor loop skip the
    round rather than crash on Averages.from_sample's not-None
    assertions.
    """
    out = (
        _HEADER
        + " 1111 99.0  1.0   256   512   00:00 R    young_a\n"
        + " 2222 99.0  1.0   256   512   00:00 R    young_b\n"
    )
    mock_check_output.side_effect = [out]
    sample, prev = _get_sample_linux(session_id=42, prev={})
    assert sample is None
    assert prev == {}

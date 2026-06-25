"""Unit tests for the collector / measurement registry and live collectors."""

from __future__ import annotations
import os
from pathlib import Path
import pytest
from con_duct._collectors import (
    ALL_MEASUREMENTS,
    CgroupCollector,
    Derive,
    PsCollector,
    PsutilCollector,
    Reduce,
    Scope,
    UnavailableMeasurementError,
    UnknownMeasurementError,
    available_keys,
    resolve_selection,
)

SID = os.getsid(0)


def test_ps_keys_match_design() -> None:
    names = {m.name for m in PsCollector.measurements}
    assert {"ps_rss", "ps_rss_total", "ps_pdcpu", "ps_cpu_seconds"} <= names
    # ps_pdcpu derives a rate; ps_cpu_seconds is a delta counter.
    by_name = {m.name: m for m in PsCollector.measurements}
    assert by_name["ps_pdcpu"].derive is Derive.RATE
    assert by_name["ps_pdcpu"].scope is Scope.PER_PID
    assert by_name["ps_cpu_seconds"].reduce is Reduce.DELTA
    assert by_name["ps_cpu_seconds"].scope is Scope.SINGLE
    assert by_name["ps_rss_total"].scope is Scope.SINGLE


def test_ps_collect_live() -> None:
    """ps always available; collecting our own session yields readings."""
    assert PsCollector.available()
    reading = PsCollector(SID).collect()
    assert reading, "expected at least our own process"
    fields = next(iter(reading.values()))
    assert set(fields) == {"rss", "cputime", "cmd"}
    assert isinstance(fields["rss"], int) and fields["rss"] > 0
    assert isinstance(fields["cputime"], float) and fields["cputime"] >= 0.0


def test_cgroup_refuses_when_missing(tmp_path: Path) -> None:
    missing = CgroupCollector(peak_path=tmp_path / "does_not_exist")
    assert missing.available() is False


def test_cgroup_reads_value(tmp_path: Path) -> None:
    peak = tmp_path / "memory.peak"
    peak.write_text("4096\n")
    cg = CgroupCollector(peak_path=peak)
    assert cg.available() is True
    assert cg.read() == {"mem_peak": 4096.0}


def test_psutil_optional_keys_are_marked() -> None:
    assert all(m.optional for m in PsutilCollector.measurements)


def test_resolve_none_returns_available() -> None:
    resolved = resolve_selection(None, SID)
    assert [m.name for m in resolved] == available_keys(SID)


def test_resolve_unknown_key_raises() -> None:
    with pytest.raises(UnknownMeasurementError):
        resolve_selection(["not_a_real_key"], SID)


def test_resolve_unavailable_psutil_message(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force psutil unavailable and confirm a clean, actionable error.
    monkeypatch.setattr(PsutilCollector, "available", staticmethod(lambda: False))
    with pytest.raises(UnavailableMeasurementError, match="psutil"):
        resolve_selection(["psutil_pss"], SID)


def test_all_measurements_have_unique_names() -> None:
    names = list(ALL_MEASUREMENTS)
    assert len(names) == len(set(names))

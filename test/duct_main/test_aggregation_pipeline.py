"""Unit tests for the collect -> buffer -> aggregate-once pipeline.

A ``FakeCollector`` feeds canned per-sample readings so the derive/collapse/
reduce logic and the cross-report seeds are exercised deterministically,
without depending on live ``ps`` timing.
"""

from __future__ import annotations
from typing import Dict, List
import pytest
from con_duct._aggregation import Aggregator
from con_duct._collectors import (
    ALL_MEASUREMENTS,
    Collector,
    Measurement,
    PerPidReading,
)


class FakeCollector:
    """Per-sample collector that pops canned readings in order."""

    per_sample = True
    measurements: List[Measurement] = []

    def __init__(self, name: str, readings: List[PerPidReading]) -> None:
        self.name = name
        self._readings = list(readings)

    def collect(self) -> PerPidReading:
        return self._readings.pop(0)


class FakeSingleCollector:
    """Read-once-per-report collector returning a fixed single reading."""

    per_sample = False
    measurements: List[Measurement] = []

    def __init__(self, name: str, value: float) -> None:
        self.name = name
        self._value = value

    def read(self) -> Dict[str, float]:
        return {"mem_peak": self._value}


def _agg(measurements: List[Measurement], collectors: List[Collector]) -> Aggregator:
    return Aggregator(measurements, session_id=0, collectors=collectors)


def test_per_pid_max_level() -> None:
    m = ALL_MEASUREMENTS["ps_rss"]
    fake = FakeCollector(
        "ps",
        [
            {1: {"rss": 100.0}, 2: {"rss": 50.0}},
            {1: {"rss": 80.0}, 2: {"rss": 70.0}},
        ],
    )
    agg = _agg([m], [fake])
    agg.add_sample()
    agg.add_sample()
    record = agg.report()
    assert record is not None
    assert record["measurements"]["ps_rss"] == {"1": 100.0, "2": 70.0}
    assert record["num_samples"] == 2


def test_single_max_total() -> None:
    m = ALL_MEASUREMENTS["ps_rss_total"]
    fake = FakeCollector(
        "ps",
        [
            {1: {"rss": 100.0}, 2: {"rss": 50.0}},  # sum 150
            {1: {"rss": 80.0}, 2: {"rss": 70.0}},  # sum 150
            {1: {"rss": 120.0}, 2: {"rss": 70.0}},  # sum 190 (peak)
        ],
    )
    agg = _agg([m], [fake])
    for _ in range(3):
        agg.add_sample()
    record = agg.report()
    assert record is not None
    assert record["measurements"]["ps_rss_total"] == 190.0


def test_single_delta_counter() -> None:
    m = ALL_MEASUREMENTS["ps_cpu_seconds"]
    # cumulative cputime per pid: totals 10 -> 12 -> 15 across samples.
    fake = FakeCollector(
        "ps",
        [
            {1: {"cputime": 6.0}, 2: {"cputime": 4.0}},  # 10
            {1: {"cputime": 7.0}, 2: {"cputime": 5.0}},  # 12
            {1: {"cputime": 9.0}, 2: {"cputime": 6.0}},  # 15
        ],
    )
    agg = _agg([m], [fake])
    for _ in range(3):
        agg.add_sample()
    record = agg.report()
    assert record is not None
    # First window seeds delta from 0, so the whole cumulative total is counted.
    assert record["measurements"]["ps_cpu_seconds"] == 15.0


def test_delta_seed_crosses_report_boundary() -> None:
    m = ALL_MEASUREMENTS["ps_cpu_seconds"]
    fake = FakeCollector(
        "ps",
        [
            {1: {"cputime": 10.0}},  # window 1 sample 1
            {1: {"cputime": 13.0}},  # window 1 sample 2 -> total 13
            {1: {"cputime": 18.0}},  # window 2 sample 1 -> delta 18-13 = 5
        ],
    )
    agg = _agg([m], [fake])
    agg.add_sample()
    agg.add_sample()
    r1 = agg.report()
    assert r1 is not None and r1["measurements"]["ps_cpu_seconds"] == 13.0
    agg.add_sample()
    r2 = agg.report()
    assert r2 is not None and r2["measurements"]["ps_cpu_seconds"] == 5.0


def test_delta_clamps_on_pid_churn() -> None:
    m = ALL_MEASUREMENTS["ps_cpu_seconds"]
    # A pid with large cputime exits between reports, so the summed cumulative
    # total drops below the carried seed and the window delta would go negative.
    fake = FakeCollector(
        "ps",
        [
            {1: {"cputime": 5.0}, 2: {"cputime": 100.0}},  # report 1: total 105
            {1: {"cputime": 6.0}},  # report 2: pid 2 gone -> total 6 (< seed 105)
        ],
    )
    agg = _agg([m], [fake])
    agg.add_sample()
    r1 = agg.report()
    assert r1 is not None and r1["measurements"]["ps_cpu_seconds"] == 105.0
    agg.add_sample()
    r2 = agg.report()
    assert r2 is not None
    assert r2["measurements"]["ps_cpu_seconds"] == 0.0  # clamped, not negative


def test_per_pid_rate_uses_monotonic_dt(monkeypatch: pytest.MonkeyPatch) -> None:
    m = ALL_MEASUREMENTS["ps_pdcpu"]
    fake = FakeCollector(
        "ps",
        [
            {1: {"cputime": 0.0}},
            {1: {"cputime": 2.0}},  # +2 cputime
            {1: {"cputime": 3.0}},  # +1 cputime
        ],
    )
    # Drive monotonic clock at a fixed 1s cadence: rates are 2.0 then 1.0.
    ticks = iter([100.0, 101.0, 102.0])
    monkeypatch.setattr("con_duct._aggregation.time.monotonic", lambda: next(ticks))
    agg = _agg([m], [fake])
    for _ in range(3):
        agg.add_sample()
    record = agg.report()
    assert record is not None
    # reduce=max over per-sample rates -> 2.0 (cputime-seconds per wall second).
    assert record["measurements"]["ps_pdcpu"] == {"1": 2.0}


def test_rate_seed_crosses_report_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    m = ALL_MEASUREMENTS["ps_pdcpu"]
    fake = FakeCollector(
        "ps",
        [
            {1: {"cputime": 0.0}},  # w1 s1
            {1: {"cputime": 1.0}},  # w1 s2  rate 1.0
            {1: {"cputime": 5.0}},  # w2 s1  rate (5-1)/1 = 4.0 via seed
        ],
    )
    ticks = iter([10.0, 11.0, 12.0])
    monkeypatch.setattr("con_duct._aggregation.time.monotonic", lambda: next(ticks))
    agg = _agg([m], [fake])
    agg.add_sample()
    agg.add_sample()
    r1 = agg.report()
    assert r1 is not None and r1["measurements"]["ps_pdcpu"] == {"1": 1.0}
    agg.add_sample()
    r2 = agg.report()
    # Without the seed there is only one point in window 2 and no rate; the
    # carried seed lets the boundary-spanning rate be recovered.
    assert r2 is not None and r2["measurements"]["ps_pdcpu"] == {"1": 4.0}


def test_single_collector_read_once_per_report() -> None:
    m = ALL_MEASUREMENTS["cgroup_rss_peak"]
    ps = FakeCollector(
        "ps", [{1: {"rss": 1.0}}]
    )  # provides a sample so window != empty
    cg = FakeSingleCollector("cgroup", 4096.0)
    agg = _agg([ALL_MEASUREMENTS["ps_rss"], m], [ps, cg])
    agg.add_sample()
    record = agg.report()
    assert record is not None
    assert record["measurements"]["cgroup_rss_peak"] == 4096.0


def test_empty_window_returns_none() -> None:
    agg = _agg([ALL_MEASUREMENTS["ps_rss"]], [FakeCollector("ps", [])])
    assert agg.report() is None


def test_summary_accumulates_across_reports() -> None:
    ms = [ALL_MEASUREMENTS["ps_rss_total"], ALL_MEASUREMENTS["ps_cpu_seconds"]]
    fake = FakeCollector(
        "ps",
        [
            {1: {"rss": 100.0, "cputime": 2.0}},
            {1: {"rss": 200.0, "cputime": 5.0}},  # report 1
            {1: {"rss": 150.0, "cputime": 9.0}},  # report 2
        ],
    )
    agg = _agg(ms, [fake])
    agg.add_sample()
    agg.add_sample()
    agg.report()
    agg.add_sample()
    agg.report()
    summary = agg.summary()
    assert summary["peak_ps_rss_total"] == 200.0  # run peak across both reports
    assert summary["ps_cpu_seconds"] == 9.0  # total cputime over the run
    assert agg.num_reports == 2
    assert agg.num_samples == 3
    # Optional collectors absent -> keys present but null (stable schema).
    assert summary["peak_cgroup_rss_peak"] is None
    assert summary["peak_psutil_pss_total"] is None

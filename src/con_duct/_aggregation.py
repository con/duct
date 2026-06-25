"""Buffer raw readings and aggregate them once per report.

The collectors in :mod:`con_duct._collectors` are pure: each sample they append
raw readings to this aggregator's buffer.  At report time
:meth:`Aggregator.report` runs the design's three-step aggregation once over the
buffered window:

    derive (e.g. a rate from a counter)
      -> collapse per-pid readings into single values where the scope is single
      -> reduce over the interval (max for a level, delta/last for a counter)

The last raw reading of each window is kept as the **seed** for the next window
so a delta or rate that crosses a report boundary is not lost.  A run-level
accumulator feeds the end-of-run summary.

See ``docs/design/resource-collectors.md``.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import logging
import subprocess
import time
from typing import Dict, List, Optional, Tuple
from con_duct._collectors import (
    Collector,
    Derive,
    Measurement,
    PerPidReading,
    Reduce,
    Scope,
    available_collectors,
)

lgr = logging.getLogger("con-duct")

# A reduced measurement value: a scalar (single scope) or a {pid: value} map.
ReducedValue = object

# Measurement-derived keys always present in execution_summary, so info.json
# schema does not depend on which collectors happened to be available.
SUMMARY_KEYS = (
    "peak_ps_rss_total",
    "ave_ps_rss_total",
    "ps_cpu_seconds",
    "peak_cgroup_rss_peak",
    "peak_psutil_pss_total",
)


def null_summary() -> Dict[str, Optional[float]]:
    """The measurement summary with every value ``None`` (no run happened)."""
    return {key: None for key in SUMMARY_KEYS}


class Aggregator:
    """Owns the per-collector buffers, the cross-boundary seeds, and the
    run-level summary accumulator for one duct execution.

    :param measurements: the selected measurements (already resolved/validated).
    :param session_id: tracked session id, used to construct collectors.
    """

    def __init__(
        self,
        measurements: List[Measurement],
        session_id: int,
        collectors: Optional[List[Collector]] = None,
    ) -> None:
        self.measurements = measurements
        selected_collectors = {m.collector for m in measurements}

        # Only keep collectors that back a selected measurement.  Tests may
        # inject fakes; otherwise discover the environment's available ones.
        if collectors is None:
            collectors = available_collectors(session_id)
        self._collectors: Dict[str, Collector] = {
            c.name: c for c in collectors if c.name in selected_collectors
        }

        # Current-window buffers (per per-sample collector): list of
        # (monotonic_ts, reading).  Wall timestamps kept in parallel.
        self._samples: Dict[str, List[Tuple[float, PerPidReading]]] = defaultdict(list)
        self._wall_times: List[str] = []

        # Cross-report seeds.
        # rate seeds:  measurement_name -> {pid: (mono_ts, value)}
        self._rate_seeds: Dict[str, Dict[int, Tuple[float, float]]] = defaultdict(dict)
        # delta seeds: measurement_name -> last cumulative collapsed total
        self._delta_seeds: Dict[str, float] = defaultdict(float)

        # Run-level accumulators for the summary.
        self._run_peak: Dict[str, float] = {}
        self._run_total: Dict[str, float] = defaultdict(float)
        self._run_sum: Dict[str, float] = defaultdict(float)  # for averages
        self._run_count: Dict[str, int] = defaultdict(int)
        self.num_samples = 0
        self.num_reports = 0

    @property
    def has_samples(self) -> bool:
        """True when the current window holds at least one buffered sample."""
        return bool(self._wall_times)

    def add_sample(self) -> int:
        """Collect one sample from every per-sample collector into the buffer.

        :returns: number of pids the ``ps`` collector saw (0 when the tracked
            session has no processes, mirroring the old ``collect_sample``
            sentinel so the monitor loop can decide to stop).
        """
        mono = time.monotonic()
        wall = datetime.now().astimezone().isoformat()
        ps_pid_count = 0
        for name, collector in self._collectors.items():
            if not collector.per_sample:  # type: ignore[attr-defined]
                continue
            try:
                reading = collector.collect()  # type: ignore[attr-defined]
            except subprocess.CalledProcessError as exc:
                # ps exits non-zero when the session has no processes left.
                lgr.debug("Collector %s found no processes: %s", name, exc)
                reading = {}
            self._samples[name].append((mono, reading))
            if name == "ps":
                ps_pid_count = len(reading)
        self._wall_times.append(wall)
        self.num_samples += 1
        return ps_pid_count

    def report(self) -> Optional[dict]:
        """Aggregate the current window into one usage record, then reset it.

        :returns: the record ``{timestamp, num_samples, measurements}`` or
            ``None`` when the window held no samples (nothing to write).
        """
        if not self.has_samples:
            return None

        window_samples = len(self._wall_times)
        measurements: Dict[str, ReducedValue] = {}
        for meas in self.measurements:
            value = self._reduce_measurement(meas)
            if value is not None:
                measurements[meas.name] = value
            self._accumulate_summary(meas, value, window_samples)

        record = {
            "timestamp": self._wall_times[-1],
            "num_samples": window_samples,
            "measurements": measurements,
        }
        self.num_reports += 1
        self._reset_window()
        return record

    def _reset_window(self) -> None:
        self._samples = defaultdict(list)
        self._wall_times = []

    # -- reduction ---------------------------------------------------------

    def _reduce_measurement(self, meas: Measurement) -> ReducedValue:
        collector = self._collectors.get(meas.collector)
        if collector is None:
            return None

        if not collector.per_sample:  # type: ignore[attr-defined]
            # Single value read once per report (e.g. cgroup peak), reduce=last.
            single = collector.read()  # type: ignore[attr-defined]
            return single.get(meas.field)

        samples = self._samples[meas.collector]
        if meas.scope is Scope.PER_PID:
            if meas.derive is Derive.RATE:
                return self._per_pid_rate(meas, samples)
            if meas.reduce is Reduce.LAST:
                return self._per_pid_last(meas, samples)
            return self._per_pid_max(meas, samples)
        # SINGLE: collapse across pids per sample, then reduce over the window.
        return self._single(meas, samples)

    @staticmethod
    def _per_pid_max(
        meas: Measurement, samples: List[Tuple[float, PerPidReading]]
    ) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for _ts, reading in samples:
            for pid, fields in reading.items():
                val = float(fields[meas.field])  # type: ignore[arg-type]
                key = str(pid)
                out[key] = val if key not in out else max(out[key], val)
        return out

    @staticmethod
    def _per_pid_last(
        meas: Measurement, samples: List[Tuple[float, PerPidReading]]
    ) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for _ts, reading in samples:  # ordered; last write wins
            for pid, fields in reading.items():
                out[str(pid)] = fields[meas.field]
        return out

    def _per_pid_rate(
        self, meas: Measurement, samples: List[Tuple[float, PerPidReading]]
    ) -> Dict[str, Optional[float]]:
        # Build each pid's (ts, value) sequence, prepend the carried seed so a
        # rate spanning the report boundary is included.
        seq_by_pid: Dict[int, List[Tuple[float, float]]] = defaultdict(list)
        for ts, reading in samples:
            for pid, fields in reading.items():
                seq_by_pid[pid].append((ts, float(fields[meas.field])))  # type: ignore[arg-type]

        prev_seed = self._rate_seeds[meas.name]
        out: Dict[str, Optional[float]] = {}
        new_seed: Dict[int, Tuple[float, float]] = {}
        for pid, seq in seq_by_pid.items():
            points = ([prev_seed[pid]] if pid in prev_seed else []) + seq
            rates = [
                (v1 - v0) / (t1 - t0)
                for (t0, v0), (t1, v1) in zip(points, points[1:])
                if t1 > t0 and v1 >= v0  # ignore non-monotonic counter (pid reuse)
            ]
            out[str(pid)] = max(rates) if rates else None
            new_seed[pid] = seq[-1]
        self._rate_seeds[meas.name] = new_seed  # drop pids that vanished
        return out

    def _single(
        self, meas: Measurement, samples: List[Tuple[float, PerPidReading]]
    ) -> Optional[float]:
        per_sample_totals = [
            sum(float(fields[meas.field]) for fields in reading.values())  # type: ignore[arg-type]
            for _ts, reading in samples
        ]
        if not per_sample_totals:
            return None
        if meas.reduce is Reduce.DELTA:
            last = per_sample_totals[-1]
            delta = last - self._delta_seeds[meas.name]
            self._delta_seeds[meas.name] = last
            if delta < 0:
                # Cumulative total dropped because a pid exited mid-window; we
                # cannot attribute the lost counter, so report 0 for the window.
                lgr.debug("delta for %s went negative (pid churn); clamping", meas.name)
                return 0.0
            return delta
        # Reduce.MAX over the per-sample collapsed totals.
        return max(per_sample_totals)

    # -- summary -----------------------------------------------------------

    def _accumulate_summary(
        self, meas: Measurement, value: ReducedValue, window_samples: int
    ) -> None:
        """Fold one report's value into the run-level summary accumulator."""
        if meas.scope is not Scope.SINGLE or value is None:
            return
        fval = float(value)  # type: ignore[arg-type]
        if meas.reduce is Reduce.DELTA:
            self._run_total[meas.name] += fval
        else:  # MAX or LAST -> a level; track the run peak (+ mean for averages)
            self._run_peak[meas.name] = (
                fval
                if meas.name not in self._run_peak
                else max(self._run_peak[meas.name], fval)
            )
            self._run_sum[meas.name] += fval * window_samples
            self._run_count[meas.name] += window_samples

    def summary(self) -> dict:
        """Measurement-derived summary keys, always present (``None`` when the
        backing measurement was not selected/available), so info.json schema is
        environment-independent.
        """

        def peak(name: str) -> Optional[float]:
            return self._run_peak.get(name)

        def average(name: str) -> Optional[float]:
            count = self._run_count.get(name, 0)
            return self._run_sum[name] / count if count else None

        return {
            "peak_ps_rss_total": peak("ps_rss_total"),
            "ave_ps_rss_total": average("ps_rss_total"),
            "ps_cpu_seconds": (
                self._run_total["ps_cpu_seconds"]
                if "ps_cpu_seconds" in self._run_total
                else None
            ),
            "peak_cgroup_rss_peak": peak("cgroup_rss_peak"),
            "peak_psutil_pss_total": peak("psutil_pss_total"),
        }

"""Collector / measurement model for con-duct resource statistics.

A *collector* does one I/O pass and yields raw readings; it is pure (no
derivation, no cross-sample state).  A *measurement* is a namespaced key that
selects one raw field from a collector and declares how it is scoped, derived,
and reduced over a report interval.  See ``docs/design/resource-collectors.md``.

Two collector flavors:

- per-sample / per-pid (``ps``, ``psutil``): ``collect()`` is called every
  sample and returns ``{pid: {field: value}}``.
- per-report / single (``cgroup``): ``read()`` is called once per report and
  returns ``{field: value}`` (the kernel already took the peak).

The aggregation that turns buffered raw readings into reduced measurement
values lives in :mod:`con_duct._aggregation`; collectors stay pure.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import platform
import subprocess
import sys
from typing import Dict, List, Optional, Protocol, Union, runtime_checkable
from con_duct._utils import etime_to_etimes

lgr = logging.getLogger("con-duct")

SYSTEM = platform.system()

_SUPPORTED_SYSTEMS = {"Linux", "Darwin"}
if SYSTEM not in _SUPPORTED_SYSTEMS:
    sys.tracebacklimit = 0
    raise NotImplementedError(
        f"`con_duct` does not currently support the detected operating system "
        f"({SYSTEM}).\n\nIf you would like to request support, please open an "
        f"issue at: https://github.com/con/duct/issues/new"
    )

# A single raw field value: numeric for everything reduced arithmetically, str
# for the ``cmd`` label (reduce=last).
ReadingValue = Union[float, int, str]
# One per-pid collect() pass: pid -> {field: value}.
PerPidReading = Dict[int, Dict[str, ReadingValue]]
# One single read() pass: {field: value}.
SingleReading = Dict[str, float]


class Scope(str, Enum):
    """Whether a measurement is one value per process or one value total."""

    PER_PID = "per_pid"
    SINGLE = "single"

    def __str__(self) -> str:
        return self.value


class Derive(str, Enum):
    """Optional per-sample derivation applied before reduction."""

    NONE = "none"
    RATE = "rate"  # Δfield / Δt between consecutive readings of a pid

    def __str__(self) -> str:
        return self.value


class Reduce(str, Enum):
    """How per-sample values collapse over a report interval."""

    MAX = "max"  # instantaneous level (or peak per-sample rate)
    DELTA = "delta"  # cumulative counter: difference across the interval
    LAST = "last"  # already-reduced value (e.g. a kernel high-water mark)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Measurement:
    """A user-selectable measurement key.

    :param name: the namespaced key the user selects (e.g. ``ps_rss``).
    :param collector: the collector that produces the raw field.
    :param field: the raw field read from that collector's readings.
    :param scope: per-process or a single total.
    :param reduce: how per-sample values collapse over the interval.
    :param derive: optional per-sample derivation (e.g. a rate from a counter).
    :param optional: True when the backing collector is an optional dependency
        (psutil); requesting such a key without the dependency is a clean error.
    """

    name: str
    collector: str
    field: str
    scope: Scope
    reduce: Reduce
    derive: Derive = Derive.NONE
    optional: bool = False


@runtime_checkable
class Collector(Protocol):
    """Structural type shared by every collector.

    A per-sample collector additionally implements ``collect()``; a per-report
    collector implements ``read()`` (callers branch on ``per_sample``).
    """

    name: str
    per_sample: bool
    measurements: List[Measurement]


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


class PsCollector:
    """``ps``-backed per-pid collector; always available (the baseline).

    One ``ps`` call per sample yields ``rss`` (bytes), ``cputime`` (seconds),
    and ``cmd`` for every pid in the tracked session.
    """

    name = "ps"
    per_sample = True
    measurements = [
        Measurement("ps_rss", "ps", "rss", Scope.PER_PID, Reduce.MAX),
        Measurement("ps_rss_total", "ps", "rss", Scope.SINGLE, Reduce.MAX),
        Measurement(
            "ps_pdcpu", "ps", "cputime", Scope.PER_PID, Reduce.MAX, Derive.RATE
        ),
        Measurement("ps_cpu_seconds", "ps", "cputime", Scope.SINGLE, Reduce.DELTA),
        # Not in the design's key list: a string label kept so per-pid records
        # stay identifiable (plot labels, ls, child-counting). reduce=last.
        Measurement("ps_cmd", "ps", "cmd", Scope.PER_PID, Reduce.LAST),
    ]

    def __init__(self, session_id: int) -> None:
        self.session_id = session_id

    @staticmethod
    def available() -> bool:
        return SYSTEM in {"Linux", "Darwin"}

    def collect(self) -> PerPidReading:
        if SYSTEM == "Darwin":
            return self._collect_darwin()
        return self._collect_linux()

    def _collect_linux(self) -> PerPidReading:
        ps_command = [
            "ps",
            "-w",
            "-s",
            str(self.session_id),
            "-o",
            "pid,rss,cputime,cmd",
        ]
        output = subprocess.check_output(ps_command, text=True)
        reading: PerPidReading = {}
        for line in output.splitlines()[1:]:
            if not line:
                continue
            pid, rss_kib, cputime, cmd = line.split(maxsplit=3)
            reading[int(pid)] = {
                "rss": int(rss_kib) * 1024,
                "cputime": etime_to_etimes(cputime),
                "cmd": cmd,
            }
        return reading

    def _collect_darwin(self) -> PerPidReading:
        # macOS ps cannot filter by session id, so list all and filter by
        # getsid (mirrors _sampling._get_sample_mac). Untested in CI (Linux).
        import os

        ps_command = ["ps", "-ax", "-o", "pid,rss,cputime,command"]
        output = subprocess.check_output(ps_command, text=True)
        reading: PerPidReading = {}
        for line in output.splitlines()[1:]:
            if not line:
                continue
            pid_s, rss_kb, cputime, cmd = line.split(maxsplit=3)
            pid = int(pid_s)
            try:
                if os.getsid(pid) != self.session_id:
                    continue
            except ProcessLookupError:
                continue
            reading[pid] = {
                "rss": int(rss_kb) * 1024,
                "cputime": etime_to_etimes(cputime),
                "cmd": cmd,
            }
        return reading


class CgroupCollector:
    """Memory-cgroup high-water peak; a single value read once per report.

    Reader-mode only: reads duct's own cgroup peak counter (duct runs inside
    the job cgroup under SLURM).  Never creates a cgroup, never escalates
    privilege; refuses cleanly when the counter is not readable.
    """

    name = "cgroup"
    per_sample = False
    measurements = [
        Measurement("cgroup_rss_peak", "cgroup", "mem_peak", Scope.SINGLE, Reduce.LAST),
    ]

    def __init__(self, peak_path: Optional[Path] = None) -> None:
        self.peak_path = peak_path if peak_path is not None else self._find_peak_path()

    @staticmethod
    def _find_peak_path() -> Optional[Path]:
        """Resolve duct's own memory-cgroup peak file, or None if absent."""
        try:
            cgroup_lines = Path("/proc/self/cgroup").read_text().splitlines()
        except OSError:
            return None

        # cgroup v2: a single "0::<path>" line; peak is memory.peak.
        for line in cgroup_lines:
            if line.startswith("0::"):
                rel = line[3:].lstrip("/")
                candidate = Path("/sys/fs/cgroup", rel, "memory.peak")
                if candidate.is_file():
                    return candidate
                root = Path("/sys/fs/cgroup/memory.peak")
                return root if root.is_file() else None

        # cgroup v1: the "...:memory:<path>" line; peak is max_usage_in_bytes.
        for line in cgroup_lines:
            parts = line.split(":")
            if len(parts) == 3 and "memory" in parts[1].split(","):
                rel = parts[2].lstrip("/")
                candidate = Path(
                    "/sys/fs/cgroup/memory", rel, "memory.max_usage_in_bytes"
                )
                if candidate.is_file():
                    return candidate
        return None

    def available(self) -> bool:
        path = self.peak_path
        if path is None:
            return False
        try:
            with open(path):
                pass
        except OSError as exc:
            lgr.debug("cgroup peak file %s not readable: %s", path, exc)
            return False
        return True

    def read(self) -> SingleReading:
        assert self.peak_path is not None
        return {"mem_peak": float(int(self.peak_path.read_text().strip()))}


class PsutilCollector:
    """Optional per-pid collector: PSS (Linux) and a pure cputime for rate.

    Uses ``psutil`` if importable.  Reads raw ``cpu_times()`` (user+system),
    never ``cpu_percent()``, so the collect stays pure.  PSS comes from
    ``memory_full_info().pss`` (Linux only).
    """

    name = "psutil"
    per_sample = True
    measurements = [
        Measurement(
            "psutil_pss", "psutil", "pss", Scope.PER_PID, Reduce.MAX, optional=True
        ),
        Measurement(
            "psutil_pss_total",
            "psutil",
            "pss",
            Scope.SINGLE,
            Reduce.MAX,
            optional=True,
        ),
        Measurement(
            "psutil_pdcpu",
            "psutil",
            "cputime",
            Scope.PER_PID,
            Reduce.MAX,
            Derive.RATE,
            optional=True,
        ),
    ]

    def __init__(self, session_id: int) -> None:
        self.session_id = session_id

    @staticmethod
    def available() -> bool:
        import importlib.util

        return importlib.util.find_spec("psutil") is not None

    def collect(self) -> PerPidReading:
        import os
        import psutil  # type: ignore[import-untyped]

        reading: PerPidReading = {}
        for proc in psutil.process_iter(["pid"]):
            pid = proc.info["pid"]
            try:
                if os.getsid(pid) != self.session_id:
                    continue
                with proc.oneshot():
                    cpu = proc.cpu_times()
                    pss = proc.memory_full_info().pss
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                continue
            reading[pid] = {"pss": pss, "cputime": cpu.user + cpu.system}
        return reading


# ---------------------------------------------------------------------------
# Registry / selection
# ---------------------------------------------------------------------------

# key -> Measurement, across every collector (selectable or not yet available).
ALL_MEASUREMENTS: Dict[str, Measurement] = {
    m.name: m
    for m in (
        *PsCollector.measurements,
        *CgroupCollector.measurements,
        *PsutilCollector.measurements,
    )
}


class UnknownMeasurementError(ValueError):
    """A requested measurement key does not exist."""


class UnavailableMeasurementError(RuntimeError):
    """A requested key's collector is unavailable (e.g. psutil not installed)."""


def available_collectors(session_id: int) -> List[Collector]:
    """Instantiate every collector whose ``available()`` holds (ps first)."""
    instances: List[Collector] = []
    if PsCollector.available():
        instances.append(PsCollector(session_id))
    cgroup = CgroupCollector()
    if cgroup.available():
        instances.append(cgroup)
    if PsutilCollector.available():
        instances.append(PsutilCollector(session_id))
    return instances


def available_keys(session_id: int) -> List[str]:
    """All measurement keys whose collector is available in this environment."""
    keys: List[str] = []
    for inst in available_collectors(session_id):
        keys.extend(m.name for m in inst.measurements)
    return keys


def resolve_selection(
    requested: Optional[List[str]], session_id: int
) -> List[Measurement]:
    """Resolve a user key selection into Measurements.

    ``None`` selects every available key.  An explicit selection validates each
    key: unknown keys raise :class:`UnknownMeasurementError`; keys whose
    (optional) collector is unavailable raise
    :class:`UnavailableMeasurementError` with an actionable message.
    """
    avail = set(available_keys(session_id))
    if requested is None:
        return [ALL_MEASUREMENTS[k] for k in available_keys(session_id)]

    resolved: List[Measurement] = []
    for key in requested:
        meas = ALL_MEASUREMENTS.get(key)
        if meas is None:
            raise UnknownMeasurementError(
                f"Unknown measurement key {key!r}. "
                f"Available keys: {', '.join(sorted(ALL_MEASUREMENTS))}."
            )
        if key not in avail:
            hint = " (install con-duct[all] for psutil)" if meas.optional else ""
            raise UnavailableMeasurementError(
                f"Measurement {key!r} is unavailable: its collector "
                f"({meas.collector}) is not available in this environment{hint}."
            )
        resolved.append(meas)
    return resolved

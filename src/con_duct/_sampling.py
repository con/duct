"""Platform-specific process sampling for con-duct."""

from __future__ import annotations
from collections import Counter, deque
from datetime import datetime
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Optional, Union
from con_duct._models import Averages, ProcessStats, Sample

SYSTEM = platform.system()

_SUPPORTED_SYSTEMS = {"Linux", "Darwin"}
if SYSTEM not in _SUPPORTED_SYSTEMS:
    sys.tracebacklimit = 0
    message = (
        f"`con_duct` does not currently support the detected operating system ({SYSTEM}).\n\n"
        "If you would like to request support, please open an issue at: "
        "https://github.com/con/duct/issues/new"
    )
    raise NotImplementedError(message)

lgr = logging.getLogger("con-duct")


def _get_sample_linux(session_id: int) -> Sample:
    sample = Sample()

    ps_command = [
        "ps",
        "-w",
        "-s",
        str(session_id),
        "-o",
        "pid,pcpu,pmem,rss,vsz,etime,stat,cmd",
    ]
    output = subprocess.check_output(ps_command, text=True)

    for line in output.splitlines()[1:]:
        if not line:
            continue

        pid, pcpu, pmem, rss_kib, vsz_kib, etime, stat, cmd = line.split(maxsplit=7)

        sample.add_pid(
            pid=int(pid),
            stats=ProcessStats(
                pcpu=float(pcpu),
                pmem=float(pmem),
                rss=int(rss_kib) * 1024,
                vsz=int(vsz_kib) * 1024,
                timestamp=datetime.now().astimezone().isoformat(),
                etime=etime,
                stat=Counter([stat]),
                cmd=cmd,
            ),
        )
    sample.averages = Averages.from_sample(sample=sample)
    return sample


def _try_to_get_sid(pid: int) -> int:
    """
    It is possible that the `pid` returned by the top `ps` call no longer exists at time of `getsid` request.
    """
    try:
        return os.getsid(pid)
    except ProcessLookupError as exc:
        lgr.debug(f"Error fetching session ID for PID {pid}: {str(exc)}")
        return -1


def _get_ps_lines_mac() -> list[str]:
    ps_command = [
        "ps",
        "-ax",
        "-o",
        "pid,pcpu,pmem,rss,vsz,etime,stat,args",
    ]
    output = subprocess.check_output(ps_command, text=True)

    lines = [line for line in output.splitlines()[1:] if line]
    return lines


def _add_pid_to_sample_from_line_mac(
    line: str, pid_to_matching_sid: dict[int, int], sample: Sample
) -> None:
    pid, pcpu, pmem, rss_kb, vsz_kb, etime, stat, cmd = line.split(maxsplit=7)

    if pid_to_matching_sid.get(int(pid)) is not None:
        sample.add_pid(
            pid=int(pid),
            stats=ProcessStats(
                pcpu=float(pcpu),
                pmem=float(pmem),
                rss=int(rss_kb) * 1024,
                vsz=int(vsz_kb) * 1024,
                timestamp=datetime.now().astimezone().isoformat(),
                etime=etime,
                stat=Counter([stat]),
                cmd=cmd,
            ),
        )


def _get_sample_mac(session_id: int) -> Optional[Sample]:
    sample = Sample()

    lines = _get_ps_lines_mac()
    pid_to_matching_sid = {
        pid: sid
        for line in lines
        if (sid := _try_to_get_sid(pid=(pid := int(line.split(maxsplit=1)[0]))))
        == session_id
    }

    if not pid_to_matching_sid:
        lgr.debug(f"No processes found for session ID {session_id}.")
        return None

    # collections.deque with maxlen=0 is used to approximate the
    # performance of list comprehension (superior to basic for-loop)
    # and also does not store `None` (or other) return values
    deque(
        (
            _add_pid_to_sample_from_line_mac(  # type: ignore[func-returns-value]
                line=line, pid_to_matching_sid=pid_to_matching_sid, sample=sample
            )
            for line in lines
        ),
        maxlen=0,
    )

    sample.averages = Averages.from_sample(sample=sample)
    return sample


_get_sample_per_system = {
    "Linux": _get_sample_linux,
    "Darwin": _get_sample_mac,
}


class PsSampler:
    """Sampler that uses `ps` to collect per-process stats."""

    name = "ps"

    def sample(self, session_id: int) -> Optional[Sample]:
        return _get_sample_per_system[SYSTEM](session_id)


_CGROUP_V2_ROOT = Path("/sys/fs/cgroup")


def _detect_cgroup_v2_path() -> Path:
    """Return the absolute path to duct's own cgroup v2 directory.

    Raises NotImplementedError if cgroup v2 unified hierarchy is not
    mounted, or if /proc/self/cgroup does not expose a v2 entry.
    """
    controllers = _CGROUP_V2_ROOT / "cgroup.controllers"
    if not controllers.exists():
        raise NotImplementedError(
            "cgroup-ps-hybrid requires cgroup v2 unified hierarchy at "
            f"{_CGROUP_V2_ROOT}; this host does not appear to have v2 mounted"
        )
    # cgroup v2 entry in /proc/<pid>/cgroup has the shape "0::/<path>".
    proc_cgroup = Path("/proc/self/cgroup").read_text()
    for line in proc_cgroup.splitlines():
        if line.startswith("0::"):
            rel = line.split("::", 1)[1].strip().lstrip("/")
            return _CGROUP_V2_ROOT / rel
    raise NotImplementedError(
        "cgroup-ps-hybrid could not find a cgroup v2 entry ('0::/...') in "
        "/proc/self/cgroup"
    )


def _read_cgroup_cpu_usage_usec(cgroup_root: Path) -> int:
    """Read cumulative CPU microseconds from cgroup v2 ``cpu.stat``."""
    for line in (cgroup_root / "cpu.stat").read_text().splitlines():
        if line.startswith("usage_usec "):
            return int(line.split()[1])
    raise RuntimeError(f"usage_usec not present in {cgroup_root / 'cpu.stat'}")


class CgroupSampler:
    """Hybrid cgroup v2 + ps sampler.

    Session totals (``total_rss``, ``total_pcpu``) come from kernel
    cgroup counters; per-pid stats come from a ``ps`` sub-sample. The
    ``sampler`` tag on each emitted record disambiguates the source.

    Reader mode only: duct does NOT create a cgroup; it reads the one
    it already lives in via ``/proc/self/cgroup``. This requires
    ``--mode=current-session`` so duct and the tracked command share a
    cgroup (enforced in ``_duct_main.execute``).

    TODO(poc): our polling shape (sample-at-interval + Sample.aggregate
    max) is inherited from the ps model. cgroup could emit cumulative/
    delta directly -- e.g. one ``memory.peak`` read at end-of-run
    instead of max-of-currents -- but that would require reshaping the
    Sample/Report pipeline. Deferred post-POC.
    """

    name = "cgroup-ps-hybrid"

    def __init__(self) -> None:
        self._cgroup_root = _detect_cgroup_v2_path()
        # Baseline for delta-based pcpu on the first sample.
        self._last_cpu_usec = _read_cgroup_cpu_usage_usec(self._cgroup_root)
        self._last_cpu_time = time.monotonic()

    def sample(self, session_id: int) -> Optional[Sample]:
        # Per-pid stats via the ps path so records still carry the pid
        # breakdown users expect from duct.
        sample = _get_sample_per_system[SYSTEM](session_id)
        if sample is None:
            return None
        try:
            # Memory: session total from cgroup (replaces the ps sum).
            mem_current = int(
                (self._cgroup_root / "memory.current").read_text().strip()
            )
            sample.total_rss = mem_current

            # CPU: delta of cumulative usage_usec over the last interval.
            now_usec = _read_cgroup_cpu_usage_usec(self._cgroup_root)
            now_time = time.monotonic()
            delta_sec = now_time - self._last_cpu_time
            if delta_sec > 0:
                delta_usec = now_usec - self._last_cpu_usec
                # usage_usec / elapsed_usec * 100 = percent of one core.
                sample.total_pcpu = delta_usec / delta_sec / 10_000
            self._last_cpu_usec = now_usec
            self._last_cpu_time = now_time
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"cgroup read failed at {self._cgroup_root}: {exc}"
            ) from exc

        # TODO(poc): total_vsz and total_pmem remain ps-sourced; cgroup
        # v2 has no direct analogs (memory.current is already physical).
        # TODO(poc): overwrite full_run_stats.total_rss with memory.peak
        # at end of run for a truer run-level peak than max-of-currents.
        # TODO(poc): this assumes the tracked command stays in duct's
        # cgroup; systemd-run or similar would migrate the child out
        # and silently break the measurement.

        # Recompute averages so they reflect the cgroup-sourced totals
        # rather than the stale ps-sourced values set by _get_sample_*.
        sample.averages = Averages.from_sample(sample=sample)
        return sample


Sampler = Union[PsSampler, CgroupSampler]


def make_sampler(name: str) -> Sampler:
    """Factory: resolve a sampler name (as passed on the CLI) to an instance."""
    if name == PsSampler.name:
        return PsSampler()
    if name == CgroupSampler.name:
        return CgroupSampler()
    raise ValueError(f"unknown sampler: {name!r}")

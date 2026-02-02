"""Platform-specific process sampling for con-duct."""

from __future__ import annotations
from collections import Counter, deque
from datetime import datetime
import logging
import os
import platform
import subprocess
import sys
from typing import Callable, Optional
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
_get_sample: Callable[[int], Optional[Sample]] = _get_sample_per_system[SYSTEM]  # type: ignore[assignment]

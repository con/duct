"""Ephemeral CPU workload: short-lived parallel children that die fast.

Forks N child processes in parallel, each busy-loops on CPU for
``work_ms`` milliseconds, then exits. The parent then sleeps for
``hold_ms`` milliseconds so duct gets at least one sample window
*after* all children have died.

Ground truth: the cgroup used approximately ``N * work_ms`` total CPU
milliseconds in a span of ``work_ms`` wall milliseconds -- i.e. a
burst at roughly ``N * 100%`` peak pcpu. A sampler that reads
cumulative cgroup counters (``cpu.stat.usage_usec``) captures this
even if the children have already exited by sample time. A sampler
that relies on per-pid snapshots at sample time (``ps -s <sid>``)
sees an empty session and misses the burst.

Standalone usage (without duct):

    python test/data/workloads/ephemeral_cpu.py <num_workers> \\
        <work_ms> <hold_ms>
"""

from __future__ import annotations
import multiprocessing
import sys
import time


def _busy(duration_s: float) -> None:
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        pass


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "usage: ephemeral_cpu.py <num_workers> <work_ms> <hold_ms>",
            file=sys.stderr,
        )
        sys.exit(2)
    num_workers = int(sys.argv[1])
    work_ms = int(sys.argv[2])
    hold_ms = int(sys.argv[3])

    work_s = work_ms / 1000
    procs = [
        multiprocessing.Process(target=_busy, args=(work_s,))
        for _ in range(num_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

    # Keep the parent alive so duct's monitor thread gets at least one
    # sample window after all children have exited. Without this, the
    # workload may end before any sampling happens at all.
    time.sleep(hold_ms / 1000)


if __name__ == "__main__":
    main()

"""Steady-state CPU workload: pin to one core, busy-loop for N seconds.

Ground truth: a single-process workload pinned to one core saturates
that core, so any accurate sampler should report ``peak_pcpu ~= 100%``
and wall-clock time roughly equal to the requested duration.

Standalone usage (without duct):

    python test/data/workloads/steady_cpu.py <duration_seconds>
"""

from __future__ import annotations
import os
import sys
import time


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: steady_cpu.py <duration_seconds>", file=sys.stderr)
        sys.exit(2)
    duration = float(sys.argv[1])

    # Pin to one core so the pcpu ceiling is deterministic across machines.
    # Linux-only; macOS lacks a stdlib equivalent, so we run unpinned there.
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {0})

    end = time.monotonic() + duration
    while time.monotonic() < end:
        pass


if __name__ == "__main__":
    main()

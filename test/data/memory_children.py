#!/usr/bin/env python3
"""Spawn child processes that each allocate a known amount of memory.

Usage: memory_children.py <num_children> <mb_per_child> <hold_seconds>

Each child allocates mb_per_child MB and holds it for hold_seconds.
The parent waits for all children to finish.
"""

from __future__ import annotations
import multiprocessing
import sys
import time


def _allocate_and_hold(mb: int, seconds: float) -> None:
    """Allocate mb megabytes and hold for seconds."""
    data = bytearray(mb * 1024 * 1024)
    assert data  # prevent optimization
    time.sleep(seconds)


def main() -> None:
    num_children = int(sys.argv[1])
    mb_per_child = int(sys.argv[2])
    hold_seconds = float(sys.argv[3])

    processes = []
    for _ in range(num_children):
        p = multiprocessing.Process(
            target=_allocate_and_hold, args=(mb_per_child, hold_seconds)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()

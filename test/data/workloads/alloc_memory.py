"""Single-process memory allocation workload.

Allocates a contiguous bytearray of known size and holds it for the
requested duration. In CPython, ``bytearray(N)`` is eagerly allocated,
so RSS grows by ~N bytes immediately (plus a small Python overhead).

Ground truth: ``peak_rss >= size_mb * 1024 * 1024`` for any sampler
that reports RSS (ps sums per-process rss; cgroup-v2 reports
``memory.peak`` for the session).

Standalone usage (without duct):

    python test/data/workloads/alloc_memory.py <size_mb> <hold_seconds>
"""

from __future__ import annotations
import sys
import time


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "usage: alloc_memory.py <size_mb> <hold_seconds>",
            file=sys.stderr,
        )
        sys.exit(2)
    size_mb = int(sys.argv[1])
    hold_seconds = float(sys.argv[2])

    buffer = bytearray(size_mb * 1024 * 1024)
    # Touch the buffer so pages are guaranteed resident (defensive -
    # CPython bytearray is already eagerly allocated).
    assert buffer[0] == 0
    time.sleep(hold_seconds)


if __name__ == "__main__":
    main()

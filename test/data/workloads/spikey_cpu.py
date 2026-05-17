"""Spikey CPU workload: multi-threaded native bursts (pcpu-overshoot trigger).

Forks N parallel worker processes. Each worker spawns M threads that
call ``hashlib.pbkdf2_hmac`` in a tight loop for ``duration`` seconds.
``pbkdf2_hmac`` releases the GIL inside its C implementation, so the
threads actually parallelize across cores -- this is a principled
stdlib-only equivalent of the real #399 trigger (pip compiling C
extensions under tox: short-lived multi-core native work).

Ground truth: across ``duration`` wall-seconds the cgroup uses up to
``min(cpu_count, N*M) * duration`` CPU-seconds. Real peak instantaneous
%CPU is bounded by ``cpu_count * 100%``.

Pathology on Linux (Bug 1, RESEARCH.md section 1.1): ``ps -o pcpu``
is ``cputime / elapsed`` accumulated over each process's lifetime.
For a young multi-threaded worker, the small elapsed denominator
inflates the ratio arbitrarily. Duct's per-pid summing across the
session then compounds this across workers. Real-world cases hit
>1000% reported pcpu.

Standalone usage (without duct):

    python test/data/workloads/spikey_cpu.py <num_workers> \\
        <num_threads> <duration_seconds>
"""

from __future__ import annotations
import hashlib
import multiprocessing
import sys
import threading
import time

_PBKDF2_ITERATIONS = 10_000


def _worker(num_threads: int, duration_s: float) -> None:
    """Spawn num_threads threads doing pbkdf2_hmac until duration elapses."""
    end = time.monotonic() + duration_s

    def burst() -> None:
        while time.monotonic() < end:
            # Fresh bytes each round so the interpreter can't cache.
            hashlib.pbkdf2_hmac("sha256", b"password", b"salt", _PBKDF2_ITERATIONS)

    threads = [threading.Thread(target=burst) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "usage: spikey_cpu.py <num_workers> <num_threads> " "<duration_seconds>",
            file=sys.stderr,
        )
        sys.exit(2)
    num_workers = int(sys.argv[1])
    num_threads = int(sys.argv[2])
    duration_s = float(sys.argv[3])

    procs = [
        multiprocessing.Process(target=_worker, args=(num_threads, duration_s))
        for _ in range(num_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()

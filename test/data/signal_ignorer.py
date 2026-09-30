#!/usr/bin/env python3
"""Ignore SIGINT, reporting progress through the file given as argv[1].

Writes "ready" once the handler is installed, then one "SIGINT" line per
SIGINT received, so a test can wait for each step instead of sleeping.
"""

import signal
import sys
import time
from types import FrameType
from typing import Optional


def report(line: str) -> None:
    with open(sys.argv[1], "a") as f:
        f.write(line + "\n")


def handle_signal(sig: int, _frame: Optional[FrameType]) -> None:
    print(f"Received {sig}")
    report("SIGINT")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.siginterrupt(
        signal.SIGINT, False
    )  # Restart interrupted system calls so we can test multiple SIGINTS
    report("ready")
    t0 = time.time()
    while time.time() - t0 < 10:
        time.sleep(0.01)

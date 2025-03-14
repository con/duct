#!/usr/bin/env python3
import signal
import time
from types import FrameType
from typing import Optional


def handle_signal(sig: int, _frame: Optional[FrameType]) -> None:
    print(f"Received {sig}")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.siginterrupt(
        signal.SIGINT, False
    )  # Restart interrupted system calls so we can test multiple SIGINTS
    time.sleep(4)

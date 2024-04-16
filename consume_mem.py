#!/usr/bin/env python3

import os
import sys
import time


def consume_memory(size_in_mb):
    """
    Consumes approximately `size_in_mb` megabytes of memory.

    Parameters:
    size_in_mb (int): Amount of memory to consume in megabytes.
    """
    bytes_per_mb = 1024 * 1024  # 1MB is 1024 * 1024 bytes
    data = bytearray(size_in_mb * bytes_per_mb)
    print(type(data))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python consume_memory.py <size_in_mb> <time_in_sec>")
        sys.exit(1)

    print(f"PID of this process: {os.getpid()}")
    size_in_mb = int(sys.argv[1])
    time_to_spend = int(sys.argv[2])

    consume_memory(size_in_mb)
    t0 = time.time()
    while time.time() - t0 < time_to_spend:
        pass

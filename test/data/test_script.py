#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
import time


def consume_cpu(duration: int, load: int) -> None:
    """Function to consume CPU proportional to 'load' for 'duration' seconds"""
    end_time = time.time() + duration
    while time.time() < end_time:
        for _ in range(load):
            pass  # Busy-wait


def consume_memory(size: int) -> bytearray:
    """Function to consume amount of memory specified by 'size' in megabytes"""
    # Create a list of size MB
    bytes_in_mb = 1024 * 1024
    return bytearray(size * bytes_in_mb)


def main(duration: int, cpu_load: int, memory_size: int) -> None:
    print("this is of test of STDOUT")
    print("this is of test of STDERR", file=sys.stderr)
    _mem_hold = consume_memory(memory_size)  # noqa
    consume_cpu(duration, cpu_load)
    print(
        f"Test completed. Consumed {memory_size} MB for {duration} seconds with CPU load factor {cpu_load}."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test script to consume CPU and memory."
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Duration to run the test in seconds."
    )
    parser.add_argument(
        "--cpu-load", type=int, default=10000, help="Load factor to simulate CPU usage."
    )
    parser.add_argument(
        "--memory-size",
        type=int,
        default=10,
        help="Amount of memory to allocate in MB.",
    )
    args = parser.parse_args()
    main(args.duration, args.cpu_load, args.memory_size)

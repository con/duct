#!/usr/bin/env python3

import argparse
import sys
import time


def consume_cpu(duration, _):
    """Function to consume CPU proportional to 'load' for 'duration' seconds"""
    for i in range(duration):
        print(f"out: {i}")
        print(f"err: {i}", file=sys.stderr)
        time.sleep(1)


def consume_memory(size):
    """Function to consume amount of memory specified by 'size' in megabytes"""
    # Create a list of size MB
    bytes_in_mb = 1024 * 1024
    _memory = bytearray(size * bytes_in_mb)  # noqa


def main(duration, cpu_load, memory_size):
    print("Printing something to STDOUT at start")
    print("Printing something to STDERR at start", file=sys.stderr)
    consume_memory(memory_size)
    consume_cpu(duration, cpu_load)
    print(
        f"Test completed. Consumed {memory_size} MB for {duration} seconds with CPU load factor {cpu_load}."
    )
    print("Printing something to STDOUT at finish")
    print("Printing something to STDERR at finish", file=sys.stderr)


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

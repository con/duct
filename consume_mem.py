import os
import sys


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
    if len(sys.argv) != 2:
        print("Usage: python consume_memory.py <size_in_mb>")
        sys.exit(1)

    size_in_mb = int(sys.argv[1])
    consume_memory(size_in_mb)
    print(f"PID of this process: {os.getpid()}")

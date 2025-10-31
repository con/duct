#!/usr/bin/env python3
"""
Resource consumption test script for testing resource monitoring tools.
Consumes various amounts of VSS, RSS, and CPU over configurable time periods.
"""

import argparse
import json
import mmap
import multiprocessing
import os
import time
from typing import Any, Dict


class ResourceConsumer:
    def __init__(self):
        self.allocated_memory = []
        self.mapped_memory = []
        self.processes = []

    def consume_rss(self, size_mb: int):
        """Consume RSS by allocating and touching memory"""
        size_bytes = size_mb * 1024 * 1024
        print(f"Allocating {size_mb}MB RSS...")

        # Allocate memory and actually touch it to force RSS consumption
        data = bytearray(size_bytes)
        # Touch every page (4KB) to ensure it's in RSS
        for i in range(0, len(data), 4096):
            data[i] = 1

        self.allocated_memory.append(data)
        print(f"RSS allocated: {size_mb}MB")

    def consume_vss(self, size_mb: int):
        """Consume VSS using memory mapping (doesn't immediately consume RSS)"""
        size_bytes = size_mb * 1024 * 1024
        print(f"Mapping {size_mb}MB VSS...")

        # Create anonymous memory mapping (VSS but not RSS until accessed)
        mapped = mmap.mmap(-1, size_bytes)
        self.mapped_memory.append(mapped)
        print(f"VSS mapped: {size_mb}MB")

    def consume_cpu(self, cores: int, duration_seconds: int, intensity: float = 1.0):
        """Consume CPU by spinning threads"""
        print(
            f"Starting CPU consumption: {cores} cores at {intensity*100}% for {duration_seconds}s..."
        )

        def cpu_burn(duration, intensity):
            """Burn CPU cycles with configurable intensity"""
            end_time = time.time() + duration
            while time.time() < end_time:
                # Busy work
                if intensity >= 1.0:
                    # Full burn
                    _ = sum(i * i for i in range(1000))
                else:
                    # Partial burn with sleep
                    _ = sum(i * i for i in range(int(1000 * intensity)))
                    time.sleep((1 - intensity) * 0.01)

        # Start processes to burn CPU
        for _ in range(cores):
            p = multiprocessing.Process(
                target=cpu_burn, args=(duration_seconds, intensity)
            )
            p.start()
            self.processes.append(p)

    def release_memory(self, rss_mb: int = 0, vss_mb: int = 0):
        """Release allocated memory"""
        if rss_mb > 0 and self.allocated_memory:
            print(f"Releasing {rss_mb}MB RSS...")
            # Release RSS memory (approximate)
            bytes_to_release = rss_mb * 1024 * 1024
            released = 0
            while self.allocated_memory and released < bytes_to_release:
                mem = self.allocated_memory.pop()
                released += len(mem)
                del mem

        if vss_mb > 0 and self.mapped_memory:
            print(f"Releasing {vss_mb}MB VSS...")
            # Release VSS memory
            for _ in range(min(vss_mb // 100, len(self.mapped_memory))):
                if self.mapped_memory:
                    mapped = self.mapped_memory.pop()
                    mapped.close()

    def wait_for_processes(self):
        """Wait for CPU burning processes to complete"""
        for p in self.processes:
            p.join()
        self.processes.clear()
        print("CPU consumption completed")

    def cleanup(self):
        """Clean up all resources"""
        print("Cleaning up resources...")
        self.allocated_memory.clear()
        for mapped in self.mapped_memory:
            mapped.close()
        self.mapped_memory.clear()
        for p in self.processes:
            if p.is_alive():
                p.terminate()
        self.processes.clear()


def run_phase(consumer: ResourceConsumer, phase: Dict[str, Any]):
    """Execute a single phase of resource consumption"""
    name = phase.get("name", "Unnamed Phase")
    duration = phase.get("duration", 10)

    print(f"\n=== Phase: {name} (Duration: {duration}s) ===")

    # Memory consumption
    if "rss_mb" in phase:
        consumer.consume_rss(phase["rss_mb"])

    if "vss_mb" in phase:
        consumer.consume_vss(phase["vss_mb"])

    # CPU consumption (non-blocking)
    if "cpu_cores" in phase:
        intensity = phase.get("cpu_intensity", 1.0)
        consumer.consume_cpu(phase["cpu_cores"], duration, intensity)

    # Memory release
    if "release_rss_mb" in phase:
        consumer.release_memory(rss_mb=phase["release_rss_mb"])

    if "release_vss_mb" in phase:
        consumer.release_memory(vss_mb=phase["release_vss_mb"])

    # Wait for the phase duration
    print(f"Running for {duration} seconds...")
    time.sleep(duration)

    # Wait for CPU processes if any were started
    consumer.wait_for_processes()


def main():
    parser = argparse.ArgumentParser(description="Resource consumption test script")
    parser.add_argument("--config", type=str, help="JSON config file with phases")
    parser.add_argument("--demo", action="store_true", help="Run demo scenario")
    args = parser.parse_args()

    consumer = ResourceConsumer()

    try:
        if args.demo:
            # Demo scenario with various resource patterns
            phases = [
                {
                    "name": "Baseline",
                    "duration": 5,
                },
                {
                    "name": "Low Memory",
                    "duration": 10,
                    "rss_mb": 50,
                    "vss_mb": 100,
                },
                {
                    "name": "Add CPU Load",
                    "duration": 10,
                    "cpu_cores": 2,
                    "cpu_intensity": 0.5,
                },
                {
                    "name": "High Memory + CPU",
                    "duration": 15,
                    "rss_mb": 200,
                    "vss_mb": 300,
                    "cpu_cores": 4,
                    "cpu_intensity": 0.8,
                },
                {
                    "name": "Memory Spike",
                    "duration": 5,
                    "rss_mb": 500,
                },
                {
                    "name": "Release Memory",
                    "duration": 10,
                    "release_rss_mb": 500,
                    "cpu_cores": 1,
                    "cpu_intensity": 0.3,
                },
                {
                    "name": "Cool Down",
                    "duration": 5,
                },
            ]

        elif args.config:
            # Load phases from config file
            with open(args.config, "r") as f:
                config = json.load(f)
                phases = config.get("phases", [])
        else:
            # Default simple test
            phases = [
                {
                    "name": "Simple Test",
                    "duration": 10,
                    "rss_mb": 100,
                    "vss_mb": 200,
                    "cpu_cores": 2,
                    "cpu_intensity": 0.7,
                }
            ]

        print(f"Starting resource consumption test with {len(phases)} phases")
        print(f"Process PID: {os.getpid()}")
        print(
            "You can monitor this process with tools like htop, top, or your resource monitor"
        )

        # Run each phase
        for phase in phases:
            run_phase(consumer, phase)

        print("\n=== Test Completed ===")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        consumer.cleanup()
        print("Cleanup complete")


if __name__ == "__main__":
    main()

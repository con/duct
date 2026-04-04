"""Validate that duct-reported resource stats match actual resource usage.

These tests run programs with known, predictable resource consumption
(memory allocation, CPU usage) and verify that duct's measurements
fall within expected bounds. This bridges the gap between unit tests
(which verify aggregation math) and real-world accuracy.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from utils import run_duct_command

from con_duct._constants import SUFFIXES

TEST_SCRIPT = str(Path(__file__).parent.parent / "data" / "test_script.py")


def _read_info(temp_output_dir: str) -> dict:
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as f:
        return json.loads(f.read())


def _read_usage(temp_output_dir: str) -> list[dict]:
    lines = []
    with open(os.path.join(temp_output_dir, SUFFIXES["usage"])) as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    return lines


@pytest.mark.flaky(reruns=3)
def test_memory_allocation_detected(temp_output_dir: str) -> None:
    """Allocate a known amount of memory and verify duct detects it.

    Runs test_script.py which allocates --memory-size MB via bytearray.
    Duct should report peak RSS at least that large (plus Python overhead).
    """
    alloc_mb = 50
    alloc_bytes = alloc_mb * 1024 * 1024

    assert (
        run_duct_command(
            [
                sys.executable,
                TEST_SCRIPT,
                "--duration",
                "2",
                "--memory-size",
                str(alloc_mb),
                "--cpu-load",
                "1",
            ],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    info = _read_info(temp_output_dir)
    summary = info["execution_summary"]

    peak_rss = summary["peak_rss"]
    # RSS must be at least the allocated amount (bytearray is contiguous in memory)
    assert peak_rss >= alloc_bytes, (
        f"peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"allocated ({alloc_mb} MB)"
    )
    # Sanity upper bound: shouldn't report more than allocation + 200MB overhead
    overhead_limit = alloc_bytes + 200 * 1024 * 1024
    assert peak_rss < overhead_limit, (
        f"peak_rss ({peak_rss / 1024 / 1024:.1f} MB) unreasonably high "
        f"for {alloc_mb} MB allocation"
    )


@pytest.mark.flaky(reruns=3)
def test_wall_clock_time_accurate(temp_output_dir: str) -> None:
    """Verify wall clock time matches actual sleep duration."""
    duration = 1.0

    assert (
        run_duct_command(
            ["sleep", str(duration)],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    info = _read_info(temp_output_dir)
    wall_clock = info["execution_summary"]["wall_clock_time"]

    # Should be close to the requested duration
    assert wall_clock >= duration, (
        f"wall_clock_time ({wall_clock:.2f}s) < requested sleep ({duration}s)"
    )
    # Allow generous overhead for slow CI environments
    assert wall_clock < duration + 2.0, (
        f"wall_clock_time ({wall_clock:.2f}s) unreasonably high "
        f"for {duration}s sleep"
    )


@pytest.mark.flaky(reruns=3)
def test_idle_process_low_cpu(temp_output_dir: str) -> None:
    """A sleeping process should report near-zero CPU usage."""
    assert (
        run_duct_command(
            ["sleep", "1"],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    info = _read_info(temp_output_dir)
    summary = info["execution_summary"]

    assert summary["peak_pcpu"] < 5.0, (
        f"peak_pcpu ({summary['peak_pcpu']}) should be near-zero for sleep"
    )
    assert summary["average_pcpu"] < 5.0, (
        f"average_pcpu ({summary['average_pcpu']}) should be near-zero for sleep"
    )


@pytest.mark.flaky(reruns=3)
def test_cpu_intensive_detected(temp_output_dir: str) -> None:
    """A busy-loop process should report significant CPU usage."""
    assert (
        run_duct_command(
            [
                sys.executable,
                TEST_SCRIPT,
                "--duration",
                "2",
                "--memory-size",
                "1",
                "--cpu-load",
                "100000",
            ],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    info = _read_info(temp_output_dir)
    summary = info["execution_summary"]

    # A busy-loop should show meaningful CPU usage
    assert summary["peak_pcpu"] > 10.0, (
        f"peak_pcpu ({summary['peak_pcpu']}) should be significant for busy-loop"
    )


@pytest.mark.flaky(reruns=3)
def test_usage_samples_recorded(temp_output_dir: str) -> None:
    """Verify that usage.jsonl contains samples with expected structure."""
    assert (
        run_duct_command(
            ["sleep", "1"],
            sample_interval=0.1,
            report_interval=0.3,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    samples = _read_usage(temp_output_dir)

    # With 1s sleep and 0.3s report interval, expect at least 2 reports
    assert len(samples) >= 2, (
        f"Expected at least 2 usage samples, got {len(samples)}"
    )

    for i, sample in enumerate(samples):
        assert "timestamp" in sample, f"Sample {i} missing timestamp"
        assert "totals" in sample, f"Sample {i} missing totals"
        totals = sample["totals"]
        assert "rss" in totals, f"Sample {i} totals missing rss"
        assert "pcpu" in totals, f"Sample {i} totals missing pcpu"
        # RSS should be non-negative
        assert totals["rss"] >= 0, f"Sample {i} has negative rss: {totals['rss']}"


@pytest.mark.flaky(reruns=3)
def test_multiple_samples_show_consistent_memory(temp_output_dir: str) -> None:
    """Memory held for the full duration should appear consistently across samples."""
    alloc_mb = 30
    alloc_bytes = alloc_mb * 1024 * 1024

    assert (
        run_duct_command(
            [
                sys.executable,
                TEST_SCRIPT,
                "--duration",
                "2",
                "--memory-size",
                str(alloc_mb),
                "--cpu-load",
                "1",
            ],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    samples = _read_usage(temp_output_dir)
    assert len(samples) >= 2, f"Expected multiple samples, got {len(samples)}"

    # At least some samples should show the allocated memory
    samples_above_threshold = [
        s for s in samples if s["totals"]["rss"] >= alloc_bytes
    ]
    assert len(samples_above_threshold) >= 1, (
        f"No usage samples showed RSS >= {alloc_mb} MB. "
        f"Sample RSS values: {[s['totals']['rss'] / 1024 / 1024 for s in samples]}"
    )

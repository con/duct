"""Validate that duct-reported resource stats match actual resource usage.

These tests run programs with known, predictable resource consumption
(memory allocation, CPU usage) and verify that duct's measurements
fall within expected bounds. This bridges the gap between unit tests
(which verify aggregation math) and real-world accuracy.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from typing import Any
import pytest
from utils import run_duct_command
from con_duct._constants import SUFFIXES

TEST_DATA_DIR = Path(__file__).parent.parent / "data"
TEST_SCRIPT = str(TEST_DATA_DIR / "test_script.py")
MEMORY_CHILDREN_SCRIPT = str(TEST_DATA_DIR / "memory_children.py")


def _read_info(temp_output_dir: str) -> Any:
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as f:
        return json.loads(f.read())


def _read_usage(temp_output_dir: str) -> list[Any]:
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
    assert (
        wall_clock >= duration
    ), f"wall_clock_time ({wall_clock:.2f}s) < requested sleep ({duration}s)"
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

    assert (
        summary["peak_pcpu"] < 5.0
    ), f"peak_pcpu ({summary['peak_pcpu']}) should be near-zero for sleep"
    assert (
        summary["average_pcpu"] < 5.0
    ), f"average_pcpu ({summary['average_pcpu']}) should be near-zero for sleep"


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
    assert (
        summary["peak_pcpu"] > 10.0
    ), f"peak_pcpu ({summary['peak_pcpu']}) should be significant for busy-loop"


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
    assert len(samples) >= 2, f"Expected at least 2 usage samples, got {len(samples)}"

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
    samples_above_threshold = [s for s in samples if s["totals"]["rss"] >= alloc_bytes]
    assert len(samples_above_threshold) >= 1, (
        f"No usage samples showed RSS >= {alloc_mb} MB. "
        f"Sample RSS values: {[s['totals']['rss'] / 1024 / 1024 for s in samples]}"
    )


# --- Child/forked process resource validation ---


@pytest.mark.flaky(reruns=3)
def test_child_processes_memory_aggregated(temp_output_dir: str) -> None:
    """Spawn children that each allocate memory; verify total RSS reflects the sum.

    Uses multiprocessing to fork N children each holding M MB.
    The total RSS across all processes should be at least N * M MB.
    """
    num_children = 3
    mb_per_child = 20
    hold_seconds = 3.0
    total_alloc_bytes = num_children * mb_per_child * 1024 * 1024

    assert (
        run_duct_command(
            [
                sys.executable,
                MEMORY_CHILDREN_SCRIPT,
                str(num_children),
                str(mb_per_child),
                str(hold_seconds),
            ],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    info = _read_info(temp_output_dir)
    summary = info["execution_summary"]

    # peak_rss is total across all tracked processes
    peak_rss = summary["peak_rss"]
    assert peak_rss >= total_alloc_bytes, (
        f"peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"total allocation ({num_children} x {mb_per_child} = "
        f"{num_children * mb_per_child} MB)"
    )

    # Also check usage.jsonl samples show multiple processes
    samples = _read_usage(temp_output_dir)
    max_pids_seen = max(len(s["processes"]) for s in samples)
    # Should see parent + N children (at least N+1 processes)
    assert max_pids_seen >= num_children + 1, (
        f"Expected at least {num_children + 1} processes in samples, "
        f"but max PIDs in any sample was {max_pids_seen}"
    )


@pytest.mark.flaky(reruns=3)
def test_child_processes_individually_tracked(temp_output_dir: str) -> None:
    """Verify per-process stats in usage.jsonl track individual children."""
    num_children = 2
    mb_per_child = 25
    hold_seconds = 3.0
    child_alloc_bytes = mb_per_child * 1024 * 1024

    assert (
        run_duct_command(
            [
                sys.executable,
                MEMORY_CHILDREN_SCRIPT,
                str(num_children),
                str(mb_per_child),
                str(hold_seconds),
            ],
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )

    samples = _read_usage(temp_output_dir)

    # Find samples where children are running (multiple processes visible)
    multi_proc_samples = [s for s in samples if len(s["processes"]) > 1]
    assert len(multi_proc_samples) >= 1, "No samples captured multiple processes"

    # In at least one sample, individual child processes should show their allocation
    # (each child holds mb_per_child MB)
    children_with_expected_rss = set()
    for sample in multi_proc_samples:
        for pid, proc in sample["processes"].items():
            if proc["rss"] >= child_alloc_bytes:
                children_with_expected_rss.add(pid)

    rss_debug = [
        {pid: p["rss"] / 1024 / 1024 for pid, p in s["processes"].items()}
        for s in multi_proc_samples[:3]
    ]
    assert len(children_with_expected_rss) >= num_children, (
        f"Expected at least {num_children} child processes with RSS >= "
        f"{mb_per_child} MB, found {len(children_with_expected_rss)}. "
        f"Per-process RSS values: {rss_debug}"
    )

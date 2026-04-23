"""Sampler matrix: per-(sampler, workload, property) cells.

Each test is marked with ``@pytest.mark.sampler_matrix`` carrying the
(sampler, workload, property, expected) metadata. The conftest hook
converts ``expected="fail"`` into ``xfail(strict=True)``, so the suite
stays green both when a sampler meets an expected-pass claim AND when
a known limitation keeps on holding. Cells are emitted to
``.sampler_matrix_results.jsonl`` and pivoted into
``test/sampler_matrix_<sampler>.csv`` by
``scripts/gen_sampler_matrix.py``.

Conventions:

- Each test exercises exactly one cell of the matrix.
- Test name follows ``test_<sampler>_<workload>_<property>`` so the
  matrix story is readable in pytest output too.
- Short durations + small allocations so the matrix is cheap to run.

TODO: consolidate with ``test/duct_main/test_resource_validation.py``
once the POC direction lands. Both files exercise the same workloads
with similar bounds; the matrix version adds per-cell metadata and
xfail dispatch. Either merge or retire the duplicate after acceptance.
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

DATA_DIR = Path(__file__).parent.parent / "data"
WORKLOADS_DIR = DATA_DIR / "workloads"
ALLOC_MEMORY_SCRIPT = str(WORKLOADS_DIR / "alloc_memory.py")
STEADY_CPU_SCRIPT = str(WORKLOADS_DIR / "steady_cpu.py")
MEMORY_CHILDREN_SCRIPT = str(DATA_DIR / "memory_children.py")


def _read_info(temp_output_dir: str) -> Any:
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as f:
        return json.loads(f.read())


# ---- ps column ----


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="alloc_memory",
    property="peak_rss_reaches_alloc",
    expected="pass",
)
def test_ps_alloc_memory_peak_rss_reaches_alloc(temp_output_dir: str) -> None:
    alloc_mb = 50
    assert (
        run_duct_command(
            [sys.executable, ALLOC_MEMORY_SCRIPT, str(alloc_mb), "1.5"],
            sampler="ps",
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    assert peak_rss >= alloc_mb * 1024 * 1024, (
        f"peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"allocated ({alloc_mb} MB)"
    )


# N and M chosen so ps's per-pid shared-lib double-counting is large
# enough to reliably exceed a ceiling that cgroup totals would respect.
# Empirically: alloc=80 MB, ps reports ~135 MB, cgroup reports ~110 MB.
_MEM_CHILDREN_N = 4
_MEM_CHILDREN_M = 20


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="memory_children",
    property="peak_rss_reaches_alloc",
    expected="pass",
)
def test_ps_memory_children_peak_rss_reaches_alloc(
    temp_output_dir: str,
) -> None:
    assert (
        run_duct_command(
            [
                sys.executable,
                MEMORY_CHILDREN_SCRIPT,
                str(_MEM_CHILDREN_N),
                str(_MEM_CHILDREN_M),
                "1.5",
            ],
            sampler="ps",
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    alloc_bytes = _MEM_CHILDREN_N * _MEM_CHILDREN_M * 1024 * 1024
    assert peak_rss >= alloc_bytes, (
        f"peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"total allocation "
        f"({_MEM_CHILDREN_N * _MEM_CHILDREN_M} MB)"
    )


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="memory_children",
    property="peak_rss_no_overcount",
    expected="fail",
)
def test_ps_memory_children_peak_rss_no_overcount(
    temp_output_dir: str,
) -> None:
    """ps sums RSS per PID, double-counting shared library pages.

    Expected to fail: the sum of per-PID RSS reported by ps exceeds a
    realistic ceiling on actual physical memory used by the session.
    This is the #399 anchor: under cgroup-ps-hybrid, session totals
    come from the kernel and this assertion should hold.
    """
    assert (
        run_duct_command(
            [
                sys.executable,
                MEMORY_CHILDREN_SCRIPT,
                str(_MEM_CHILDREN_N),
                str(_MEM_CHILDREN_M),
                "1.5",
            ],
            sampler="ps",
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    # Ceiling: alloc + 40 MB (one shared-lib copy + generous slack).
    # cgroup session totals should fit; ps per-pid sum should not.
    alloc_bytes = _MEM_CHILDREN_N * _MEM_CHILDREN_M * 1024 * 1024
    ceiling = alloc_bytes + 40 * 1024 * 1024
    assert peak_rss <= ceiling, (
        f"ps reported peak_rss {peak_rss / 1024 / 1024:.1f} MB > "
        f"physical ceiling {ceiling / 1024 / 1024:.1f} MB "
        f"({_MEM_CHILDREN_N} children x {_MEM_CHILDREN_M} MB)"
    )


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="steady_cpu",
    property="peak_pcpu_reaches_floor",
    expected="pass",
)
def test_ps_steady_cpu_peak_pcpu_reaches_floor(
    temp_output_dir: str,
) -> None:
    duration = 2.0
    assert (
        run_duct_command(
            [sys.executable, STEADY_CPU_SCRIPT, str(duration)],
            sampler="ps",
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"]
    # One core pinned + busy-loop should push near 100%. Use a loose
    # floor to tolerate CI scheduling jitter.
    assert peak_pcpu >= 80.0, (
        f"peak_pcpu ({peak_pcpu}) should be >= 80% for one-core-pinned " f"busy-loop"
    )

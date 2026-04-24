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
import shutil
import subprocess
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

# Path to duct in the current venv -- resolves to .tox/py312/bin/duct
# under tox, .venv-austin/bin/duct in a direct venv invocation, etc.
DUCT_BIN = str(Path(sys.executable).parent / "duct")


def _read_info(temp_output_dir: str) -> Any:
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as f:
        return json.loads(f.read())


def _skip_unless_systemd_run_scope() -> None:
    """Skip the calling test unless ``systemd-run --user --scope`` is usable.

    Cgroup-matrix tests spawn each duct invocation in a transient
    systemd scope so the cgroup counters CgroupSampler reads are
    dedicated to just duct + its workload, not polluted by the test
    runner or sibling processes in the caller's cgroup. This requires:

    - ``systemd-run`` binary on PATH
    - a running user systemd instance (``systemctl --user status``
      succeeds)

    Missing either: skip, don't fail. These tests are opt-in via
    ``--cgroup-matrix`` already, but the skip-gate gives a useful
    reason when someone opts in on a host that can't run them.
    """
    if shutil.which("systemd-run") is None:
        pytest.skip("systemd-run not on PATH")
    probe = subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        capture_output=True,
        text=True,
    )
    # 'running', 'degraded' (some unit failed but system up), etc. are
    # all fine; only 'offline'/exit-nonzero-with-no-output means no user
    # systemd instance.
    if probe.returncode != 0 and not probe.stdout.strip():
        pytest.skip(f"user systemd not running: {probe.stderr.strip() or 'unknown'}")
    if not Path(DUCT_BIN).exists():
        pytest.skip(f"duct binary not found at {DUCT_BIN}")


def _run_duct_in_scope(out_prefix: str, workload_args: list[str]) -> None:
    """Run duct in a transient systemd scope so its cgroup is dedicated.

    The scope's cgroup contains exactly ``duct + workload`` -- pytest
    and anything else running on the host stay in their own cgroups.
    CgroupSampler therefore reads clean ``memory.current`` / ``cpu.stat``
    values, and matrix ceiling assertions can actually discriminate
    ps-sum-with-overcount vs. cgroup-physical-totals.
    """
    subprocess.run(
        [
            "systemd-run",
            "--user",
            "--scope",
            "--collect",
            "--quiet",
            "--",
            DUCT_BIN,
            "--sampler=cgroup-ps-hybrid",
            "--mode=current-session",
            "--log-level=ERROR",
            "--sample-interval=0.1",
            "--report-interval=0.5",
            "-p",
            out_prefix,
            *workload_args,
        ],
        check=True,
    )


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


# ---- cgroup-ps-hybrid column ----
#
# Opt-in: marked cgroup_matrix (see conftest.py --cgroup-matrix flag).
# Each test spawns duct in a transient systemd --user --scope so the
# cgroup CgroupSampler reads is dedicated to just duct + the workload.
# Without the scope, the ambient cgroup (user session, container root
# ns, etc.) contains far more memory than our workload and matrix
# assertions become meaningless.


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="alloc_memory",
    property="peak_rss_reaches_alloc",
    expected="pass",
)
def test_cgroup_alloc_memory_peak_rss_reaches_alloc(
    temp_output_dir: str,
) -> None:
    _skip_unless_systemd_run_scope()
    alloc_mb = 50
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[
            sys.executable,
            ALLOC_MEMORY_SCRIPT,
            str(alloc_mb),
            "1.5",
        ],
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    assert peak_rss >= alloc_mb * 1024 * 1024, (
        f"cgroup peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"allocated ({alloc_mb} MB)"
    )


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="memory_children",
    property="peak_rss_reaches_alloc",
    expected="pass",
)
def test_cgroup_memory_children_peak_rss_reaches_alloc(
    temp_output_dir: str,
) -> None:
    _skip_unless_systemd_run_scope()
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[
            sys.executable,
            MEMORY_CHILDREN_SCRIPT,
            str(_MEM_CHILDREN_N),
            str(_MEM_CHILDREN_M),
            "1.5",
        ],
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    alloc_bytes = _MEM_CHILDREN_N * _MEM_CHILDREN_M * 1024 * 1024
    assert peak_rss >= alloc_bytes, (
        f"cgroup peak_rss ({peak_rss / 1024 / 1024:.1f} MB) should be >= "
        f"total allocation "
        f"({_MEM_CHILDREN_N * _MEM_CHILDREN_M} MB)"
    )


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="memory_children",
    property="peak_rss_no_overcount",
    expected="pass",
)
def test_cgroup_memory_children_peak_rss_no_overcount(
    temp_output_dir: str,
) -> None:
    """cgroup memory.current reports physical memory, not per-pid sums.

    Expected to pass: this is the flip of the ps-column cell. cgroup
    counts each physical page once regardless of how many PIDs have
    it mapped, so shared library pages don't inflate the total.
    """
    _skip_unless_systemd_run_scope()
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[
            sys.executable,
            MEMORY_CHILDREN_SCRIPT,
            str(_MEM_CHILDREN_N),
            str(_MEM_CHILDREN_M),
            "1.5",
        ],
    )
    peak_rss = _read_info(temp_output_dir)["execution_summary"]["peak_rss"]
    # Ceiling: alloc + 60 MB (interpreter + shared-libs-once + headroom).
    # ps-column reports ~180 MB for this workload (double-counts shared
    # libs per child) so the 140 MB ceiling discriminates.
    alloc_bytes = _MEM_CHILDREN_N * _MEM_CHILDREN_M * 1024 * 1024
    ceiling = alloc_bytes + 60 * 1024 * 1024
    assert peak_rss <= ceiling, (
        f"cgroup reported peak_rss {peak_rss / 1024 / 1024:.1f} MB > "
        f"physical ceiling {ceiling / 1024 / 1024:.1f} MB "
        f"({_MEM_CHILDREN_N} children x {_MEM_CHILDREN_M} MB)"
    )


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="steady_cpu",
    property="peak_pcpu_reaches_floor",
    expected="pass",
)
def test_cgroup_steady_cpu_peak_pcpu_reaches_floor(
    temp_output_dir: str,
) -> None:
    _skip_unless_systemd_run_scope()
    duration = 2.0
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[sys.executable, STEADY_CPU_SCRIPT, str(duration)],
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"]
    assert peak_pcpu >= 80.0, (
        f"cgroup peak_pcpu ({peak_pcpu}) should be >= 80% for "
        f"one-core-pinned busy-loop"
    )

"""Sampler matrix: per-(sampler, workload, metric, direction) cells.

Each test is marked with ``@pytest.mark.sampler_matrix`` carrying the
``(sampler, workload, metric, direction, expected)`` metadata. The
conftest hook converts ``expected="fail"`` into ``xfail(strict=True)``,
so the suite stays green both when a sampler meets an expected-pass
claim AND when a known limitation keeps on holding. Cells are emitted
to ``.sampler_matrix_results.jsonl`` and pivoted into
``test/sampler_matrix_<sampler>.csv`` by
``scripts/gen_sampler_matrix.py`` (rows=``<workload>/<metric>``,
columns=``no_<direction>``).

``direction`` is either ``"underreport"`` or ``"overreport"`` and
names what the test asserts the sampler DOES NOT do. A test marked
``direction="overreport"`` asserts ``measured <= ceiling``; failing
means the sampler over-reported. A test marked
``direction="underreport"`` asserts ``measured >= floor``; failing
means the sampler under-reported.

Conventions:

- Each test exercises exactly one cell of the matrix.
- Test name follows
  ``test_<sampler>_<workload>_<metric>_no_<direction>`` so the matrix
  story is readable in pytest output too.
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
import platform
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
EPHEMERAL_CPU_SCRIPT = str(WORKLOADS_DIR / "ephemeral_cpu.py")
SPIKEY_CPU_SCRIPT = str(WORKLOADS_DIR / "spikey_cpu.py")
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
    runner or sibling processes in the caller's cgroup.
    """
    if shutil.which("systemd-run") is None:
        pytest.skip("systemd-run not on PATH")
    probe = subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 and not probe.stdout.strip():
        pytest.skip(f"user systemd not running: {probe.stderr.strip() or 'unknown'}")
    if not Path(DUCT_BIN).exists():
        pytest.skip(f"duct binary not found at {DUCT_BIN}")


def _skip_unless_linux() -> None:
    """Skip on non-Linux. Bug 1 (ps pcpu overshoot) is Linux-specific.

    BSD/Darwin ``ps -o pcpu`` is a decaying ~1min average, not a
    lifetime cumulative ratio, so the overshoot mechanism doesn't
    apply. See RESEARCH.md section 1.1.
    """
    if platform.system() != "Linux":
        pytest.skip(
            f"Bug 1 is Linux-specific; {platform.system()} ps uses a "
            f"decaying average, not lifetime cumulative"
        )


def _skip_if_no_thread_oversubscription(demand: int) -> None:
    """Skip when cpu_count >= workload thread demand.

    Bug 1's ps-pcpu-overshoot amplifies when threads oversubscribe
    cores (young processes + scheduler contention). On hosts with
    far more cores than our workload demands, ps reports stay close
    to legitimate physical peak and the ``no_overreport`` ceiling
    can't cleanly discriminate ps from cgroup. Workload + ceiling
    are tuned for 4-12 core hosts (typical laptops / small runners).
    """
    have = os.cpu_count() or 1
    if have >= demand:
        pytest.skip(
            f"host has {have} cores and workload demands {demand} threads; "
            f"no oversubscription, so Bug 1 cannot reliably inflate ps "
            f"beyond physical. Run on a host with cpu_count < {demand}."
        )


def _run_duct_in_scope(
    out_prefix: str,
    workload_args: list[str],
    sample_interval: float = 0.1,
    report_interval: float = 0.5,
) -> None:
    """Run duct in a transient systemd scope so its cgroup is dedicated.

    The scope's cgroup contains exactly ``duct + workload`` -- pytest
    and anything else running on the host stay in their own cgroups.
    CgroupSampler therefore reads clean ``memory.current`` / ``cpu.stat``
    values, and matrix ceiling/floor assertions can actually
    discriminate ps-with-bug-1 vs. cgroup.
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
            f"--sample-interval={sample_interval}",
            f"--report-interval={report_interval}",
            "-p",
            out_prefix,
            *workload_args,
        ],
        check=True,
    )


# N and M chosen so ps's per-pid shared-lib double-counting is large
# enough to reliably exceed a ceiling that cgroup totals would respect.
# Empirically: alloc=80 MB, ps reports ~135 MB, cgroup reports ~110 MB.
_MEM_CHILDREN_N = 4
_MEM_CHILDREN_M = 20

# Ephemeral CPU: short-lived parallel workers that die between duct
# samples (sample_interval=0.1s, each worker runs ~30ms of CPU then
# exits). Parent holds 500ms so duct gets at least one sample after
# children are gone.
_EPHEMERAL_N_WORKERS = 4
_EPHEMERAL_WORK_MS = 30
_EPHEMERAL_HOLD_MS = 500

# Spikey CPU: multi-threaded native work (pbkdf2_hmac releases GIL)
# via N parallel workers, each with M threads, for D seconds. Fast
# sampling (0.01s) catches workers at young lifetimes where ps's
# cputime/elapsed ratio is inflated per hub's Bug 1 analysis.
_SPIKEY_N_WORKERS = 4
_SPIKEY_N_THREADS = 8
_SPIKEY_DURATION_S = 0.3
# Physical ceiling on instantaneous %CPU. Bounded by cores in use;
# cgroup respects this, ps (Bug 1) can exceed by an order of magnitude.
_SPIKEY_PCPU_CEILING = (os.cpu_count() or 1) * 100 + 100


# ---- ps column ----


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="alloc_memory",
    metric="rss",
    direction="underreport",
    expected="pass",
)
def test_ps_alloc_memory_rss_no_underreport(temp_output_dir: str) -> None:
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


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="memory_children",
    metric="rss",
    direction="underreport",
    expected="pass",
)
def test_ps_memory_children_rss_no_underreport(
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
    metric="rss",
    direction="overreport",
    expected="fail",
)
def test_ps_memory_children_rss_no_overreport(
    temp_output_dir: str,
) -> None:
    """ps sums RSS per PID, double-counting shared library pages.

    Expected to fail: the sum of per-PID RSS reported by ps exceeds a
    realistic ceiling on actual physical memory used by the session.
    Under cgroup-ps-hybrid, session totals come from the kernel and
    this assertion holds.
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
    metric="pcpu",
    direction="underreport",
    expected="pass",
)
def test_ps_steady_cpu_pcpu_no_underreport(
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
    assert peak_pcpu >= 80.0, (
        f"peak_pcpu ({peak_pcpu}) should be >= 80% for one-core-pinned " f"busy-loop"
    )


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="ephemeral_cpu",
    metric="pcpu",
    direction="underreport",
    expected="fail",
)
def test_ps_ephemeral_cpu_pcpu_no_underreport(
    temp_output_dir: str,
) -> None:
    """ps misses CPU consumed by children that exit between samples.

    Expected to fail: short-lived parallel workers die before ps
    samples them, so ``ps -s <sid>`` shows an empty session at sample
    time and reported peak_pcpu stays near zero -- even though the
    cgroup actually burned ~N-cores worth of CPU. Under
    cgroup-ps-hybrid, ``cpu.stat.usage_usec`` is cumulative and
    captures work regardless of process lifetime.
    """
    assert (
        run_duct_command(
            [
                sys.executable,
                EPHEMERAL_CPU_SCRIPT,
                str(_EPHEMERAL_N_WORKERS),
                str(_EPHEMERAL_WORK_MS),
                str(_EPHEMERAL_HOLD_MS),
            ],
            sampler="ps",
            sample_interval=0.1,
            report_interval=0.5,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"] or 0.0
    # Floor chosen to comfortably discriminate ps (reports ~0% because
    # children die between samples) from cgroup (reports > 100% for
    # 4 parallel bursts over the sample window). Generous slack for
    # Python startup + sample-window dilution.
    floor = 80.0
    assert peak_pcpu >= floor, (
        f"peak_pcpu ({peak_pcpu}) should be >= {floor}% for "
        f"{_EPHEMERAL_N_WORKERS} parallel {_EPHEMERAL_WORK_MS}ms workers"
    )


@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="ps",
    workload="spikey_cpu",
    metric="pcpu",
    direction="overreport",
    expected="fail",
)
def test_ps_spikey_cpu_pcpu_no_overreport(
    temp_output_dir: str,
) -> None:
    """ps Bug 1: multi-threaded young processes inflate cputime/elapsed.

    Expected to fail (Linux only): ``ps -o pcpu`` is cumulative over
    a process's lifetime, so a worker that just started a multi-core
    pbkdf2 burst reports ``cputime / elapsed`` with a small elapsed
    denominator -- easily several hundred percent per worker. Duct's
    per-pid sum across the session then compounds this across N
    parallel workers. Real-world #399 (pip compiling C extensions
    under tox) hits >1000%.

    Cite: RESEARCH.md section 1.1 (pcpu fully broken);
    DEEP_DIVE_PROGRESS.md section 2 (Bug 1 confirmed in
    src/con_duct/_sampling.py). Distinct from Bug 2 (aggregation
    inconsistency, xfailed in c017800) -- do not conflate.
    """
    _skip_unless_linux()
    _skip_if_no_thread_oversubscription(_SPIKEY_N_WORKERS * _SPIKEY_N_THREADS)
    assert (
        run_duct_command(
            [
                sys.executable,
                SPIKEY_CPU_SCRIPT,
                str(_SPIKEY_N_WORKERS),
                str(_SPIKEY_N_THREADS),
                str(_SPIKEY_DURATION_S),
            ],
            sampler="ps",
            sample_interval=0.01,
            report_interval=0.1,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"] or 0.0
    # Ceiling: the workload demands N*M threads worth of parallel
    # work, but the host only has cpu_count cores; physical peak can't
    # exceed that. Plus a generous 100% slack.
    assert peak_pcpu <= _SPIKEY_PCPU_CEILING, (
        f"ps reported peak_pcpu {peak_pcpu:.0f}% > "
        f"physical ceiling {_SPIKEY_PCPU_CEILING:.0f}% "
        f"(Bug 1: cputime/elapsed inflation x per-pid sum)"
    )


# ---- cgroup-ps-hybrid column ----
#
# Opt-in: marked cgroup_matrix (see conftest.py --cgroup-matrix flag).
# Each test spawns duct in a transient systemd --user --scope so the
# cgroup CgroupSampler reads is dedicated to just duct + the workload.
# Without the scope, duct's ambient cgroup (a login user slice, a
# non-ns container, etc.) contains far more memory than our workload
# and matrix assertions become meaningless.


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="alloc_memory",
    metric="rss",
    direction="underreport",
    expected="pass",
)
def test_cgroup_alloc_memory_rss_no_underreport(
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
    metric="rss",
    direction="underreport",
    expected="pass",
)
def test_cgroup_memory_children_rss_no_underreport(
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
    metric="rss",
    direction="overreport",
    expected="pass",
)
def test_cgroup_memory_children_rss_no_overreport(
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
    metric="pcpu",
    direction="underreport",
    expected="pass",
)
def test_cgroup_steady_cpu_pcpu_no_underreport(
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


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="ephemeral_cpu",
    metric="pcpu",
    direction="underreport",
    expected="pass",
)
def test_cgroup_ephemeral_cpu_pcpu_no_underreport(
    temp_output_dir: str,
) -> None:
    """cgroup cpu.stat is cumulative: dead children's CPU is counted.

    Expected to pass: short-lived workers that finish between duct
    samples still contribute to ``cpu.stat.usage_usec``. The delta
    between two samples captures the full burst.
    """
    _skip_unless_systemd_run_scope()
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[
            sys.executable,
            EPHEMERAL_CPU_SCRIPT,
            str(_EPHEMERAL_N_WORKERS),
            str(_EPHEMERAL_WORK_MS),
            str(_EPHEMERAL_HOLD_MS),
        ],
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"] or 0.0
    # Same floor as ps version: discriminates "captured non-zero CPU"
    # from "missed entirely."
    floor = 80.0
    assert peak_pcpu >= floor, (
        f"cgroup peak_pcpu ({peak_pcpu}) should be >= {floor}% for "
        f"{_EPHEMERAL_N_WORKERS} parallel {_EPHEMERAL_WORK_MS}ms workers"
    )


@pytest.mark.cgroup_matrix
@pytest.mark.flaky(reruns=3)
@pytest.mark.sampler_matrix(
    sampler="cgroup-ps-hybrid",
    workload="spikey_cpu",
    metric="pcpu",
    direction="overreport",
    expected="pass",
)
def test_cgroup_spikey_cpu_pcpu_no_overreport(
    temp_output_dir: str,
) -> None:
    """cgroup cpu.stat delta is bounded by cores in use.

    Expected to pass: unlike ps's lifetime-cumulative per-pid ratio,
    ``usage_usec`` delta over a sample interval measures actual CPU
    time consumed during that window. Bounded by
    ``cpu_count * sample_interval``.
    """
    _skip_unless_systemd_run_scope()
    _skip_unless_linux()
    _skip_if_no_thread_oversubscription(_SPIKEY_N_WORKERS * _SPIKEY_N_THREADS)
    _run_duct_in_scope(
        out_prefix=temp_output_dir,
        workload_args=[
            sys.executable,
            SPIKEY_CPU_SCRIPT,
            str(_SPIKEY_N_WORKERS),
            str(_SPIKEY_N_THREADS),
            str(_SPIKEY_DURATION_S),
        ],
        sample_interval=0.01,
        report_interval=0.1,
    )
    peak_pcpu = _read_info(temp_output_dir)["execution_summary"]["peak_pcpu"] or 0.0
    assert peak_pcpu <= _SPIKEY_PCPU_CEILING, (
        f"cgroup reported peak_pcpu {peak_pcpu:.0f}% > "
        f"physical ceiling {_SPIKEY_PCPU_CEILING:.0f}% "
        f"(cgroup cpu.stat should be bounded by cpu_count)"
    )

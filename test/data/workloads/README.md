# Workload catalog

Small, deterministic scripts with known ground-truth resource-usage
patterns. The sampler matrix tests (landing in a follow-up commit)
invoke duct against these scripts under each sampler and assert
expected behavior per cell (accurate / known-limitation).

Each script is **standalone-runnable** — you can invoke it directly
(without duct) to verify it does what it claims. Each script's
docstring states its ground-truth contract.

## Scripts in this directory

- `steady_cpu.py <duration_seconds>` — pin to one core, busy-loop.
  Ground truth: single-process `peak_pcpu ~= 100%` (one core
  saturated), wall clock `~= duration`. Any sampler should be
  accurate.

- `alloc_memory.py <size_mb> <hold_seconds>` — allocate a contiguous
  bytearray and hold it. Ground truth: `peak_rss >= size_mb * 1024 *
  1024` bytes.

- `ephemeral_cpu.py <num_workers> <work_ms> <hold_ms>` — fork N
  short-lived parallel children doing `work_ms` of CPU each, parent
  holds for `hold_ms`. Ground truth: cgroup used ~`N * work_ms` of
  CPU in ~`work_ms` wall time. **ps misses this**: children die
  between samples, so `ps -s <sid>` returns an empty session and
  reported `peak_pcpu` is near zero. **cgroup catches this**:
  `cpu.stat.usage_usec` is cumulative even for exited processes.

- `spikey_cpu.py <num_workers> <num_threads> <duration_seconds>` —
  fork N workers, each spawning M threads running
  `hashlib.pbkdf2_hmac` (GIL-released, truly parallel) for
  `duration` seconds. Ground truth: peak instantaneous %CPU ≤
  `cpu_count * 100%`. **Linux ps dramatically OVER-reports**
  (Bug 1, #399): `ps -o pcpu` is lifetime cumulative
  `cputime / elapsed`, and a young multi-threaded worker's ratio is
  arbitrarily inflated; duct's per-pid sum across the session then
  compounds across workers. Real-world cases hit >1000%. **cgroup is
  bounded**: `cpu.stat.usage_usec` delta over a sample interval
  measures actual CPU time consumed, capped by cores in use.
  Principled stdlib equivalent of the real #399 trigger (pip
  compiling C extensions under tox).

## Additional workload scripts (elsewhere)

- `test/data/memory_children.py <num_children> <mb_per_child>
  <hold_seconds>` — fork N child processes, each holding M MB. Ground
  truth diverges by sampler: under `ps`, each PID's RSS counts shared
  library pages separately, so `sum(rss)` overcounts actual physical
  memory; cgroup v2 session totals reflect real physical usage. Kept
  at its original location to avoid history churn; the TODO below
  covers longer-term consolidation.

## TODO: consolidate workload scripts

Workload scripts are currently split across `test/data/` (legacy:
`test_script.py`, `memory_children.py`) and this directory. A future
cleanup could either:

- Migrate all workload scripts into this directory so the catalog has
  a single location; or
- Collapse the pre-POC `test_script.py` (`--memory-size` +
  `--cpu-load` multi-purpose) into the one-phenomenon-per-script
  style used here.

Decision deferred pending POC acceptance.

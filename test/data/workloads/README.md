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

## Additional workload scripts (elsewhere)

- `test/data/memory_children.py <num_children> <mb_per_child>
  <hold_seconds>` — fork N child processes, each holding M MB. Ground
  truth diverges by sampler: under `ps`, each PID's RSS counts shared
  library pages separately, so `sum(rss)` overcounts actual physical
  memory; cgroup v2 session totals reflect real physical usage. This
  divergence is one of the core anchors for the sampler matrix (see
  issue #399 for context). Kept at its original location to avoid
  history churn; the TODO below covers longer-term consolidation.

## Planned: spikey multi-core CPU burst

Not yet implemented. The #399 motivating case is a short-lived burst
of parallel CPU work across multiple cores — which `ps` may
undersample/misattribute and cgroup v2 session totals should catch
correctly. This is arguably the most important cell in the sampler
matrix, and should be added before the POC is pitched as "direction
proven."

Tentative implementation lean: `hashlib.pbkdf2_hmac` in N threads —
stdlib only, releases the GIL during the C-side crypto work, so the
threads parallelize across cores without needing a free-threaded
Python build or external deps. Alternatives considered in the plan:
free-threaded Python (`3.13t`/`3.14t`), numpy BLAS, stress-ng binary.

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

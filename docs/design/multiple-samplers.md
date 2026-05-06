# Design: multiple samplers (cgroup-ps-hybrid)

**Status:** POC implementation landed on branch `sampler-choice`. This
document describes the design *as implemented* for in-scope items and
lists deferred work in §10 (Future Directions).

**Related:** [`docs/resource-statistics.md`](../resource-statistics.md)
documents the current `ps`-based semantics honestly; this document
describes how we give users a *different* sampler alongside `ps` with
cleaner semantics for the cases that matter.

---

## 1. Summary

Duct historically sampled resource usage exclusively via `ps(1)`. The
semantics `ps` provides are correct for what `ps` measures but mis-fit
for the HPC / job-accounting use case where duct's numbers are often
used to size follow-up SLURM allocations. Two failure modes in
particular surface in practice:

- `ps -o pcpu` is a *lifetime average*, not an instantaneous rate.
  Summed across a session with short-lived or bursty multi-threaded
  children, totals can legitimately exceed the system's physical CPU
  ceiling — issue [#399](https://github.com/con/duct/issues/399)
  reported 5363% on a 20-core box.
- `ps -o rss` counts shared pages in every process that maps them.
  Summed across forked workers, shared libraries and copy-on-write
  memory get counted 3–10× on typical Python workloads.

Neither is a duct bug; both are correct consequences of what `ps`
measures. Fixing them requires a different measurement source.

This design ships **one** additional sampler:

- **`cgroup-ps-hybrid`** — Linux-only, zero new dependency, reads
  cgroup v2 counters (`memory.current`, `cpu.stat.usage_usec`) for
  session totals, keeps `ps` as the per-pid sub-sampler. Matches the
  counters SLURM's `slurmstepd` and Docker's `docker stats` already
  report.

`ps` remains the default — backwards-compatible, stdlib-only, works
on every platform duct currently supports. `cgroup-ps-hybrid` is
explicitly opt-in via `--sampler=cgroup-ps-hybrid`.

> **Name note.** `cgroup-ps-hybrid` is a deliberately clunky
> *placeholder* for the POC. It is descriptive (it *is* a hybrid of
> cgroup totals and ps per-pid) but not a production name. Renaming
> is listed under §9 Schema Open Questions.

Other candidate samplers (notably `psutil`) are interesting and are
enumerated in §10 Future Directions, but are not in the POC scope.

---

## 2. Problem statement

`docs/resource-statistics.md` has the user-facing explanation of what
the current `ps`-based sampler does and doesn't measure. Condensed
motivation for this design:

### 2.1 CPU: lifetime-cumulative ratio × per-pid summing

Linux `ps -o pcpu` reports `cputime / elapsed`, with both numbers
accumulated over the process's entire life. For a just-spawned
multi-threaded native workload, the elapsed denominator is small and
the ratio inflates — a worker that's been alive 10 ms and consumed
40 ms of multi-thread CPU reports 400%. Duct's per-pid sampling then
sums these per-pid values across the session, compounding the
inflation across N workers. Real-world examples on `pip install`
workloads under `tox` (short-lived C-extension compilers) have hit
over 1000% aggregated pcpu.

Note: this is **Linux-specific**. BSD/Darwin `ps -o pcpu` is a
decaying ~1-minute average, not a lifetime cumulative ratio, so the
inflation mechanism doesn't apply there.

### 2.2 Memory: shared pages per-pid × per-pid summing

`ps -o rss` counts every page a process has mapped, including shared
pages like the Python interpreter's `.text` segment. Forking N
children that all share the interpreter causes duct's per-pid rss
sum to count those shared pages N times. On a typical Python workload
with a few children, the overcount is 3–10× actual physical memory.

### 2.3 Why cgroup

Linux cgroup v2 counters are kernel-accounted for the entire cgroup
at once:

- `memory.current` is physical memory use of the cgroup. Shared pages
  are counted once regardless of how many processes map them.
- `cpu.stat.usage_usec` is cumulative microseconds of CPU consumed
  by the cgroup. Delta between two reads divided by wall-clock gives
  instantaneous %CPU, physically bounded by cores in use.

These are the same counters SLURM's `slurmstepd` and `docker stats`
read. Using them for duct's totals makes duct's numbers directly
comparable to the scheduler's own accounting — which is the killer
feature for HPC users sizing follow-up allocations from duct logs.

The cost is that cgroup counters are cgroup-scoped, not pid-scoped.
Per-pid attribution still requires `ps` (or a future alternative).
That's why the POC shipped a *hybrid*: cgroup for session totals, ps
for the per-pid breakdown.

---

## 3. Requirements

Three axes, pulling against each other:

| Requirement                 | What it means                                                                                      |
|-----------------------------|----------------------------------------------------------------------------------------------------|
| **Portable**                | Linux primary (HPC), macOS secondary (dev). Must not regress any platform duct currently works on. |
| **Lightweight at runtime**  | Sampling overhead scales reasonably with process count and polling cadence.                        |
| **Lightweight to install**  | Stdlib-only path (`pip install con-duct`) keeps working without any new mandatory dep.             |

Secondary:

- **Accurate** for what each sampler claims to measure. No sampler
  should lie about its semantics.
- **Backwards compatible** with existing `usage.jsonl` / `info.json`
  consumers. Additive schema changes only.

The multi-sampler approach satisfies these by keeping `ps` as the
default (portable, stdlib, unchanged behavior) and adding
`cgroup-ps-hybrid` as opt-in for the platform and use case that needs
different semantics.

---

## 4. Sampler comparison (in-scope)

| Sampler              | Portable                 | Runtime cost                            | Install cost | CPU semantics                                                  | Memory semantics                                              |
|----------------------|--------------------------|------------------------------------------|--------------|----------------------------------------------------------------|---------------------------------------------------------------|
| `ps`                 | Linux + macOS            | O(N) fork+exec per sample, 10–20 ms/poll | stdlib       | Lifetime-average per-pid summed across session (macOS: decaying average) | Per-process RSS summed across session (counts shared pages N×) |
| `cgroup-ps-hybrid`   | Linux (cgroup v2 only)   | O(1) cgroup read per sample plus one ps call | stdlib       | Delta of kernel cumulative `usage_usec`; physically bounded     | Kernel-accounted `memory.current`; shared pages counted once   |

Alternatives considered but not implemented for the POC (`psutil`,
`pidstat`, `cgmemtime`, `memory_profiler`, a hand-rolled `/proc`
parser) are enumerated in §10 Future Directions.

---

## 5. Architecture (as implemented)

### 5.1 Sampler abstraction

`src/con_duct/_sampling.py` moved from platform-dispatch to
sampler-dispatch. Each sampler is a concrete class that exposes a
`name` attribute and a `sample(session_id) -> Optional[Sample]`
method. A `Sampler` type alias (`Union[PsSampler, CgroupSampler]`)
stands in for a Protocol/ABC — introducing one is easy later if a
third concrete class joins; the POC didn't need it.

`Report` (in `_tracker.py`) takes an optional `sampler` argument in
its constructor, defaulting to a fresh `PsSampler()` so every existing
caller is unaffected. `Report.collect_sample` delegates to
`self.sampler.sample(...)`.

The `Sample` dataclass (in `_models.py`) is unchanged. `Sample.aggregate`
is unchanged — the peak-is-max, running-average pattern was kept
deliberately; the "aggregate totals mismatch" described in
`resource-statistics.md §Peak vs. average` is a property of what peaks
and averages respectively mean, not a bug.

### 5.2 Backends

#### `ps` sampler

- Default. Preserves every byte of historical duct behavior.
- Only change: records carry `"sampler": "ps"` (see §5.4).
- `_get_sample_linux` / `_get_sample_mac` became private helpers
  wrapped by `PsSampler.sample`.

#### `cgroup-ps-hybrid` sampler

Reader mode, hybrid. Implementation in `_sampling.py::CgroupSampler`:

- **Availability.** `__init__` checks `/sys/fs/cgroup/cgroup.controllers`
  exists (cgroup v2 unified hierarchy) and reads `/proc/self/cgroup`
  to resolve duct's own cgroup path. v1 is refused with a clear
  `NotImplementedError`.
- **Session totals from cgroup:**
  - `memory.current` → `sample.total_rss` (overwrites the ps-sum;
    the `"sampler"` tag disambiguates which source produced a given
    record).
  - `cpu.stat.usage_usec` delta over the last sample interval →
    `sample.total_pcpu`. The sampler holds `(usage_usec, monotonic)`
    state across calls; the first sample's delta is taken from a
    baseline captured in `__init__`.
- **Per-pid data from ps.** The ps sub-sampler runs as before to
  populate `sample.stats[pid]`, so the usage.jsonl records keep the
  per-pid breakdown users expect. That's why the sampler is called
  `-hybrid`.
- **`total_vsz` and `total_pmem` are still ps-sourced.** cgroup v2
  has no direct analogs (`memory.current` is already physical; vsz
  is per-process by definition).
- **Catch-and-release** on cgroup read failures: OSError / ValueError
  are caught and re-raised as a `RuntimeError` pointing at the cgroup
  path for debuggability.

The cgroup-ps-hybrid sampler additionally **requires
`--mode=current-session`**. Reader mode assumes duct and the tracked
command share a cgroup, which they do by default when duct does not
start a new session. `--mode=new-session` with `--sampler=cgroup-ps-hybrid`
errors out at startup before log paths are created.

### 5.3 Selection UX

**Explicit selection** (no auto-detection in the POC):

- CLI: `--sampler={ps,cgroup-ps-hybrid}`
- Env: `DUCT_SAMPLER=…`
- Dotenv: loaded via the existing `DUCT_CONFIG_PATHS` mechanism

Unknown sampler → `ValueError`. Known sampler unavailable in the
environment (cgroup v2 absent, Darwin asking for cgroup, etc.) →
clear error at startup; **no silent fallback**. The user explicitly
asked for something; if duct can't honor it, it refuses instead of
silently doing something different.

Default is `ps` — preserves compatibility with every existing invocation.

### 5.4 Schema

The `usage.jsonl` and `info.json` shape changes minimally:

- **New `sampler` field** on every usage.jsonl record and in
  info.json. Value is the sampler's `name` (e.g., `"ps"` or
  `"cgroup-ps-hybrid"`). Consumers that ignore unknown fields keep
  working. Consumers that care can switch interpretation based on
  the tag.
- **`total_*` fields are populated from cgroup counters** when the
  cgroup sampler is in use. Field names are unchanged; only the
  data source is different, and the `sampler` tag disambiguates.
- **`stats[pid]`** remains populated from the per-pid sub-sampler (ps
  for this POC).

No field renames. Consumers don't have to change. This is deliberately
the smallest possible schema delta; §9 lists the schema-level Open
Questions that were *not* resolved in the POC.

---

## 6. Per-sampler detail

### 6.1 `ps` sampler

No substantive behavior change beyond the `sampler` tag on records.
`resource-statistics.md` carries the honest-labeling documentation of
what ps measures; the code doesn't need to change to make semantics
clearer.

### 6.2 `cgroup-ps-hybrid` sampler

**Availability detection.** On import of `_sampling.py`, no cgroup
action happens — the check runs when `CgroupSampler()` is instantiated
from `make_sampler`. Three steps, any failure → `NotImplementedError`
with an actionable message:

1. Check `/sys/fs/cgroup/cgroup.controllers` exists (v2 filesystem).
2. Read `/proc/self/cgroup`, find the v2 line (`0::/…`), resolve it
   to an absolute path under `/sys/fs/cgroup`.
3. (Implicit) Subsequent reads of `memory.current` and `cpu.stat` in
   that cgroup either succeed or the sampler's catch-and-release turns
   any OSError into a `RuntimeError` that names the failing path.

**Counter reads per sample.**

- `memory.current` → `sample.total_rss`. Kernel-accounted, shared
  pages counted once.
- `cpu.stat` parsed for `usage_usec`. Delta from the previous
  `(usage_usec, monotonic_clock)` stored on the sampler instance →
  `sample.total_pcpu = delta_usec / delta_wall_seconds / 10_000`
  (percent of one core). `__init__` captures the baseline so the
  first call produces a meaningful delta.

**Reader-mode scope caveat.** The cgroup duct reads is whatever
cgroup duct lives in. In HPC contexts this matches exactly what we
want (SLURM step cgroup; a container's cgroup namespace; a
`systemd-run --user --scope` transient unit). In a bare interactive
login session it's the user's slice, which contains every other
process the user has running — the numbers are then "all my stuff"
rather than "the command I asked about." This is documented, not
fixed; creator mode (see §10) is the proper remedy.

**Explicit TODOs flagged in code** as `TODO(poc)`:

- The ps-shaped polling cadence is a compromise. cgroup counters are
  naturally *cumulative*; the sampler could emit deltas (or a single
  end-of-run cumulative read) without the per-sample poll pattern.
  The POC kept polling to reuse the existing `Sample`/`Report`
  pipeline; reshaping that is §10 work.
- At end of run, `full_run_stats.total_rss` is the max across
  per-sample `memory.current` reads. The kernel tracks a proper
  high-water mark in `memory.peak` (available on Linux ≥5.13);
  overwriting `full_run_stats.total_rss` from `memory.peak` at end of
  run would give a more accurate peak than max-of-currents.
- The sampler assumes the tracked command stays in duct's cgroup.
  `systemd-run` and other cgroup-migrating wrappers silently break
  this. Creator mode (see §10) fixes it.

---

## 7. Test strategy

Test infrastructure lives in three layers:

**Tier 0 — model unit tests.** Sampler-agnostic. `Sample`,
`aggregate`, etc. with handcrafted fixtures. Unchanged by this work.

**Tier 1 — per-sampler behavior tests.**
`test/duct_main/test_resource_validation.py` (absorbed from PR #403)
exercises duct end-to-end against workload scripts with known ground
truth. These still run under the default `ps` sampler.

**Tier 2 — sampler matrix.** `test/duct_main/test_sampler_matrix.py`
probes each `(sampler, workload, metric, direction)` cell of the
capability matrix. Each test:

- Is marked with `@pytest.mark.sampler_matrix(sampler, workload,
  metric, direction, expected)` carrying the cell metadata.
- Asserts one polarity (`peak >= floor` for `direction="underreport"`,
  `peak <= ceiling` for `direction="overreport"`).
- Has an `expected` of `"pass"` or `"fail"`. A conftest hook converts
  `expected="fail"` into `xfail(strict=True)`, so known sampler
  limitations stay committed as expected-fail cells without making
  the overall suite red; if a sampler improves, the xpass surfaces
  noisily and we flip the expectation.

The conftest also writes each test's actual outcome to
`.sampler_matrix_results.jsonl`. `scripts/gen_sampler_matrix.py`
pivots that into one CSV per sampler
(`test/sampler_matrix_<sampler>.csv`, rows=`<workload>/<metric>`,
columns=`no_<direction>`, cells=`pass|fail|n/a`). Regeneration is
wrapped in `scripts/regen_matrix.sh` and canonically invoked via
`datalad run scripts/regen_matrix.sh --explicit --output …` so the
regeneration commit carries command provenance.

**Opt-in cgroup matrix cells.** The `cgroup-ps-hybrid` matrix cells
are marked `@pytest.mark.cgroup_matrix` and skipped unless pytest is
invoked with `--cgroup-matrix`. Each such test spawns duct in a
transient systemd scope (`systemd-run --user --scope --collect`) so
the cgroup CgroupSampler reads is dedicated to just `duct + workload`,
not polluted by pytest or sibling host processes. This makes assertions
meaningful on a normal developer machine without requiring a SLURM
job. Hosts without a user systemd instance skip these tests.

**Workload catalog** (`test/data/workloads/`). Small, deterministic,
standalone-runnable scripts with documented ground-truth contracts:

- `steady_cpu.py` — single-core busy-loop.
- `alloc_memory.py` — known-size `bytearray` allocation.
- `ephemeral_cpu.py` — short-lived parallel workers that die between
  duct samples. Anchors the "ps misses dead children's CPU" story.
- `spikey_cpu.py` — multi-threaded `hashlib.pbkdf2_hmac` bursts.
  GIL-released, truly parallel. Anchors the "ps cputime/elapsed
  inflation × per-pid summing" story. Linux-only (Darwin ps is a
  decaying average, not cumulative).
- `test/data/memory_children.py` (absorbed from PR #403) — forked
  children each holding a known-size allocation. Anchors the "ps
  double-counts shared library pages" story.

**CI.** A follow-up adds a GitHub Actions job that runs
`pytest --cgroup-matrix` on a runner with user systemd enabled (e.g.
via `loginctl enable-linger`) so the cgroup column of the matrix is
regenerated in CI and drift is caught. The POC commit does not wire
this up — CSVs are regenerated locally and committed via
`datalad run`. See §9 and §10.

---

## 8. Results

The POC's claim — that `cgroup-ps-hybrid` addresses real ps
pathologies — is captured in the committed CSVs:

**`test/sampler_matrix_ps.csv`:**

| workload/metric      | no_overreport | no_underreport |
|----------------------|---------------|----------------|
| alloc_memory/rss     | n/a           | pass           |
| ephemeral_cpu/pcpu   | n/a           | **fail**       |
| memory_children/rss  | **fail**      | pass           |
| spikey_cpu/pcpu      | **fail**      | n/a            |
| steady_cpu/pcpu      | n/a           | pass           |

**`test/sampler_matrix_cgroup-ps-hybrid.csv`:**

| workload/metric      | no_overreport | no_underreport |
|----------------------|---------------|----------------|
| alloc_memory/rss     | n/a           | pass           |
| ephemeral_cpu/pcpu   | n/a           | **pass**       |
| memory_children/rss  | **pass**      | pass           |
| spikey_cpu/pcpu      | **pass**      | n/a            |
| steady_cpu/pcpu      | n/a           | pass           |

Three ps failure modes flip to pass under cgroup-ps-hybrid:

- **`memory_children/rss/no_overreport`** — shared-library per-pid
  double-counting (§2.2).
- **`spikey_cpu/pcpu/no_overreport`** — cputime/elapsed inflation on
  young multi-threaded processes × per-pid summing (§2.1).
- **`ephemeral_cpu/pcpu/no_underreport`** — ps misses CPU consumed by
  children that exit between samples; cgroup's cumulative
  `cpu.stat.usage_usec` captures it regardless.

`n/a` cells mean "no test currently probes that (workload, metric,
direction) combination." They are not claims; §10 lists matrix
completeness as future work.

---

## 9. Schema open questions

Schema changes in the POC were deliberately minimal: one additive
`"sampler"` field on records and in info.json. The following
questions were deferred rather than resolved:

1. **Explicit `schema_version` bump?** The POC keeps
   `__schema_version__` unchanged since the change is strictly
   additive. A production release may want to bump anyway, so
   consumers have a clean signal that the sampler tag might be
   present.

2. **Translation / compat layer for pre-tag consumers?** Current
   consumers (`con-duct pprint`, `plot`, `ls`) are all in-repo and
   handle the optional field transparently. External consumers that
   parse `usage.jsonl` directly will see a new field; most will
   ignore it. If any consumer key-collides or strictly-validates,
   they'd need a reader that tolerates the new field. The POC does
   not ship any compat shim.

3. **Per-block source tagging.** Right now `sampler` is a single
   top-level field per record. Under the hybrid sampler, session
   totals come from cgroup but per-pid stats come from ps. A more
   faithful record shape would tag each block with its source
   (e.g., `totals.source = "cgroup"`, `stats[pid].source = "ps"`).
   Not required for the in-repo consumers; worth considering if
   external tools want to treat the two sources differently.

4. **Should the placeholder `cgroup-ps-hybrid` name change for
   production?** The current name is descriptive-but-clunky. A
   production name should either commit to "this is the cgroup
   sampler" (and the ps per-pid fallback becomes an internal
   implementation detail) or expose the hybrid composition more
   intentionally (`--sampler=cgroup --per-pid-sampler=ps`). See §10.

---

## 10. Future directions

A fair amount of the original proposal has been explicitly deferred.
Listed here roughly in order of "how likely this is the next thing
someone wants":

### 10.1 `psutil` sampler — cross-platform instantaneous

Optional pip dep (`pip install con-duct[psutil]`). Per-pid sampling
uses `psutil.Process.cpu_percent(interval=None)` for delta CPU
(maintains per-pid prior-cputime state in the sampler) and
`memory_full_info()` for PSS on Linux / USS on macOS / RSS fallback.
Session enumeration via `psutil.process_iter()` + `os.getsid(pid)`
filter.

Platform coverage: Linux, macOS, Windows (bonus — a psutil-only
Windows path would be the first Windows support duct has ever had).

Install footprint: one C-extension dep, ~500 KB wheel per platform,
wheels available for every Python duct supports.

Pid lifecycle is the main wrinkle: first sample after pid birth
returns 0% pcpu (psutil's documented "discard first reading" caveat).
Subsequent samples return proper deltas. The sampler needs to retain
`Process` objects across duct samples, keyed by pid, and prune on
disappearance.

This was a first-class sampler in the original proposal; the POC
deliberately scoped it out to get the cgroup story shipped first.

### 10.2 Cgroup creator mode (scoping robustness)

The POC's reader mode trusts that duct and its command stay in the
same cgroup. That holds in SLURM / Docker / `systemd-run --user`
invocations but breaks on a bare interactive shell where the
enclosing cgroup is the user's session slice.

Creator mode places the child in a new sub-cgroup — either via
`systemd-run --user --scope` (easy; needs user systemd) or by writing
directly to cgroupfs (harder; needs an explicitly delegated cgroup
subtree, à la BenchExec). Either way the measurement becomes exact
regardless of invocation context.

### 10.3 `memory.peak` end-of-run overwrite

`CgroupSampler` currently reports `total_rss` = `memory.current`
per sample, and `full_run_stats.total_rss` is the max across samples
— which misses any peak that fell between samples. The kernel
already tracks a proper high-water mark in `memory.peak` (Linux
≥5.13). At end of run, overwriting `full_run_stats.total_rss` from
`memory.peak` would give a truer peak than max-of-currents. (On
kernels without `memory.peak`, document the fallback and move on.)

### 10.4 Reshape Sample / Report pipeline for cgroup's cumulative nature

The POC forces cgroup counters into the ps-shaped sample-at-interval
pipeline. cgroup is fundamentally *cumulative*: a single
`cpu.stat.usage_usec` read at end of run answers "how much CPU did
this cgroup use?" exactly, no polling required. Reshaping the
pipeline so each sampler can emit its natural shape (ps: point-in-time
snapshots; cgroup: cumulative + delta; both: final) would make the
samplers less awkward and allow cheaper measurement.

This is a bigger refactor (affects `Sample`, `Report.collect_sample`,
the JSONL schema, and consumers) and is explicitly out of POC scope.

### 10.5 Auto-detection of sampler

Heuristics that safely default to `cgroup-ps-hybrid` when we can tell
the invocation context has a tight scope:

- `SLURM_JOB_ID` set → step cgroup.
- `container=docker` / `INVOCATION_ID` (systemd-run) → scoped cgroup.
- Fall back to `ps`.

Not done in POC because explicit selection is easier to reason about
for reviewers. Default-change is a breaking change to `usage.jsonl`
interpretation and warrants a real deprecation cycle anyway.

### 10.6 Matrix completeness

Each test in `test_sampler_matrix.py` probes one
`(workload, metric, direction)` cell. We wrote cells for the
directions that tell a story (where ps fails and cgroup doesn't, or
vice versa). Cells where both samplers would pass — e.g.,
`alloc_memory/rss/no_overreport`, `steady_cpu/pcpu/no_overreport` —
are currently `n/a`. A future pass could fill every cell, giving
reviewers a complete capability card at the cost of ~8 more
"both-pass" tests.

### 10.7 cgroup v1 support

The POC refuses cleanly on v1. RHEL 8 and older HPC systems ship v1,
so if that's blocking any real user, a v1 fallback path would read
the equivalent counters from the v1 memory / cpuacct controllers.
Added complexity; worth it only if there's demand.

### 10.8 Windows support

Neither `ps` nor `cgroup` are relevant. `psutil` (see §10.1) is the
natural route. Would require a session-scoping model since Windows
doesn't have POSIX sessions.

### 10.9 Renaming the `cgroup-ps-hybrid` placeholder

The name is a POC marker. Production should pick one of:

- **`cgroup`** — commits to "this is the cgroup sampler" and treats
  the ps per-pid fallback as an implementation detail. Easier to
  explain to users.
- **`cgroup+ps`** / **`cgroup:ps`** / similar — exposes the hybrid
  composition and leaves room for `cgroup+psutil` later.
- **Decouple entirely:** `--sampler=cgroup --per-pid-sampler=ps`
  (two knobs). Most flexible, most complex.

Tied to §9.4.

### 10.10 Schema translation layer for pre-tag consumers

If external tools consume `usage.jsonl` and the `sampler` field
interacts with their parsing (e.g., JSONSchema validation with
`additionalProperties: false`), duct could offer a legacy-format
writer that drops the tag. Not needed for in-repo consumers; listed
here in case demand surfaces.

### 10.11 CI coverage for the cgroup matrix

Default GitHub Actions Ubuntu runners don't have a user systemd
instance active, so `pytest --cgroup-matrix` skips everything. A
separate CI job could `sudo loginctl enable-linger` the runner user
or use a container with cgroup-namespace isolation to exercise the
cgroup cells. Without it, the committed cgroup CSV is a local-run
snapshot; drift is caught by developer re-run before PR.

---

## 11. Non-goals

Explicitly out of scope for *this POC*, so they don't get rolled in
accidentally. (Several appear in §10 as future directions; these are
the things the POC says "not now, full stop" about.)

- **New metrics.** Duct's metric set (pcpu, rss, vsz, pmem) stays the
  same; what changed is where some of those numbers come from.
- **Field renames in `usage.jsonl`.** Only the additive `sampler`
  tag. Consumers don't have to change.
- **Reshaping `--sample-interval` / `--report-interval` semantics.**
  Every sampler honors both; no interaction beyond what already
  exists.
- **Default-sampler change.** `ps` stays the default. Changing the
  default is a breaking change to `usage.jsonl` interpretation; not
  something the POC does under cover.

---

## 12. Resolved / still-open from the original proposal

The original proposal (`pcpu-overshoot-investigation` branch) listed
eight open questions. Status after the POC:

1. **cgroup v1 support** — *resolved: no.* v2 only; v1 deferred to
   §10.7.
2. **Auto-detection timeline** — *deferred to §10.5.* POC ships
   explicit selection only.
3. **Will the default sampler ever change?** — *still open.* §10.5
   discusses the deprecation cycle that'd be required.
4. **Hybrid mode UX — implicit or explicit knobs?** — *resolved:
   implicit.* `--sampler=cgroup-ps-hybrid` is the hybrid; no
   separate per-pid-sampler knob.
5. **Creator mode scope** — *deferred to §10.2.* Reader-only in POC.
6. **Sampler tag discoverability** — *resolved.* `sampler` appears on
   every record and in info.json.
7. **Error UX when requested sampler unavailable** — *resolved.*
   cgroup-ps-hybrid errors with a message naming the missing
   `cgroup.controllers` file or the unavailable `/proc/self/cgroup`
   v2 entry.
8. **cgroup v2 features not available on older kernels** — *deferred
   to §10.3.* `memory.peak` is Linux ≥5.13; POC uses
   `memory.current` + max-across-samples as the fallback.

---

## 13. Implementation sequencing (as landed)

The POC landed on branch `sampler-choice` as a sequence of
topic-focused commits:

1. Sampler abstraction refactor — no behavior change.
2. `--sampler` flag, `DUCT_SAMPLER` env, `sampler` schema tag.
3. Absorb resource-validation harness from PR #403.
4. Workload catalog (initial).
5. Sampler-matrix harness (marker + JSONL hook + CSV generator).
6. Rework the harness + add ps-column cells.
7. `CgroupSampler` implementation (cgroup v2 + ps hybrid).
8. cgroup-column matrix cells (via systemd-run subprocess per test).
9. `scripts/regen_matrix.sh` + `datalad run` regeneration.
10. Matrix expansion (schema, ephemeral + spikey workloads).
11. This document's revision.

The commits are small enough that, if the direction is accepted, this
can split into three follow-up PRs — docs, tests, impl — or be
polished and merged in place.

---

## 14. References

- [`docs/resource-statistics.md`](../resource-statistics.md) — the
  semantics of the ps-based sampler. Required background.
- [Issue #399](https://github.com/con/duct/issues/399) — peak pcpu
  overshoot report that prompted this work.
- [Linux cgroup v2 admin guide](https://docs.kernel.org/admin-guide/cgroup-v2.html)
  — canonical reference for the counters we read.
- [psutil documentation](https://psutil.readthedocs.io/) — the
  library `§10.1` would depend on.
- [BenchExec](https://github.com/sosy-lab/benchexec) — reference
  implementation of cgroup-based reproducible resource measurement;
  worth cribbing from for creator-mode work (§10.2).
- `RESEARCH.md` on branch `pcpu-overshoot-investigation` — deeper
  analysis of alternatives considered (pidstat, cgmemtime,
  memory_profiler, a hand-rolled `/proc` parser).
- `DEEP_DIVE_PROGRESS.md` on the same branch — investigation
  confirmation for the ps pathologies described in §2.

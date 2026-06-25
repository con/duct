# Decision log — collector / measurement POC

Records every non-trivial design or implementation decision, each with a
one-line rationale. **Bold** marks decisions I was unsure about and that are
worth revisiting.

See `POC_BRIEF.md` for the goal and `resource-collectors.md` for the design.

## Environment / setup

- Container venv lives at `.venv` (created with `uv`, not the host's
  `~/.venvs/duct`); installed `-e .[all]` plus `tox`, `pytest`, and `psutil`
  so both the stdlib-only and optional-psutil paths can be exercised. Rationale:
  the container ships `uv` only (no pip/tox/venv preinstalled).
- Tests live under `test/` (singular), matching the existing repo layout — the
  brief/CLAUDE.md say `tests/`, but I follow the repo's actual convention.
  Rationale: behavior-preserving, don't fork the test tree.

## Decisions

<!-- newest first; one line each, **bold** the uncertain ones -->

- **Scope = data collection e2e (incl. the end-of-run summary).** The
  collector/measurement pipeline replaces the old sampling + per-sample-max
  aggregation, emits new renamed measurement keys per report, AND writes the
  end-of-run `execution_summary` from those same measurements (its keys update
  to the new names). The other log consumers — `plot.py` / `ls.py` /
  `pprint.py` — are explicitly NOT touched this round (user decision).
- Replace, don't reproduce: old fields become new namespaced keys carrying the
  same data (e.g. `rss` → `ps_rss`, `total_rss` → `ps_rss_total`); there is no
  legacy/back-compat field block (user decision — "only new renamed fields").
- Per-report usage record uses a single `measurements` object keyed by
  measurement name: per_pid keys hold a `{pid: value}` map, single keys hold a
  scalar. (Design's "measurements are keys" framing; user deferred to judgment.)
- CLI: add a `--measurements` flag (default: all available keys). Requesting a
  `psutil_*` key without psutil installed is a clean error. (user decision)
- Cgroup here is v2 (`/sys/fs/cgroup/memory.peak`, readable); v1
  `memory.max_usage_in_bytes` path is code-only/untested in this container.

### Implementation architecture (after reading the code)

- Module split: `_collectors.py` (pure I/O → raw readings: `Scope`/`Reduce`/
  `Derive` enums, `Measurement`, the ps/cgroup/psutil collectors, key registry)
  and `_aggregation.py` (buffer raw readings, aggregate-once: derive → collapse
  → reduce, with per-key seeds carried across report boundaries + a run-level
  summary accumulator). Keeps pure collection separate from stateful reduction.
- The brief's ps keys are exactly `ps_rss`, `ps_rss_total`, `ps_pdcpu`,
  `ps_cpu_seconds` — so the new model **drops `pmem`, `vsz`, and lifetime
  `pcpu`** entirely (not in the design's key list). The ps `-o` columns shrink
  to `pid,rss,cputime,cmd`. `cputime` is parsed by reusing
  `etime_to_etimes` (same `[[DD-]HH:]MM:SS` grammar).
- **Added a non-brief `ps_cmd` key** (per_pid, reduce=last) to keep per-pid
  command labels in the record — needed for plot labels / `ls` / the e2e
  child-counting test, and it exercises a string-valued per_pid measurement.
  Mild stretch of the "measurement = numeric" framing; revisit.
- Per-report usage record is replaced by `{timestamp, num_samples,
  measurements:{key: scalar | {pid: value}}}`; old `processes`/`totals`/
  `averages` blocks are gone. Records carry only selected+available keys.
- `execution_summary` is rewritten from the run-level accumulator and **always
  emits the full key set** (optional cgroup/psutil keys present as `null` when
  unavailable) so info.json schema is environment-independent and `test_schema`
  stays deterministic. Summary keys: meta (unchanged) + `peak_ps_rss_total`,
  `ave_ps_rss_total`, `ps_cpu_seconds`, plus `peak_cgroup_rss_peak`,
  `peak_psutil_pss_total` (null when absent).
- Renaming summary keys forces updating `ls.py`'s `LS_FIELD_CHOICES` registry
  and bumping `__schema_version__` — this is the schema test's own sanctioned
  workflow ("Fails when schema changes — bump schema version"), treated as a
  field-registry update, NOT as reworking `ls`/`plot`/`pprint` behavior (still
  out of scope; they keep reading their existing test fixtures, so their tests
  stay green; live plot/ls on new-format logs is explicit follow-up).
- **cgroup scope = duct's own cgroup peak** (resolved from `/proc/self/cgroup`;
  v2 `memory.peak`, v1 `memory.max_usage_in_bytes`), since under SLURM duct runs
  inside the job cgroup. Reader-mode only; refuse cleanly if unreadable.
- **Summary keys fully replaced** (not additive): old `peak_rss`/`peak_vsz`/
  `peak_pmem`/`peak_pcpu`/`average_*` are gone, replaced by `peak_ps_rss_total`,
  `ave_ps_rss_total`, `ps_cpu_seconds`, `peak_cgroup_rss_peak`,
  `peak_psutil_pss_total` (meta keys unchanged). This honors "only new renamed
  fields" for the summary too. The rename's unavoidable cascade: `ls.py`'s
  `LS_FIELD_CHOICES` registry, the `ls --fields` default in `cli.py` (`peak_rss`
  → `peak_ps_rss_total`, else argparse rejects its own default), and
  `EXECUTION_SUMMARY_FORMAT`. Treated as the schema test's sanctioned
  "bump schema version" workflow — `__schema_version__` 0.2.2 → 0.3.0 — NOT as
  reworking ls/plot/pprint *behavior* (their logic + fixtures stay untouched and
  green; `pprint`'s humanize map simply won't pretty-print the new keys, which
  is fine for the POC). `ps_pdcpu` rate is generic Δfield/Δt = **cputime-seconds
  per wall second (≈cores, 1.0 = one core), NOT percent** like the old `pcpu`;
  kept generic so future io rates fit the same `derive=rate`. Revisit.
- `ps` is the liveness signal: when it returns no pids the whole sample is
  dropped (not buffered, not counted) so a trailing empty reading can't skew a
  delta/total. `add_sample()` returns whether a sample was recorded; reporting
  is no longer gated on a nonzero ps pid count, so a non-ps-only selection
  (e.g. just `cgroup_rss_peak`) still emits records.
- **`ps_cpu_seconds` delta clamps to 0 on a negative window** (a pid with
  accrued cputime exits, so the summed cumulative total drops below the seed).
  The lost counter can't be attributed without per-pid delta tracking; clamping
  under-counts that window. Acceptable for the POC; a per-pid delta sum would
  fix it. Revisit.
- Collectors expose `collect()` (per-sample) / `read()` (per-report) with no
  `ts` arg — the aggregator stamps `time.monotonic()` (for rate Δt) and a wall
  isoformat (for the record) centrally, keeping collectors pure.
- The first foundation commit was reformatted by pre-commit and aborted, so the
  collector+aggregation modules landed inside the "wire the engine" commit
  rather than as a separate commit. Harmless; history is clean.

### Out of scope — interface fit (per brief)

- **`io` collector:** fits cleanly. It is just another per-sample/per-pid
  collector whose counters use `derive=rate` exactly like cputime
  (`io_read_rate` = `rate(read_bytes)`), and node `iowait` is a single-read like
  cgroup. No new machinery needed.
- **`/proc` sub-second CPU:** fits — same `derive=rate` measurement, different
  collector reading `/proc/<pid>/stat`. Only the source changes; the reducer is
  identical. (Confirms the rate derive belongs to the measurement, not ps.)
- **Named key-groups / presets:** easy to add over the existing registry as an
  alias layer expanding to keys before `resolve_selection`; deliberately not
  built.
- **Differential (same metric, two collectors):** the model already supports it
  — `ps_pdcpu` and `psutil_pdcpu` coexist and are recorded side by side, so
  comparing two methods of the same quantity is just selecting both keys. The
  awkward part is purely presentation (plot/ls), which is out of scope.

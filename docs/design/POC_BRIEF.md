# POC implementation brief — collector / measurement resource stats

This worktree is a throwaway **proof of concept**. Goal: make the design in `docs/design/resource-collectors.md` concrete enough to evaluate and to anchor a PR (the design doc and this implementation go up together). It does **not** need to be the final shape — it needs to work, be reasonably clean, and surface the real problems the design sketch can't.

## What to build (one vertical slice that exercises the whole interface)

Implement the collect → aggregate model from `resource-collectors.md`:

- **Pure collect, aggregate once per report.** Each sample, collectors append raw readings to a buffer (collect does no derivation and holds no cross-sample state). At each report interval, aggregate once: **derive** (e.g. pdcpu from cputime) → **collapse** per-pid readings into single values → **reduce** over the interval (a level reduces by `max`; a counter by `delta`/`last`). Keep the previous window's last reading per key as the **seed** for deltas that cross a report boundary.
- **Measurements are keys.** A measurement = `(name, scope, derive?, reduce)` where `scope` is `per_pid` or `single`. The user selects which measurement keys to record (default: all available keys). Collectors are internal; a collector batches the I/O for all of its selected keys (one `ps` call serves every `ps_*` key).
- **Collectors:**
  - **`ps`** (always available, per-pid). Keys: `ps_rss` (per_pid, max), `ps_rss_total` (single, max), `ps_pdcpu` (per_pid, derive rate from `cputime`, max), `ps_cpu_seconds` (single, delta of `cputime`). Add `cputime` to the `ps -o` columns (a one-line change).
  - **`cgroup`** (available iff a memory cgroup is present; single value; read once per report). Key: `cgroup_rss_peak` (single, last) from `memory.max_usage_in_bytes` (cgroup v1) / `memory.peak` (v2). Reader-mode only — no sudo/setuid/privilege probes; refuse cleanly if the file isn't readable; never create a cgroup.
  - **`psutil`** (optional, available iff `psutil` is importable; per-pid). Keys: `psutil_pss` (per_pid, max; Linux), `psutil_pss_total` (single, max), `psutil_pdcpu` (per_pid, rate from psutil's raw `cpu_times()` — **not** `cpu_percent()`, so the collector stays pure). psutil must be an **optional** dependency (`options.extras_require` "all"), never required for `con-duct run`; a clean error if a `psutil_*` key is requested without psutil installed.
- **Behavior-preserving where possible:** existing ps-based numbers and the existing tests should stay green; cputime/pdcpu/cgroup/psutil are additive.

## Constraints (follow the repo `CLAUDE.md`)

- `con-duct run` stays standard-library-only by default; psutil only via `extras_require`.
- Strict typing (`from __future__ import annotations`), `pathlib` over `os.path`, tests under `tests/`, run `tox` (lint, typing, py3) before declaring done.
- **Namespacing:** never overload an existing field name with new semantics; each new measurement is a distinct key.

## Process requirements (IMPORTANT)

- **Keep a decision log** in a git-tracked file: `docs/design/DECISIONS_LOG.md`. Record every non-trivial design or implementation decision, each with a one-line rationale.
- **Bold any decision you were unsure about** (`**like this**`) in that log, so they are easy to find and revisit.
- Commit as you go with clear messages.

## Out of scope (note in the log if relevant, do NOT build)

- The `io` collector, named key-groups/presets, a `/proc` sub-second CPU source, and running multiple collectors of the same metric for differential comparison. If the interface makes any of these obviously easy or awkward, note it in the decision log — but don't implement them here.

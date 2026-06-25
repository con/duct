# Resource statistics: correctness problems and a proposed collector/measurement model

## Problems with the current resource statistics

duct's per-process resource statistics (collected via `ps`) have several correctness problems:

1. **CPU is a lifetime average, not a rate.** `ps -o pcpu` reports cumulative CPU% over the whole process lifetime, so summing it across a process tree overshoots the core ceiling (con/duct#399 shows 5363% on a 20-core machine) and cannot show *when* CPU was actually spent. The plot-time correction in con/duct#424 reconstructs an instantaneous rate, but only approximately: it works from the already-`max`-aggregated `pcpu`, so it is an upper bound whose error grows with run length.

2. **Memory is summed, double-counting shared pages.** `total_rss` is the sum of per-process `rss`, so shared pages (shared libraries, etc.) are counted once per process, overstating real memory use.

3. **Aggregation happens per sample, discarding intra-interval detail.** Each sample is immediately folded into a running `max` and dropped. Because the individual samples are gone, a per-interval CPU rate cannot be recovered after the fact, and short spikes between report points are lost.

4. **Every field is reduced by `max`.** That is correct for an instantaneous level (memory, %CPU) but wrong for a cumulative counter (e.g. CPU-seconds), where the meaningful quantity is a difference between readings.

5. **`pcpu` is not portable.** On Linux it is a lifetime average; on macOS it is a decayed moving average. The same field means different things on different platforms.

## Proposal

Two connected changes.

### 1. Aggregate once per report, over kept readings

Today each sample is reduced immediately into a running aggregate, then dropped. Instead, keep the raw readings for a report interval and aggregate them once, at report time.

This is what makes a per-sample instantaneous CPU rate ("pdcpu") possible at all: `pdcpu = Δ(CPU time) / Δ(wall time)` between consecutive readings, which needs the individual readings that per-sample `max` currently discards. Each reported value is then the **max** of those per-sample rates over the interval, so a short CPU spike between report points is preserved rather than averaged away.

It depends on collecting **cumulative CPU time** instead of `pcpu`. `cputime` is a one-line addition to the `ps` columns duct already requests; unlike `pcpu`, it is the same cumulative quantity on Linux and macOS, so the rate is identical on both. (Deriving the rate from it was prototyped in con/duct#423.)

There is a resolution tradeoff, and it is the user's to make. `ps` cputime has whole-second resolution, so the shorter the interval a rate is computed over — the closer the sample interval gets to ~1s — the more a reported "spike" can be a quantization artifact rather than a real one; longer intervals are smoother but can hide real spikes. duct exposes the knob (sample interval) and can offer finer-resolution sources (e.g. a `/proc` reader on Linux) so the user chooses where to sit on the sensitivity/noise tradeoff.

### 2. A collector / measurement interface

Define two roles:

- A **collector** does one I/O pass and produces a set of **measurements** — e.g. `ps` produces `rss`, `cputime`, …; a cgroup collector reads the kernel's peak-RAM counter.
- A **measurement** is a named, namespaced value that declares its scope (per-process or total) and how it reduces over the interval — an instantaneous level reduces by `max`; a cumulative counter is differenced, either as a per-interval total or as a per-sample rate whose peak (`max`) reveals spikes.

The pipeline becomes:

```
per sample:  collect (pure)  → append raw readings to a buffer
per report:  aggregate = derive (e.g. rate from cputime) → combine across processes → reduce over the interval → write
```

This makes new data sources modular and composable instead of special-cased. The motivating example is cgroup `memory.max_usage_in_bytes`: the kernel's high-water peak RAM, which cannot miss a between-sample spike, is job-scoped under SLURM, and is the number an HPC `--mem` request needs. As a collector/measurement it is just another entry; without the interface, a new total has to mutate the shared sample object — which is what made an earlier cgroup prototype (con/duct#415) awkward. Namespacing measurements (a cgroup peak is a distinct field, never overwriting the ps-summed total) keeps different sources or methods from silently colliding under one field name.

Users select measurements by key (e.g. `ps_rss`, `cgroup_rss_peak`); the collector behind each key is internal, and a collector batches the I/O for all of its selected keys, so selecting several keys from one source is still a single pass. Named groups of keys are possible later but are not required.

The same interface should absorb other collectors without special-casing. Sketching several is how we check the shape holds:

<details>
<summary>How collectors map onto the interface — ps, cgroup, psutil, /proc, io</summary>

```
Collector:   available() -> bool;  measurements;  collect(ts) -> [reading];  report_read(ts) -> [reading]
Measurement = (name, scope, derive?, reduce)
  scope  = per_pid | single             # single = one value; the collector decides how (sum of its pids, a kernel read, a system read)
  derive = e.g. rate(cputime)           # counter -> per-sample rate; optional
  reduce = max | mean | delta | last    # per-interval collapse

# ps — per-pid, always available (the baseline)
collect: one `ps` call -> reading per pid {rss, cputime}
  ps_rss          per_pid  reduce=max
  ps_rss_total    single   reduce=max                 # the ps collector sums its pids per tick, then max
  ps_pdcpu        per_pid  derive=rate(cputime)  reduce=max
  ps_cpu_seconds  single   reduce=delta(cputime)

# cgroup — totals only, read once per report (kernel high-water mark)
available:   memory cgroup present
report_read: memory.max_usage_in_bytes -> reading {mem_peak}
  cgroup_rss_peak single   reduce=last                # kernel already took the peak; no per-pid pass

# psutil — optional per-pid (PSS + finer cputime), only if installed
available: `import psutil` works
collect:   iterate procs (getsid filter) -> reading per pid {pss, uss, cputime}
  psutil_pss        per_pid  reduce=max               # Linux; shared pages split across sharers
  psutil_pss_total  single   reduce=max               # sum = exact session footprint
  psutil_pdcpu      per_pid  derive=rate(cputime)  reduce=max   # sub-second, cross-platform

# /proc — Linux, per-pid, sub-second, stdlib
available: Linux + /proc
collect:   read /proc/<pid>/stat for session pids -> reading per pid {cputime, ...}
  proc_pdcpu        per_pid  derive=rate(cputime)  reduce=max   # same derive, finer source

# io — NEW / speculative: does it fit, and what does it reveal?
collect: /proc/<pid>/io + /proc/<pid>/stat per pid -> reading per pid {read_bytes, write_bytes, blkio_ticks}
  io_read_rate      per_pid  derive=rate(read_bytes)   reduce=max   # counter -> rate, exactly like cputime
  io_write_rate     per_pid  derive=rate(write_bytes)  reduce=max
  io_blocked_pct    per_pid  derive=rate(blkio_ticks)  reduce=max   # time blocked on block-IO (needs delay accounting)
  io_wait_pct       single   reduce=max                # node iowait (/proc/stat): a single read, same shape as cgroup
```

What the sketch shows: every collector is the same three pieces (`available` / `collect` / `measurements`); counters always reduce by `rate`/`delta` and levels by `max`. A measurement is either per-pid (rows) or a single value — and a single value is whatever the collector produces: a sum of its own pids (ps total), a kernel read (cgroup peak), or a system read (iowait). So a system-wide signal is not a special scope; it is a single-value collector like cgroup. The shape holds across all five.

</details>

## What this enables

- A per-sample instantaneous CPU rate that can reveal spikes, cross-platform, with a user-controlled resolution/noise tradeoff.
- Kernel-accurate peak memory (cgroup) for HPC sizing, added as a modular collector rather than special-cased.
- Running more than one collector at once — e.g. measuring the same quantity two ways to compare them directly.
- Future sources (psutil, `/proc`, I/O statistics) added as collectors without touching the core.

## Other approaches considered

- **Surgical fixes without the interface:** change `total_rss` to `max(per-process rss)` instead of the sum (removes the shared-page double-count, but undercounts a large private child), and keep the plot-time CPU correction (already shipped, approximate). Smaller, but does not generalize and does not let new sources compose.
- **Add `cputime` and the cgroup peak as standalone fields, no refactor:** cheaper and delivers the two numbers, but commits field names and record placement without the structure, and each additional source stays ad-hoc.

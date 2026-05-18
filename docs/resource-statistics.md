# Interpreting duct's resource statistics

duct records resource usage in two places:

- **`usage.jsonl`**: one JSON record per report interval (default: every 60 seconds), capturing per-process and session-total stats aggregated over that window.
- **`execution_summary`** (printed at exit and stored in `info.json`): a whole-run summary of peak and average values across the full execution.

The numbers in both come from the same sampling pipeline.
This document explains what those numbers actually measure, how `con-duct plot` renders them, and where they're trustworthy vs misleading.

## How duct samples and aggregates

Duct polls the monitored process tree on two independent intervals:

- **`--sample-interval` (default 1.0s)**: how often duct reads per-pid stats via `ps -s <session_id>`.
  Each read is a *sample*.
- **`--report-interval` (default 60.0s)**: how often duct writes an aggregated record to `usage.jsonl`.
  Each record summarizes all the samples taken during that report window.

Aggregation within a report window uses **max reduction**:

- For each per-pid metric, the reported value is the maximum observed across all samples of that pid in the window.
- For each session-total metric (`total_rss`, `total_pcpu`, etc.), the reported value is the maximum observed across all samples' totals in the window.

Consequences worth knowing:

1. **Short spikes between samples are not recorded.**
   A process that briefly allocates 10GB and frees it within a single sample interval is invisible to duct.
2. **Per-pid and session-total peaks may come from different sample moments.**
   Per-pid max-reduction and total max-reduction are independent.
   The same record can have `stats[A].rss = X` (A's peak from one sub-sample) and `total_rss = Y` (the peak simultaneous total from another sub-sample).

---

## CPU — `pcpu`

### What it measures

On Linux, `ps -o pcpu` is computed per process as:

```
pcpu = ((utime + stime) / (now - process_start_time)) × 100
```

- `utime + stime` is **cumulative CPU time consumed by the process since it started** (kernel ticks from `/proc/[pid]/stat`).
- `now - process_start_time` is **wall-clock time elapsed since the process started**.

So `pcpu` is *the fraction of wall time the process has spent on CPU, averaged from birth until the moment of sampling*.
It is a **lifetime average**, not an instantaneous rate.
This differs from `top(1)`, which shows instantaneous-over-refresh-interval.

### `etime` is integer seconds

`ps -o etime` reports elapsed time as an integer count of seconds (formatted `[[DD-]HH:]MM:SS`).
This has consequences for short-lived and freshly-spawned pids:

- During a pid's first second of life, `etime` reads as `00:00`.
  ps's `pcpu` calculation divides by this `etime`, and the result during sub-second life is unstable.
- A pid sampled at sub-second age that has accumulated meaningful CPU work across multiple threads can yield extreme `pcpu` readings.
  Issue [#399](https://github.com/con/duct/issues/399) included a single pid reporting 5347% `pcpu` at `etime=3` on a 20-core machine, which is physically impossible: it came from a sub-second-young sub-sample where ps's calculation was racy.

This is why sample intervals shorter than `1.0s` behave erratically.
Consecutive samples of the same pid often see the same integer `etime`, so derived measurements (like the `--cpu ps-cpu-timepoint` view, below) discard those points because `Δetime = 0`.

### Three scenarios to build intuition

#### Scenario A: long-running steady-state process at 100% CPU

```
t = 1s:   cumulative CPU = 1.0s,  elapsed = 1s   → pcpu = 100%
t = 10s:  cumulative CPU = 10.0s, elapsed = 10s  → pcpu = 100%
t = 60s:  cumulative CPU = 60.0s, elapsed = 60s  → pcpu = 100%
```

For steady-state workloads, lifetime-average converges to instantaneous.
*This is why the mental model "pcpu = current CPU usage" works most of the time.*

#### Scenario B: brief burst, then idle

A process that does 1 second of 100% CPU work, then sits idle:

```
t = 1s:   cumulative CPU = 1.0s, elapsed = 1s    → pcpu = 100%
t = 2s:   cumulative CPU = 1.0s, elapsed = 2s    → pcpu =  50%
t = 10s:  cumulative CPU = 1.0s, elapsed = 10s   → pcpu =  10%
t = 100s: cumulative CPU = 1.0s, elapsed = 100s  → pcpu =   1%
```

After the burst, `pcpu` decays toward 0.
The process "remembers" past CPU work and slowly forgets as its elapsed time grows.
Counterintuitive if you expected a real-time number.

#### Scenario C: the pathological summation case

Many short-lived, multi-threaded native child processes, as happens under tox when pip compiles C extensions:

```
Child 1 runs for 200ms on 4 cores, observed by sample at t=150ms:
  cumulative CPU = 600ms, elapsed = 150ms
  → pcpu reported = 400%

…30 such children observed during a single sample…

sum across children at sample time = 30 × 400% = 12,000%
system physical ceiling (20 cores)  =  2,000%
```

Each individual child's number is correct for what `ps` is answering ("fraction of wall time spent on CPU, averaged from start").
The problem is that *summing* lifetime-averages across processes that took turns on the CPU produces a total claiming work the system didn't have the cores to do.
The children ran sequentially, but the sum over the report window treats the spikes as simultaneous.

### When `pcpu` is reliable

| Workload shape                                | `pcpu` reliability                                      |
|-----------------------------------------------|---------------------------------------------------------|
| Single long-running steady-state process      | Accurate                                                |
| Few long-running processes at steady state    | Accurate                                                |
| Bursty processes that are long-running        | Accurate at the average; misses burst structure         |
| Many short-lived (few second) child processes | **Unreliable: can inflate dramatically when summed**    |
| Multi-threaded native code bursts             | Per-process `pcpu` correct; summed totals may overshoot |

---

## Memory — `rss` and `pmem`

`ps -o rss` reports per-process **resident set size**: physical memory currently mapped into the process's address space, in kilobytes.
This counts:

- Private pages the process has allocated and touched.
- **Shared pages** (libraries, copy-on-write memory after `fork()`) that the process has mapped, counted independently in **each** process that maps them.

`ps -o pmem` is derived: `rss` divided by total system RAM, expressed as a percentage.
It inherits every property of `rss` and adds a host-dependent denominator.

### The shared-page issue

When multiple processes share the same physical page, that page appears in **each process's RSS**, but the physical page exists only once.

Example: a Python parent process with 100MB RSS forks 10 child workers.
Immediately after fork:

```
Parent RSS:  100MB
Child 1 RSS: 100MB
…
Child 10 RSS: 100MB

Sum of RSS across processes: 1100MB
Actual physical memory used: ~100MB (all shared with parent)
```

As children write to their copy of each page, copy-on-write triggers and the page becomes private.
At that point physical use genuinely grows.
So `sum(rss)` is a **loose upper bound** on actual usage: never less than true usage, often much more.

For a duct-monitored Python test suite with `pytest-xdist` spawning 8 workers, expect `sum(rss)` to overstate physical memory by 3-5×.

---

## What `con-duct plot` renders

`con-duct plot <usage>` renders, per report-interval record:

- **Per-pid traces**: one faint dotted line per pid.
  CPU is on the primary y-axis.
  RSS is on a secondary axis (`twinx`) so the two scales don't fight.
  Color encodes metric, not pid identity.
- **Envelope lines**: summarize the per-pid cloud at each timestamp (one solid lower bound + one dashed upper bound).
- **Optional host-memory annotation**: when `info.json` is alongside the usage file, the rss legend label includes total host RAM (e.g. `rss (host: 256.0GB)`).
  Useful for SLURM contexts.
  Without `info.json`, plain `rss`.

### `--cpu` mode flag

duct stores `pcpu` (lifetime average from ps) per pid in `usage.jsonl`.
The plot can render this two ways:

- **`--cpu ps-pcpu` (default)**: plot the raw lifetime ratio untransformed.
  "Lossless" view: every point on the chart is an unaltered ps reading.
  Useful when you want to see exactly what the sampler captured.
- **`--cpu ps-cpu-timepoint`**: at plot time, derive a per-interval estimate from consecutive `(pcpu, etime)` pairs: `(curr_pcpu × curr_etime − prev_pcpu × prev_etime) / Δetime`.
  This inverts ps's lifetime-average formula to extract an approximate instantaneous CPU rate.
  Motivated by [Scenario C](#scenario-c-the-pathological-summation-case): lifetime averages of short-lived bursty processes overstate "current" usage by orders of magnitude.

Both modes have caveats:

- The raw `ps-pcpu` mode shows what ps reported, including lifetime-average inflation.
  A pid that ran on 4 cores for 150ms and went idle peaks at 400% in the first report interval that observed it, then decays toward its true average as `etime` grows in subsequent intervals.
- The derived `ps-cpu-timepoint` mode is approximate (delta math on max-reduced samples).
  It discards each pid's first observation (no prior point to delta against), so short-lived pids that appear in only one record drop out entirely.
  CPU bursts from those pids are not visible in the timepoint view, but remain visible in the `ps-pcpu` view via `total_pcpu`.

### Envelope semantics

The plot draws two envelopes over the per-pid trace cloud:

- **Lower bound (solid)**: max-across-pids at each timestamp.
  Reads as "at least this much was in use."
- **Upper bound (dashed)**: depends on what's being plotted.
  - **RSS, and CPU in `ps-pcpu` mode**: `total_*` from the record.
    duct computes this as the peak simultaneous total observed across the report window's sub-samples.
  - **CPU in `ps-cpu-timepoint` mode**: sum-across-pids of the derived (instantaneous) values at each timestamp.
    Used here because `total_pcpu` is a peak of *lifetime averages* and doesn't share units with the derived instantaneous values.

## Common questions

### Why is the raw `pcpu` line in `ps-pcpu` mode so much higher than `ncores × 100%`?

Two compounding reasons, either of which can do it alone:

1. **Single-pid extremes from ps.**
   For pids sampled at sub-second age, ps's `cputime / etime` calculation is unstable (see [`etime` is integer seconds](#etime-is-integer-seconds)).
   Individual pids can briefly report thousands of percent.
2. **Summed lifetime-averages across many short-lived pids.**
   Even if each pid's `pcpu` is finite, summing lifetime averages across processes that took turns on the cores produces a total claiming work the cores couldn't have done.
   See [Scenario C](#scenario-c-the-pathological-summation-case).
   Most common in workloads that spawn many short-lived child processes involving native/multi-threaded code: pip install compiling C extensions, `make -j`, tox, any CI/build workflow.

### Why is the `ps-cpu-timepoint` line lower than the `ps-pcpu` line?

`ps-pcpu` plots the lifetime average from ps.
A burst captured early in a pid's life pulls the reported `pcpu` high, and that pid's trace decays slowly as `etime` grows.
`ps-cpu-timepoint` instead estimates an instantaneous rate per report interval, so a burst contributes only to the interval that contained it.

Example: a pid that did 600ms of CPU on 4 cores in its first 150ms and was idle thereafter.
`ps-pcpu` shows ~400% in the first report interval and a decaying trace in subsequent intervals (until the pid dies or the trace falls off the chart).
`ps-cpu-timepoint` shows ~400% only in the burst interval and ~0% thereafter.

The timepoint view is more "honest" about current usage but loses the cumulative-effort information that `ps-pcpu` carries.

### Why does `total_*` not equal `sum(per-pid max)` in a record?

duct max-reduces per-pid stats and session totals independently within a report window.
A pid's reported `rss` is its max across sub-samples in the window; `total_rss` is the max of the *simultaneous total* across those sub-samples.
The per-pid peaks may have happened at different moments, so summing them counts moments that never coexisted.
`total_*` is the actual peak simultaneous footprint and is the right number for sizing.

### My RSS chart grew a lot when I added more worker processes. Did memory usage really grow proportionally?

Probably not.
If the workers are forked children of a common parent, each child's RSS counts the shared pages it inherited.
Per-pid traces and their max envelope grow roughly linearly with child count even when physical memory grows much less.
The dashed `total_rss` upper bound is closer to actual physical use, but still over-counts shared libraries linked by independent processes.
See [The shared-page issue](#the-shared-page-issue).

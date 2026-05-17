# Interpreting duct's resource statistics

duct records resource usage in two places:

- **`usage.jsonl`** — one JSON record per report interval (default:
  every 60 seconds), capturing per-process and session-total stats
  aggregated over that window.
- **`execution_summary`** (printed at exit and stored in `info.json`)
  — a whole-run summary: peak and average values across the full
  execution.

The numbers in both come from the same sampling pipeline. This
document explains what those numbers actually measure, where they're
accurate, where they're not, and what questions they can and can't
answer.

> **Who this is for.** End users reading `usage.jsonl` or
> `execution_summary` to interpret resource usage — for example,
> sizing a SLURM allocation for a follow-up job, debugging a memory
> issue, or comparing runs. If you're looking at a number and
> wondering "what does that actually mean" or "should I trust it,"
> this is the right document.

> **Scope.** This describes duct's current behavior, which uses
> `ps(1)` as the underlying sampler.

---

## Quick reference

| Field       | Answers                                                                                                             | Does **not** answer                         | Key caveat                                                                                                                                                                                  |
|-------------|---------------------------------------------------------------------------------------------------------------------|---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pcpu`      | fraction of wall time a process has spent on CPU, **averaged from its birth until each measurement**                     | current CPU usage at the moment of sampling | short-lived or recently-bursty processes can report much higher numbers than their current activity; summed across many such processes, totals can exceed the system's physical CPU ceiling |
| `rss`       | physical memory mapped into each process's address space, counting **shared pages in every process that maps them** | unique physical memory used by the session  | summing `rss` across forked children double-counts shared libraries and copy-on-write pages                                                                                                 |
| `pmem`      | `rss` as a percentage of total system RAM                                                                           | anything `rss` doesn't answer already       | inherits RSS caveats; comparing `pmem` across hosts with different RAM is misleading                                                                                                        |
| `vsz`       | total **virtual** address space the process has reserved (not necessarily using)                                    | how much physical RAM the process is using  | includes mapped files (even unread), library mappings, thread stacks, and allocator reservations; often orders of magnitude larger than `rss`                                               |
| `peak_*`    | max observed value during the run                                                                                   | anything happening *between* samples        | sub-sample-interval spikes are not captured                                                                                                                                                 |
| `average_*` | time-weighted mean of samples                                                                                       | "average while the process was active"      | averaged over the whole run, including idle time at start/end                                                                                                                               |

---

## How duct samples and aggregates

Duct polls the monitored process tree on two independent intervals:

- **`--sample-interval` (default 1.0s)** — how often duct reads
  per-pid stats via `ps -s <session_id>`. Each read is a *sample*.
- **`--report-interval` (default 60.0s)** — how often duct writes an
  aggregated record to `usage.jsonl`. Each record summarizes all the
  samples taken during that report window.

Aggregation within a report window uses **max reduction**:

- For each per-pid metric, the reported value is the maximum observed
  across all samples of that pid in the window.
- For each session-total metric (`total_rss`, `total_pcpu`, etc.),
  the reported value is the maximum observed across all samples'
  totals in the window.

Two consequences worth knowing:

1. **Short spikes between samples are not recorded.** If a process
   briefly allocates 10GB and frees it within a single sample
   interval, duct doesn't see it. Lowering `--sample-interval`
   catches shorter spikes at the cost of higher polling overhead.

2. **Per-pid and session-total peaks may come from different sample
   moments.** The reported peak for pid A is when *A* was at its
   max, which may not be when *the session as a whole* was at its max.
   See [Peak vs. average](#peak-vs-average) for a worked example.

---

## CPU — `pcpu`

### What it measures

On Linux, `ps -o pcpu` is computed per process as:

```
pcpu = ((utime + stime) / (now - process_start_time)) × 100
```

Where:

- `utime + stime` is **cumulative CPU time consumed by the process
  since it started** — a kernel counter, user-mode plus system-mode
  ticks from `/proc/[pid]/stat`.
- `now - process_start_time` is **wall-clock time elapsed since the
  process started**.

So `pcpu` is *the fraction of wall time the process has spent on CPU,
averaged from birth until the moment of sampling*. It is a **lifetime
average**, not an instantaneous rate.

This differs from what many users expect, and from what `top(1)`
shows (which is instantaneous-over-refresh-interval). A process's
`pcpu` in `ps` and in `top` can differ substantially.

### Four scenarios to build intuition

#### Scenario A: long-running steady-state process at 100% CPU

A compute-bound single-threaded process running at 100% CPU
continuously:

```
t = 1s:   cumulative CPU = 1.0s,  elapsed = 1s   → pcpu = 100%
t = 10s:  cumulative CPU = 10.0s, elapsed = 10s  → pcpu = 100%
t = 60s:  cumulative CPU = 60.0s, elapsed = 60s  → pcpu = 100%
```

For steady-state workloads, lifetime-average converges to
instantaneous. *This is why the mental model "pcpu = current CPU
usage" works most of the time* — long-running daemons and big compute
jobs pinning a core report numbers that match intuition.

#### Scenario B: brief burst, then idle

A process that does 1 second of 100% CPU work, then sits idle:

```
t = 1s:   cumulative CPU = 1.0s, elapsed = 1s    → pcpu = 100%
t = 2s:   cumulative CPU = 1.0s, elapsed = 2s    → pcpu =  50%
t = 10s:  cumulative CPU = 1.0s, elapsed = 10s   → pcpu =  10%
t = 100s: cumulative CPU = 1.0s, elapsed = 100s  → pcpu =   1%
```

After the burst ends, `pcpu` decays toward 0. The process
"remembers" past CPU work and slowly forgets as its elapsed time
grows. Counterintuitive if you were expecting a real-time number.

#### Scenario C: multi-threaded native process

A process with 4 native threads, each pinning a separate core,
running for 1 second of wall time:

```
cumulative CPU = 4.0s  (each thread contributed 1.0s)
elapsed time   = 1s
pcpu           = 400%
```

A single process can legitimately report `pcpu > 100%` when it uses
multiple cores simultaneously. The per-process ceiling is
`Ncores × 100`.

(Pure-Python multi-threaded code cannot exceed ~100% because of the
GIL — each process gets one core's worth of CPU regardless of thread
count. C extensions and native code can break out of this and report
multi-hundred-percent legitimately.)

#### Scenario D: the pathological summation case

This is the mechanism behind issue
[#399](https://github.com/con/duct/issues/399). Many short-lived,
multi-threaded native child processes, as happens under tox when pip
compiles C extensions for many dependencies:

```
Child 1 runs for 200ms on 4 cores, observed by sample at t=150ms:
  cumulative CPU = 600ms, elapsed = 150ms
  → pcpu reported = 400%

Child 2 runs for 200ms on 4 cores:
  → pcpu reported = 400%

…30 such children observed during a single sample…

sum across children at sample time = 30 × 400% = 12,000%
system physical ceiling (20 cores)  =  2,000%
```

Each individual child's number is correct for what `ps` is answering
("fraction of wall time spent on CPU, averaged from start"). The
problem is that *summing* those lifetime-averages across processes
that took turns on the CPU produces a total claiming work the system
didn't have the cores to do. The children ran sequentially; each
reports a high number individually; the sum treats them as
simultaneous.

This is why duct can report `peak_pcpu` numbers that exceed the
system's physical CPU ceiling. It's not wrong per se — it's an
accurate sum of individually-correct lifetime averages — but it
doesn't answer the question most users are asking.

### When `pcpu` is reliable

| Workload shape                                | `pcpu` reliability                                      |
|-----------------------------------------------|---------------------------------------------------------|
| Single long-running steady-state process      | Accurate                                                |
| Few long-running processes at steady state    | Accurate                                                |
| Bursty processes that are long-running        | Accurate at the average; misses burst structure         |
| Many short-lived (few second) child processes | **Unreliable — can inflate dramatically when summed**   |
| Multi-threaded native code bursts             | Per-process `pcpu` correct; summed totals may overshoot |

### Linux vs. macOS

macOS's `ps` uses a different formula: an **exponentially decaying
average** with a roughly 1-minute time constant. After a CPU burst
ends, the reported `pcpu` drops visibly within a minute rather than
decaying over the full process lifetime.

Practical implications:

- On macOS, `pcpu` for a long-idle-now-previously-busy process
  converges back to 0 much faster than on Linux.
- On macOS, summation across short-lived processes is less prone to
  overshoot than on Linux, because each process's contribution decays
  out faster.
- **Numbers are not directly comparable across platforms.** The same
  workload can report different `peak_pcpu` and `average_pcpu` on
  Linux vs. macOS. If you're comparing runs, compare within a
  platform.

---

## Memory — `rss` and `pmem`

### What they measure

`ps -o rss` reports per-process **resident set size**: the amount of
physical memory currently mapped into the process's address space, in
kilobytes. This counts:

- Private (anonymous) pages the process has allocated and touched.
- Shared pages (libraries, copy-on-write memory after `fork()`) **that
  the process has mapped**, with each process counted independently.

`ps -o pmem` is derived: `rss` divided by total system RAM, expressed
as a percentage. It inherits every property of `rss` and adds a
host-dependent denominator.

### The shared-page issue

The critical subtlety: when multiple processes share the same physical
page (because of `fork()`, or because they link the same library),
that page appears in **each process's RSS** — but the physical page
exists only once.

Example: a Python parent process with 100MB RSS (libpython, libc,
site-packages) forks 10 child workers. Each child inherits the
parent's address space via copy-on-write. Immediately after fork:

```
Parent RSS:  100MB
Child 1 RSS: 100MB
Child 2 RSS: 100MB
…
Child 10 RSS: 100MB

Sum of RSS across processes: 1100MB
Actual physical memory used: ~100MB (all shared with parent)
```

Summing RSS reports 1100MB. The system is using ~100MB. The sum is
off by a factor of 11.

As children write to their copy of each page, copy-on-write triggers
and the page becomes private to that child — at which point physical
memory use genuinely grows. So over time, `sum(rss)` becomes a looser
upper bound on actual usage: it's never less than true usage, but
can be much more.

### Typical inflation ranges

| Workload                                                | Sum-of-RSS vs. actual                              |
|---------------------------------------------------------|----------------------------------------------------|
| Single process                                          | 1:1 (accurate)                                     |
| Parent + few forked children, children mostly read-only | 3-5× inflated                                      |
| Parent + many forked children running similar code      | 10× or more inflated                               |
| Independent processes (not forked from a common parent) | Closer to 1:1, but still double-counts shared libs |

For a duct-monitored Python test suite with `pytest-xdist` spawning 8
workers, expect `sum(rss)` to overstate actual physical memory by
3-5×. For a parallel native compile (`make -j16`), each compile child
loads its own copy of libstdc++ and similar, so the overstating is
smaller (1.5-2×) but still present.

### When RSS is safe to read

- Single-process workloads: RSS is the right number.
- Per-process RSS in the per-pid data: correct for that process's
  perspective ("how much of its address space is resident"), even if
  much of that is shared.
- `sum(rss)` across forked children: treat as an **upper bound** on
  physical memory, not the actual footprint.

---

## Memory — `vsz`

### What it measures

`ps -o vsz` reports per-process **virtual set size**: the total
amount of virtual address space the process has reserved, in
kilobytes.

This counts much more than physical memory:

- **Memory-mapped files, even if never read.** `mmap(100GB_file)`
  adds 100GB to `vsz` without using any physical RAM until pages are
  touched.
- **Shared libraries.** Every `.so` mapped into the process — libc,
  libpython, libssl, libcuda, all the native parts of
  numpy/scipy/pandas/etc — contributes to `vsz`. These are shared
  with other processes and use far less physical memory than `vsz`
  implies.
- **Thread stacks.** Each thread gets an 8MB stack *reservation* by
  default on Linux. A process with 1000 threads has 8GB of `vsz` from
  stacks alone; physical use is kilobytes per thread.
- **Allocator reservations.** glibc malloc reserves arenas per thread
  (~64MB each). Go's runtime reserves a very large heap upfront
  (trivial Go programs can show 100GB+ `vsz` on some versions). The
  JVM reserves its configured max heap (`-Xmx`) in `vsz` whether or
  not it's used.
- **Sparse reservations.** `mmap(PROT_NONE, big_region)` reserves
  address space without committing anything.

`vsz` is "the largest amount of memory this process *could* touch if
it tried" — a theoretical upper bound, not a usage number. On a
64-bit system, a process can have terabytes of `vsz` with only
megabytes of RSS. This is normal.

### Summing `vsz` across processes isn't meaningful as a memory metric

Summing `vsz` has all the problems of summing RSS (shared libs counted
N times) plus the bigger-magnitude inflation from reservations and
mapped files. On a tox session that clones datalad datasets, pulls
containers, and scaffolds jobs, cumulative `vsz` can reach hundreds
of GB or multiple TB on a machine with 16GB of RAM. That number
doesn't correspond to anything physical.

### Where `vsz` is still useful — anomaly detection

`vsz` is not a sizing metric, but it is a useful **canary**. If your
workload's `peak_vsz` is much larger than you'd expect, something
did a lot of memory mapping. This could be:

- **Benign:** mmap'd container layers, git-annex objects, mmap'd data
  files, many threads, a Go or JVM runtime reserving heap.
- **Worth investigating:** a thread leak, a runaway `mmap` loop, a
  container tool misbehaving.

The value is: an order-of-magnitude change in `peak_vsz` between
runs of the same workload is a signal that something changed about
memory mapping behavior. It doesn't tell you *what*, but it tells
you *look*.

---

## Peak vs. average

### Peak

`execution_summary.peak_*` and per-sample-window maxes come from the
same reduction: the maximum observed value across samples.

Key properties:

- **Misses sub-sample-interval spikes.** With default
  `--sample-interval=1.0`, a 200ms spike to 10GB between samples is
  invisible. Lowering the interval catches shorter spikes, at the
  cost of more polling work.

- **Per-pid peak and session-total peak may come from different
  moments.** Example:

    ```
    sample 1: pid A = 1GB,  pid B = 0     → total = 1GB
    sample 2: pid A = 0,    pid B = 1GB   → total = 1GB

    aggregated report:
      stats[A].rss = 1GB   (A's peak, from sample 1)
      stats[B].rss = 1GB   (B's peak, from sample 2)
      total_rss    = 1GB   (max observed simultaneous total)
    ```

    `total_rss` is **not** the sum of per-pid peaks — that would be
    2GB, implying both processes were simultaneously at their peaks,
    which didn't happen. `total_rss` is the peak *simultaneous*
    usage. Both numbers are correct answers to different questions:

    - *"What's the most any individual process used?"* → per-pid peak.
    - *"What's the most the whole job used at any one moment?"* →
      `total_*`.

    **For SLURM allocation sizing**, you want `total_*` — it's the
    peak simultaneous footprint, and therefore the minimum
    allocation that would have fit this workload.

### Average

`average_*` is the time-weighted mean of samples over the run.
Sampling artifacts:

- **Averaged over the whole run, including idle time at start and
  end.** A process that used 2 cores for 10 seconds during a 60-second
  run has `average_pcpu` ≈ 33%, not 200%.
- **Sensitive to how the run started and ended.** A long startup or
  long teardown (both low-CPU) drags the average down.

Under `ps`-based sampling, `average_pcpu` is also affected by the
lifetime-average semantics described above — it's an average of
samples of lifetime-averages, which is a compound measurement. Treat
it as a rough "overall intensity" number, not a precise
utilization figure.

---

## Common questions

### Why is my `peak_pcpu` greater than `Ncores × 100%`?

Because `ps -o pcpu` reports a lifetime-average per process, and
summing lifetime-averages across many short-lived processes produces
totals that exceed what the system's cores could have done
simultaneously. See
[Scenario D](#scenario-d-the-pathological-summation-case).

Most common in workloads that spawn many short-lived child processes,
especially involving native/multi-threaded code: pip install
compiling C extensions, `make -j`, tox, any CI/build workflow.

### Why is my `peak_vsz` many times larger than total RAM?

`vsz` is virtual address space, not physical memory. It includes
reservations (thread stacks, allocator arenas, JVM or Go heap),
memory-mapped files (even unread), and shared library mappings. On a
64-bit system, `vsz` can legitimately exceed physical RAM by orders
of magnitude. See [Memory — `vsz`](#memory--vsz).

### My RSS number changed a lot when I added more worker processes. Did memory usage actually increase proportionally?

Probably not. If the workers are forked children of a common parent,
each child's RSS counts the shared pages (libraries, copy-on-write
memory) it inherited. `sum(rss)` grows roughly linearly with child
count even when physical memory usage grows much less. See
[The shared-page issue](#the-shared-page-issue).

### Can I compare numbers across Linux and macOS?

For the general shape, yes, but results will differ, with Linux over-reporting
in comparison to macOS. macOS `pcpu` uses decaying-exponential semantics;
Linux uses lifetime-average. The same workload can report different
`peak_pcpu` and `average_pcpu` on the two platforms. Memory numbers
(`rss`, `vsz`) have similar per-process semantics but differ in how
shared memory is reported. Compare runs within a single platform.

### How do I catch memory spikes shorter than my sample interval?

Lower `--sample-interval`. The default is 1.0s; dropping to 0.1s
catches spikes longer than ~100ms. Log size does not grow with
faster sampling, because the report window aggregates samples into
fixed-size records regardless of how many are taken.

The tradeoff is polling overhead — `ps` forks a subprocess each
sample. At very fast sampling (tens of ms), the polling cost becomes
a non-trivial fraction of a core.

### What should I use to size a SLURM allocation?

- **Memory allocation**: `execution_summary.peak_rss` as an upper
  bound. Remember it over-counts shared pages across forked
  children, so it's a safe-but-loose bound. For workloads with many
  forks, the real physical peak is often 1.5-5× smaller.
- **CPU allocation**: `execution_summary.peak_pcpu / 100` rounded up
  as a core-count estimate **only if your workload is
  steady-state**. For workloads with many short-lived native
  children, `peak_pcpu` can inflate past the system ceiling — in
  those cases, `Ncores` on the system that ran the job is a
  better upper bound than `peak_pcpu / 100`.
- **Wall time**: `execution_summary.wall_clock_time` plus headroom
  for variation.

### Why does `total_rss` disagree with `sum(per-pid rss)` in an aggregated record?

They answer different questions. `total_rss` is the peak
*simultaneous* total — the most the session used at any one moment.
`sum(per-pid rss)` over an aggregated record sums each process's
individual peak, which may have occurred at different moments. For
sizing and budgeting, `total_rss` is the one you want. See
[Peak vs. average](#peak-vs-average).

---

## Alternative sampler: `cgroup-ps-hybrid`

Most of this document describes behavior specific to `ps`-based
sampling. Duct also ships an opt-in alternative,
`--sampler=cgroup-ps-hybrid` (Linux cgroup v2 only), which reads
kernel cgroup counters for session totals while keeping `ps` for
the per-pid breakdown. Three of the `ps` pathologies above go away
for the session-wide numbers:

- Shared pages counted once (not per forked child).
- `total_pcpu` is physically bounded by the cores in use.
- CPU from children that exit between samples is still captured.

Per-pid values (`stats[pid].*`) are still `ps`-sourced. The
committed capability matrix shows which cells each sampler gets
right:

- [`test/sampler_matrix_ps.csv`](../test/sampler_matrix_ps.csv)
- [`test/sampler_matrix_cgroup-ps-hybrid.csv`](../test/sampler_matrix_cgroup-ps-hybrid.csv)

See [`design/multiple-samplers.md`](design/multiple-samplers.md)
for the full design.

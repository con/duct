# Temporary plot demo for #399 — REVERT BEFORE MERGE

This commit (`REVERT ME: TEMPORARY DEMO`) is on the draft PR only so
reviewers can compare the new plot output against real data without
hunting for log files. The actual PR content is the previous commit
(`plot: render per-pid pdcpu/pmem/rss instead of summed totals`).
This commit will be dropped via `git reset --hard HEAD~1` (or
equivalent) before the PR is marked ready.

## Reproduce default output

Install the branch and run on the bundled logs:

```sh
pip install -e '.[all]'
con-duct plot tmp-logs/399-usage.json --output 399.png
con-duct plot tmp-logs/fmriprep_sub-CC0007_usage.jsonl --output fmriprep.png
```

Output should match `tmp-images/00_399_plot_py_default.png` and
`tmp-images/00_fmriprep_plot_py_default.png` respectively.

## Filter / layout variants

The 01–08 PNGs in `tmp-images/` show alternative knob settings on
both datasets, side-by-side. Regenerate from the same logs with:

```sh
python tmp-render_variants.py
```

| variant | 399 | fmriprep |
|---|---|---|
| 00 — production CLI default | [PNG](tmp-images/00_399_plot_py_default.png) | [PNG](tmp-images/00_fmriprep_plot_py_default.png) |
| 01 — top 10 hybrid (renderer default) | [PNG](tmp-images/01_399_default.png) | [PNG](tmp-images/01_fmriprep_default.png) |
| 02 — top 5 hybrid | [PNG](tmp-images/02_399_top_5.png) | [PNG](tmp-images/02_fmriprep_top_5.png) |
| 03 — top 20 hybrid | [PNG](tmp-images/03_399_top_20.png) | [PNG](tmp-images/03_fmriprep_top_20.png) |
| 04 — no cap (chaos baseline) | [PNG](tmp-images/04_399_no_cap.png) | [PNG](tmp-images/04_fmriprep_no_cap.png) |
| 05 — pdcpu only (no pmem/rss) | [PNG](tmp-images/05_399_pdcpu_only.png) | [PNG](tmp-images/05_fmriprep_pdcpu_only.png) |
| 06 — split subplots, lines | [PNG](tmp-images/06_399_split_subplots.png) | [PNG](tmp-images/06_fmriprep_split_subplots.png) |
| 07 — top 40 hybrid | [PNG](tmp-images/07_399_top_40.png) | [PNG](tmp-images/07_fmriprep_top_40.png) |
| 08 — split subplots, stacked area (brainlife-style) | [PNG](tmp-images/08_399_stack_split.png) | [PNG](tmp-images/08_fmriprep_stack_split.png) |

## Sources

- `tmp-logs/399-usage.json` — 36-record duct log from con/duct#399
  (datalad/tox workload, 2853 unique pids, original totals.pcpu peak
  was 5363%).
- `tmp-logs/fmriprep_sub-CC0007_usage.jsonl` — one fmriprep subject
  (`ds003798`) on a SLURM cluster (324 unique pids, 36 records).

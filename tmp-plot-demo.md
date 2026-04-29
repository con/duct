# Temporary plot demo for #399 — REVERT BEFORE MERGE

This commit (`REVERT ME: TEMPORARY DEMO`) is on the draft PR only so
reviewers can compare the new plot output against real data without
hunting for log files. The actual PR content is the previous commit
(`plot: render per-pid pdcpu/pmem/rss instead of summed totals`).
This commit will be dropped via `git reset --hard HEAD~1` (or
equivalent) before the PR is marked ready.

## Reproduce

Install the branch and run on the bundled logs:

```sh
pip install -e '.[all]'
con-duct plot tmp-logs/399-usage.json --output 399-after.png
con-duct plot tmp-logs/fmriprep_sub-CC0007_usage.jsonl --output fmriprep-after.png
```

The pre-rendered "before" images were produced by the old `plot.py`
on `main` against the same logs.

## #399 (datalad/tox, 2853 unique pids)

Old `con-duct plot` summed `totals.pcpu` / `totals.rss`, producing
the 5363% peak that started this issue. The new chart shows per-pid
`pdcpu` lines with kernel pid-reuse and aggregation-noise filtered
out.

| before (main) | after (this branch) |
|---|---|
| ![#399 before](tmp-images/00_399_before.png) | ![#399 after](tmp-images/00_399_after.png) |

## fmriprep on SLURM (`ds003798` sub-CC0007, 324 unique pids)

Same story on a real fmriprep run.

| before (main) | after (this branch) |
|---|---|
| ![fmriprep before](tmp-images/00_fmriprep_before.png) | ![fmriprep after](tmp-images/00_fmriprep_after.png) |

## Sources

- `tmp-logs/399-usage.json` — 36-record duct log from con/duct#399.
- `tmp-logs/fmriprep_sub-CC0007_usage.jsonl` — one fmriprep subject
  (`ds003798`) recorded on a SLURM cluster.

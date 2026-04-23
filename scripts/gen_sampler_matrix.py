#!/usr/bin/env python3
"""Regenerate test/sampler_matrix.csv from sampler-matrix test results.

The conftest hook in test/conftest.py writes a JSONL file (one record
per sampler_matrix-marked test, pass/fail) during the pytest run. This
script reads that JSONL and pivots it into a CSV committed alongside
the tests: rows=workload, columns=sampler, cells=pass|fail|(not yet
tested).

Usage:
    python -m pytest test/              # populate .sampler_matrix_results.jsonl
    python scripts/gen_sampler_matrix.py

The CSV is checked in so reviewers (and the future CI drift check)
can see which cells are currently passing / failing / untested without
running tests.
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / ".sampler_matrix_results.jsonl"
CSV_PATH = REPO_ROOT / "test" / "sampler_matrix.csv"

# Fixed column order so the committed CSV is stable across runs.
# Extend here when new samplers are added.
SAMPLERS: list[str] = ["ps", "cgroup-ps-hybrid"]

UNTESTED = "(not yet tested)"


def load_records() -> list[dict[str, str]]:
    if not JSONL_PATH.exists():
        return []
    records = []
    with JSONL_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def pivot(records: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_workload: dict[str, dict[str, str]] = {}
    for r in records:
        workload = r.get("workload")
        sampler = r.get("sampler")
        status = r.get("status")
        if not (workload and sampler and status):
            continue
        # Last write wins if the same cell is reported twice in a run.
        by_workload.setdefault(workload, {})[sampler] = status
    return by_workload


def write_csv(by_workload: dict[str, dict[str, str]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["workload", *SAMPLERS])
        for workload in sorted(by_workload):
            row = [workload]
            for sampler in SAMPLERS:
                row.append(by_workload[workload].get(sampler, UNTESTED))
            writer.writerow(row)


def main() -> int:
    records = load_records()
    if not records:
        print(
            f"no matrix results found at {JSONL_PATH}; " "run `pytest test/` first",
            file=sys.stderr,
        )
        # Still write a header-only CSV so the file exists.
        write_csv({})
        return 0
    write_csv(pivot(records))
    print(f"wrote {CSV_PATH} ({len(records)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

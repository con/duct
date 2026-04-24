#!/usr/bin/env python3
"""Regenerate test/sampler_matrix_<sampler>.csv from matrix test results.

The conftest hook in test/conftest.py writes a JSONL file (one record
per sampler_matrix-marked test) during the pytest run. Each record:

    {
      "sampler":   "ps",
      "workload":  "memory_children",
      "metric":    "rss",
      "direction": "overreport",
      "expected":  "fail",
      "actual":    "fail",
      "nodeid":    "test/duct_main/test_sampler_matrix.py::..."
    }

This script pivots the JSONL into one CSV per sampler --
rows=``<workload>/<metric>``, columns=``no_<direction>``,
cells=pass|fail|n/a -- and writes them into test/. The CSVs are
checked in so reviewers can see each sampler's capability profile
(does-not-under-report / does-not-over-report, per workload/metric
pair) without running tests.

Each cell records the *actual* outcome (what the sampler did),
independent of whether that matched our committed expectation. The
commit hash for a given matrix snapshot is the source of truth for
what we expected at that point; the ``expected`` metadata lives in
the test marker, not the CSV.

Usage:
    python -m pytest test/              # populate .sampler_matrix_results.jsonl
    python scripts/gen_sampler_matrix.py
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / ".sampler_matrix_results.jsonl"
CSV_DIR = REPO_ROOT / "test"

UNTESTED = "n/a"


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


def group_by_sampler(
    records: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for r in records:
        sampler = r.get("sampler")
        if not sampler:
            continue
        grouped.setdefault(sampler, []).append(r)
    return grouped


def write_csv_for_sampler(sampler: str, records: list[dict[str, str]]) -> Path:
    # row label -> column label -> actual
    by_row: dict[str, dict[str, str]] = {}
    columns: set[str] = set()
    for r in records:
        workload = r.get("workload")
        metric = r.get("metric")
        direction = r.get("direction")
        actual = r.get("actual")
        if not (workload and metric and direction and actual):
            continue
        row_label = f"{workload}/{metric}"
        col_label = f"no_{direction}"
        # Last write wins if the same cell appears twice in one run.
        by_row.setdefault(row_label, {})[col_label] = actual
        columns.add(col_label)

    sorted_columns = sorted(columns)
    out_path = CSV_DIR / f"sampler_matrix_{sampler}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["workload/metric", *sorted_columns])
        for row_label in sorted(by_row):
            row = [row_label]
            for col in sorted_columns:
                row.append(by_row[row_label].get(col, UNTESTED))
            writer.writerow(row)
    return out_path


def main() -> int:
    records = load_records()
    if not records:
        print(
            f"no matrix results found at {JSONL_PATH}; " "run `pytest test/` first",
            file=sys.stderr,
        )
        return 0
    for sampler, sampler_records in sorted(group_by_sampler(records).items()):
        path = write_csv_for_sampler(sampler, sampler_records)
        print(f"wrote {path} ({len(sampler_records)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

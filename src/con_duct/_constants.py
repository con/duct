"""Constants used throughout con-duct."""

from __future__ import annotations

ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")
SUFFIXES = {
    "stdout": "stdout",
    "stderr": "stderr",
    "usage": "usage.jsonl",
    "usage_legacy": "usage.json",
    "info": "info.json",
}

"""Constants used throughout con-duct."""

__schema_version__ = "0.2.3"

ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")
SUFFIXES = {
    "stdout": "stdout",
    "stderr": "stderr",
    "usage": "usage.jsonl",
    "usage_legacy": "usage.json",
    "info": "info.json",
}

"""Constants used throughout con-duct."""

__schema_version__ = "0.3.0"

# Skip pids whose ps `etime` reads "00:00" -- i.e. too young for ps
# to report a non-zero elapsed time. Mitigates con/duct#399's
# churn-of-short-lived-workers case at the cost of the whole
# record (cmd/rss/vsz/pmem) for that pid in that sample. Mirrors
# the smon ancestor's pattern. Module-level toggle for now;
# elevating to a CLI flag later is a one-line wire-up.
DROP_YOUNG_PIDS = True

ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")
SUFFIXES = {
    "stdout": "stdout",
    "stderr": "stderr",
    "usage": "usage.jsonl",
    "usage_legacy": "usage.json",
    "info": "info.json",
}

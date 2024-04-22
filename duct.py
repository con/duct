from collections import defaultdict
from dataclasses import dataclass, field
import os


@dataclass
class Report:
    system: dict = field(default_factory=dict)
    subreports: list = field(default_factory=list)

@dataclass
class SubReport:
    number: int = 0
    pids_dummy: list = field(default_factory=lambda: defaultdict(list))


def pid_dummy_monitor(pid, elapsed_time, subreport):
    try:
        os.kill(pid, 0)
        subreport.pids_dummy[pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        report["pids"][pid].append(f"Process {pid} has terminated.")


def memory_total(elapsed_time, report):
    report["system"]["memory_total"] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'),

from collections import defaultdict
from dataclasses import dataclass, field
import json
import os


class Report:
    def __init__(self, command):
        self.command = command
        self.system = {}
        self.subreports = []
        self.stdout = ""
        self.stderr = ""
        self.system["memory_total"] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'),

    def __repr__(self):
        return json.dumps({
            "Command": self.command,
            "System": self.system,
            "Subreports": [str(subreport) for subreport in self.subreports],
            "STDOUT": self.stdout,
            "STDERR": self.stderr,
        })


@dataclass
class SubReport:
    number: int = 0
    pids_dummy: list = field(default_factory=lambda: defaultdict(list))


def pid_dummy_monitor(pid, elapsed_time, subreport):
    try:
        os.kill(pid, 0)
        subreport.pids_dummy[pid].append(f"Process {pid} checked at {elapsed_time} seconds")
    except OSError:
        subreport.pids_dummy[pid].append(f"Process {pid} has terminated.")

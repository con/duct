#!/usr/bin/env python3
import argparse
import json
import os
import pprint
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field

import profilers

__version__ = "0.0.1"
ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")


class Report:
    """Top level report"""

    def __init__(self, command, session_id):
        self.start_time = time.time()
        self.command = command
        self.session_id = session_id
        self.system_info = {"uid": os.environ["USER"]}
        self.env = (
            {k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)},
        )
        self.gpu = None
        self.unaggregated_samples = []
        self.stdout = ""
        self.stderr = ""
        self.number = 0
        self.get_system_info()

    def get_system_info(self):
        """Gathers system information related to CPU, GPU, memory, and environment variables."""
        self.system_info["memory_total"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf(
            "SC_PHYS_PAGES"
        )
        self.system_info["cpu_total"] = os.sysconf("SC_NPROCESSORS_CONF")

        # GPU information
        if shutil.which("nvidia-smi"):
            try:
                gpu_info = (
                    subprocess.check_output(
                        [
                            "nvidia-smi",
                            "--query-gpu=index,name,pci.bus_id,driver_version,memory.total,compute_mode",
                            "--format=csv",
                        ],
                        text=True,
                    )
                    .strip()
                    .split("\n")[1:]
                )
                self.gpus = [
                    dict(zip(gpu_info[0].split(", "), gpu.split(", ")))
                    for gpu in gpu_info[1:]
                ]
            except subprocess.CalledProcessError:
                self.gpus = "Failed to query GPU info"

    def collect_sample(self):
        process_data = {}
        try:
            output = subprocess.check_output(["ps", "-s", str(self.session_id), "-o", "pid,pcpu,pmem,rss,vsz,etime,cmd"], text=True)
            for line in output.splitlines()[1:]:
                if line:
                    pid, pcpu, pmem, rss, vsz, etime, cmd = line.split(maxsplit=6)
                    process_data[pid] = {
                        # %CPU
                        'pcpu': float(pcpu),
                        # %MEM
                        'pmem': float(pmem),
                        # Memory Resident Set Size
                        'rss': int(rss),
                        # Virtual Memory size
                        'vsz': int(vsz),
                    }
        except subprocess.CalledProcessError:
            process_data['error'] = "Failed to query process data"

        self.unaggregated_samples.append(process_data)

    def aggregate_samples(self):
        max_values = {}
        for sample in self.unaggregated_samples:
            for pid, metrics in sample.items():
                if pid not in max_values:
                    max_values[pid] = metrics.copy()  # Make a copy of the metrics for the first entry
                else:
                    # Update each metric to the maximum found so far
                    for key in metrics:
                        max_values[pid][key] = max(max_values[pid][key], metrics[key])

        return max_values

    def __repr__(self):
        return json.dumps(
            {
                "Command": self.command,
                "System": self.system_info,
                "ENV": self.env,
                "GPU": self.gpu,
                "STDOUT": self.stdout,
                "STDERR": self.stderr,
            }
        )


@dataclass
class SubReport:
    """Group of aggregated statestics on a session"""

    number: int = 0
    pids_dummy: list = field(default_factory=lambda: defaultdict(list))
    session_data = None
    elapsed_time = None

    def serialize(self):
        return {
            "Subreport Number": self.number,
            "Number": self.number,
            "Elapsed Time": self.elapsed_time,
            "Session Data": self.session_data,
        }


def main():
    """A wrapper to execute a command, monitor and log the process details."""
    parser = argparse.ArgumentParser(
        description="A process wrapper script that monitors the execution of a command."
    )
    parser.add_argument("command", help="The command to execute.")
    parser.add_argument("arguments", nargs="*", help="Arguments for the command.")
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=1.0,
        help="Interval in seconds between status checks of the running process.",
    )
    parser.add_argument(
        "--stats_log_path",
        type=str,
        default="TODO_BETTER.stats.json",
    )
    parser.add_argument(
        "--report-interval",
        type=float,
        default=60.0,
        help="Interval in seconds at which to report aggregated data.",
    )
    args = parser.parse_args()

    try:
        process = subprocess.Popen(
            [str(args.command)] + args.arguments.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        session_id = os.getsid(process.pid)  # Get session ID of the new process
        report = Report(args.command, session_id)

        while True:
            elapsed_time = time.time() - report.start_time
            report.collect_sample()
            if elapsed_time >= (report.number + 1) * args.report_interval:
                aggregated = report.aggregate_samples()
                print(aggregated)
                with open(args.stats_log_path, "a") as resource_statistics_log:
                    aggregated["elapsed_time"] = elapsed_time
                    resource_statistics_log.write(json.dumps(aggregated))
                report.number += 1

            if process.poll() is not None:  # the passthrough command has finished
                break
            time.sleep(args.sample_interval)

        stdout, stderr = process.communicate()
        report.end_time = time.time()
        report.run_time_seconds = f"{report.end_time - report.start_time}"
        report.stdout = stdout.decode()
        report.stderr = stderr.decode()
        pprint.pprint(report, width=120)

    except Exception as e:
        print(f"Failed to execute command: {str(e)}")


if __name__ == "__main__":
    main()

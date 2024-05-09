#!/usr/bin/env python3
import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, DefaultDict, Dict, List, Optional, TextIO, Tuple, Union

__version__ = "0.0.1"
ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")


class Report:
    """Top level report"""

    start_time: float
    command: str
    session_id: int
    gpus: Optional[list]
    unaggregated_samples: List[Dict]
    number: int
    system_info: Dict[str, Any]  # Use more specific types if possible

    def __init__(self, command: str, session_id: int) -> None:
        self.start_time = time.time()
        self.command = command
        self.session_id = session_id
        self.gpus = []
        self.unaggregated_samples = []
        self.number = 0
        self.system_info = {}

    def collect_environment(self):
        self.env = (
            {k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)},
        )

    def get_system_info(self):
        """Gathers system information related to CPU, GPU, memory, and environment variables."""
        self.system_info["uid"] = os.environ["USER"]
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
                self.gpus = ["Failed to query GPU info"]

    def collect_sample(self):
        process_data = {}
        try:
            output = subprocess.check_output(
                [
                    "ps",
                    "-s",
                    str(self.session_id),
                    "-o",
                    "pid,pcpu,pmem,rss,vsz,etime,cmd",
                ],
                text=True,
            )
            for line in output.splitlines()[1:]:
                if line:
                    pid, pcpu, pmem, rss, vsz, etime, cmd = line.split(maxsplit=6)
                    process_data[pid] = {
                        # %CPU
                        "pcpu": float(pcpu),
                        # %MEM
                        "pmem": float(pmem),
                        # Memory Resident Set Size
                        "rss": int(rss),
                        # Virtual Memory size
                        "vsz": int(vsz),
                    }
        except subprocess.CalledProcessError:
            process_data["error"] = "Failed to query process data"

        self.unaggregated_samples.append(process_data)

    def aggregate_samples(self):
        max_values = {}
        while self.unaggregated_samples:
            sample = self.unaggregated_samples.pop()
            for pid, metrics in sample.items():
                if pid not in max_values:
                    max_values[
                        pid
                    ] = metrics.copy()  # Make a copy of the metrics for the first entry
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
                "GPU": self.gpus,
            }
        )


@dataclass
class SubReport:
    """Group of aggregated statestics on a session"""

    number: int = 0

    pids_dummy: DefaultDict[Any, List[Any]] = field(
        default_factory=lambda: defaultdict(list)
    )
    session_data = None
    elapsed_time = None

    def serialize(self):
        return {
            "Subreport Number": self.number,
            "Number": self.number,
            "Elapsed Time": self.elapsed_time,
            "Session Data": self.session_data,
        }


def create_and_parse_args():
    parser = argparse.ArgumentParser(
        description="Gathers metrics on a command and all its child processes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("command", help="The command to execute.")
    parser.add_argument("arguments", nargs="*", help="Arguments for the command.")
    parser.add_argument(
        "-p",
        "--output-prefix",
        type=str,
        default=os.getenv(
            "DUCT_OUTPUT_PREFIX", ".duct/logs/{datetime_filesafe}-{pid}_"
        ),
        help="File string format to be used as a prefix for the files -- the captured "
        "stdout and stderr and the resource usage logs. The understood variables are "
        "{datetime}, {datetime_filesafe}, and {pid}. "
        "Leading directories will be created if they do not exist. "
        "You can also provide value via DUCT_OUTPUT_PREFIX env variable. ",
    )
    parser.add_argument(
        "--sample-interval",
        "--s-i",
        type=float,
        default=float(os.getenv("DUCT_SAMPLE_INTERVAL", "1.0")),
        help="Interval in seconds between status checks of the running process.",
    )
    parser.add_argument(
        "--report-interval",
        "--r-i",
        type=float,
        default=float(os.getenv("DUCT_REPORT_INTERVAL", "60.0")),
        help="Interval in seconds at which to report aggregated data.",
    )
    parser.add_argument(
        "-c",
        "--capture-outputs",
        type=str,
        default=os.getenv("DUCT_CAPTURE_OUTPUTS", "all"),
        choices=["all", "none", "stdout", "stderr"],
        help="Record stdout, stderr, all, or none to log files. "
        "You can also provide value via DUCT_CAPTURE_OUTPUTS env variable.",
    )
    parser.add_argument(
        "-o",
        "--outputs",
        type=str,
        default="all",
        choices=["all", "none", "stdout", "stderr"],
        help="Print stdout, stderr, all, or none to stdout/stderr respectively.",
    )
    parser.add_argument(
        "-t",
        "--record-types",
        type=str,
        default="all",
        choices=["all", "system-summary", "processes-samples"],
        help="Record system-summary, processes-samples, or all",
    )
    return parser.parse_args()


class TailPipe:
    """TailPipe simultaneously streams to standard output (stdout) and a specified file."""

    def __init__(self, file_path, buffer):
        self.file_path = file_path
        self.has_run = False
        self.buffer = buffer

    def start(self):
        Path(self.file_path).touch()
        self.stop_event = threading.Event()
        self.infile = open(self.file_path, "rb")
        self.thread = threading.Thread(target=self._tail, daemon=True)
        self.thread.start()

    def fileno(self):
        return self.infile.fileno()

    def _tail(self):
        while not self.stop_event.is_set():
            data = self.infile.read()
            if data:
                self.buffer.write(data)
            # Do we really need this? TODO should be configurable
            time.sleep(0.01)

        # After stop event, collect and passthrough data one last time
        data = self.infile.read()
        if data:
            self.buffer.write(data)

    def close(self):
        self.stop_event.set()
        self.thread.join()
        self.infile.close()


def monitor_process(
    stdout, stderr, report, process, report_interval, sample_interval, output_prefix
):
    while True:
        if process.poll() is not None:  # the passthrough command has finished
            if hasattr(stdout, "close"):
                stdout.close()
            if hasattr(stderr, "close"):
                stderr.close()
            break

        elapsed_time = time.time() - report.start_time
        resource_stats_log_path = "{output_prefix}usage.json"
        if elapsed_time >= (report.number + 1) * report_interval:
            aggregated = report.aggregate_samples()
            for pid, pinfo in aggregated.items():
                with open(
                    resource_stats_log_path.format(
                        output_prefix=output_prefix, pid=pid
                    ),
                    "a",
                ) as resource_statistics_log:
                    pinfo["elapsed_time"] = elapsed_time
                    resource_statistics_log.write(json.dumps(aggregated))
            report.number += 1
        time.sleep(sample_interval)


def prepare_outputs(
    capture_outputs: str, outputs: str, output_prefix: str
) -> Tuple[Union[TextIO, TailPipe, int], Union[TextIO, TailPipe, int]]:
    stdout: Union[TextIO, TailPipe, int]
    stderr: Union[TextIO, TailPipe, int]

    # Code remains the same
    if capture_outputs in ["all", "stdout"] and outputs in ["all", "stdout"]:
        stdout = TailPipe(f"{output_prefix}stdout", buffer=sys.stdout.buffer)
    elif capture_outputs in ["all", "stdout"] and outputs in ["none", "stderr"]:
        stdout = open(f"{output_prefix}stdout", "w")
    elif capture_outputs in ["none", "stderr"] and outputs in ["all", "stdout"]:
        stdout = subprocess.PIPE
    else:
        stdout = subprocess.DEVNULL

    if capture_outputs in ["all", "stderr"] and outputs in ["all", "stderr"]:
        stderr = TailPipe(f"{output_prefix}stderr", buffer=sys.stderr.buffer)
        stderr.start()
    elif capture_outputs in ["all", "stderr"] and outputs in ["none", "stdout"]:
        stderr = open(f"{output_prefix}stderr", "w")
    elif capture_outputs in ["none", "stdout"] and outputs in ["all", "stderr"]:
        stderr = subprocess.PIPE
    else:
        stderr = subprocess.DEVNULL
    return stdout, stderr


def format_output_prefix(output_prefix_template: str) -> str:
    datenow = datetime.now()
    f_kwargs = {
        # 'pure' iso 8601 does not make good filenames
        "datetime": datenow.isoformat(),
        "datetime_filesafe": datenow.strftime("%Y-%m-%dT%H-%M-%S"),
        "pid": os.getpid(),
    }
    return output_prefix_template.format(**f_kwargs)


def ensure_directories(path: str) -> None:
    if path.endswith(os.sep):  # If it ends in "/" (for linux) treat as a dir
        os.makedirs(path, exist_ok=True)
    else:
        # Path does not end with a separator, treat the last part as a filename
        directory = os.path.dirname(path)
        if directory:  # If there's a directory part, create it
            os.makedirs(directory, exist_ok=True)


def main():
    """A wrapper to execute a command, monitor and log the process details."""
    args = create_and_parse_args()
    formatted_output_prefix = format_output_prefix(args.output_prefix)
    ensure_directories(formatted_output_prefix)
    stdout, stderr = prepare_outputs(
        args.capture_outputs, args.outputs, formatted_output_prefix
    )
    with open(stdout.file_path, "wb") as write_out:
        process = subprocess.Popen(
            [str(args.command)] + args.arguments,
            stdout=write_out,
            stderr=stderr,
            preexec_fn=os.setsid,
        )
        stdout.start()
        session_id = os.getsid(process.pid)  # Get session ID of the new process
        report = Report(args.command, session_id)
        report.collect_environment()
        report.get_system_info()
        process.wait()
        stdout.close()

    if args.record_types in ["all", "processes-samples"]:
        monitoring_args = [
            stdout,
            stderr,
            report,
            process,
            args.report_interval,
            args.sample_interval,
            formatted_output_prefix,
        ]
        monitoring_thread = threading.Thread(
            target=monitor_process, args=monitoring_args
        )
        monitoring_thread.start()
        monitoring_thread.join()

    if args.record_types in ["all", "system-summary"]:
        system_info_path = f"{formatted_output_prefix}info.json"
        with open(system_info_path, "a") as system_logs:
            report.end_time = time.time()
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            report.get_system_info()
            system_logs.write(str(report))


if __name__ == "__main__":
    main()

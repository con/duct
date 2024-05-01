#!/usr/bin/env python3
import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
import errno
import json
import os
import pprint
import shutil
import subprocess
import sys
import threading
import time

__version__ = "0.0.1"
ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")


class Report:
    """Top level report"""

    def __init__(self, command, session_id):
        self.start_time = time.time()
        self.command = command
        self.session_id = session_id
        self.gpu = None
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
                self.gpus = "Failed to query GPU info"

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
                "GPU": self.gpu,
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


class TeeStream:
    """TeeStream simultaneously streams to standard output (stdout) and a specified file."""

    def __init__(self, file_path):
        self.file = open(file_path, "w")
        (
            self.listener_fd,
            self.writer_fd,
        ) = os.openpty()  # Use pseudo-terminal to simulate terminal behavior

    def fileno(self):
        """Return the file descriptor to be used by subprocess as stdout/stderr."""
        return self.listener_fd

    def start(self):
        """Start a thread to read from the main_fd and write to stdout and the file."""
        thread = threading.Thread(target=self._redirect_output, daemon=True)
        thread.start()

    def _redirect_output(self):
        with os.fdopen(self.listener_fd, "rb", buffering=0) as stream:
            while True:
                try:
                    data = stream.read(1024)
                except OSError as e:
                    if e.errno == errno.EIO:  # The file has been closed
                        break
                    else:
                        raise
                if not data:  # Still open, but no new data to write
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
                self.file.write(
                    data.decode("utf-8", "replace")
                )  # Handling decoding errors
                self.file.flush()

    def close(self):
        """Close the slave fd and the file when done."""
        os.close(self.listener_fd)
        self.file.close()


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


def prepare_outputs(capture_outputs, outputs, output_prefix):
    if capture_outputs in ["all", "stdout"] and outputs in ["all", "stdout"]:
        stdout = TeeStream(f"{output_prefix}stdout")
        stdout.start()
    elif capture_outputs in ["all", "stdout"] and outputs in ["none", "stderr"]:
        stdout = open(f"{output_prefix}stdout")
    elif capture_outputs in ["none", "stderr"] and outputs in ["all", "stdout"]:
        stdout = subprocess.PIPE
    else:
        stdout = subprocess.DEVNULL

    if capture_outputs in ["all", "stderr"] and outputs in ["all", "stderr"]:
        stderr = TeeStream(f"{output_prefix}stderr")
        stderr.start()
    elif capture_outputs in ["all", "stderr"] and outputs in ["none", "stdout"]:
        stderr = open(f"{output_prefix}stderr")
    elif capture_outputs in ["none", "stdout"] and outputs in [
        "all",
        "stderr",
    ]:
        stderr = subprocess.PIPE
    else:
        stderr = subprocess.DEVNULL
    return stdout, stderr


def format_output_prefix(output_prefix_template):
    datenow = datetime.now()
    f_kwargs = {
        # 'pure' iso 8601 does not make good filenames
        "datetime": datenow.isoformat(),
        "datetime_filesafe": datenow.strftime("%Y-%m-%dT%H-%M-%S"),
        "pid": os.getpid(),
    }
    return output_prefix_template.format(**f_kwargs)


def ensure_directories(path):
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
    process = subprocess.Popen(
        [str(args.command)] + args.arguments,
        stdout=stdout,
        stderr=stderr,
        preexec_fn=os.setsid,
    )
    session_id = os.getsid(process.pid)  # Get session ID of the new process
    report = Report(args.command, session_id)
    report.collect_environment()
    report.get_system_info()

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
    pprint.pprint(report, width=120)


if __name__ == "__main__":
    main()

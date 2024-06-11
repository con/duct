#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import IO, Any, TextIO

__version__ = "0.0.1"
ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"  # Reset to default color
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class Report:
    """Top level report"""

    def __init__(
        self,
        command: str,
        arguments: list[str],
        session_id: int | None,
        output_prefix: str,
        process: subprocess.Popen,
        datetime_filesafe: str,
    ) -> None:
        self.start_time = time.time()
        self._command = command
        self.arguments = arguments
        self.session_id = session_id
        self.gpus: list | None = []
        self.env: dict[str, str] | None = None
        self.number = 0
        self.system_info: dict[str, Any] = {}  # Use more specific types if possible
        self.output_prefix = output_prefix
        self.max_values: dict[str, dict[str, Any]] = defaultdict(dict)
        self.process = process
        self._sample: dict[str, dict[str, Any]] = defaultdict(dict)
        self.datetime_filesafe = datetime_filesafe
        self.end_time: float | None = None
        self.run_time_seconds: str | None = None

    @property
    def command(self) -> str:
        return " ".join([self._command] + self.arguments)

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    def collect_environment(self) -> None:
        self.env = {k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)}

    def get_system_info(self) -> None:
        """Gathers system information related to CPU, GPU, memory, and environment variables."""
        self.system_info["uid"] = os.environ.get("USER")
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

    def calculate_total_usage(
        self, sample: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        pmem = 0.0
        pcpu = 0.0
        for _pid, pinfo in sample.items():
            pmem += pinfo["pmem"]
            pcpu += pinfo["pcpu"]
        totals = {"totals": {"pmem": pmem, "pcpu": pcpu}}
        return totals

    @staticmethod
    def update_max_resources(
        maxes: dict[str, dict[str, Any]], sample: dict[str, dict[str, Any]]
    ) -> None:
        for pid in sample:
            if pid in maxes:
                for key, value in sample[pid].items():
                    maxes[pid][key] = max(maxes[pid].get(key, value), value)
            else:
                maxes[pid] = sample[pid].copy()

    def collect_sample(self) -> dict[str, dict[str, int | float | str]]:
        assert self.session_id is not None
        process_data: dict[str, dict[str, int | float | str]] = {}
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
                        "timestamp": datetime.now().astimezone().isoformat(),
                    }
        except subprocess.CalledProcessError:
            pass
        return process_data

    def write_pid_samples(self) -> None:
        resource_stats_log_path = f"{self.output_prefix}usage.json"
        with open(resource_stats_log_path, "a") as resource_statistics_log:
            resource_statistics_log.write(json.dumps(self._sample) + "\n")

    def print_max_values(self) -> None:
        for pid, maxes in self.max_values.items():
            print(f"PID {pid} Maximum Values: {maxes}")

    def finalize(self) -> None:
        if not self.process.returncode:
            print(Colors.OKGREEN)
        else:
            print(Colors.FAIL)
        print(f"Exit Code: {self.process.returncode}")
        print(f"{Colors.OKCYAN}Command: {self.command}")
        print(f"Log files location: {self.output_prefix}")
        print(f"Wall Clock Time: {self.elapsed_time:.3f} sec")
        print(
            f"Memory Peak Usage: {self.max_values.get('totals', {}).get('pmem', 'unknown')}%"
        )
        print(
            f"CPU Peak Usage: {self.max_values.get('totals', {}).get('pcpu', 'unknown')}%"
        )

    def dump_json(self) -> str:
        return json.dumps(
            {
                "command": self.command,
                "system": self.system_info,
                "env": self.env,
                "gpu": self.gpus,
                "duct_version": __version__,
            }
        )


@dataclass
class Arguments:
    command: str
    command_args: list[str]
    output_prefix: str
    sample_interval: float
    report_interval: float
    capture_outputs: str
    outputs: str
    record_types: str

    @classmethod
    def from_argv(cls) -> Arguments:
        parser = argparse.ArgumentParser(
            description="Gathers metrics on a command and all its child processes.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "command",
            metavar="command [command_args ...]",
            help="The command to execute, along with its arguments.",
        )
        parser.add_argument(
            "--version", action="version", version=f"%(prog)s {__version__}"
        )
        parser.add_argument(
            "command_args", nargs=argparse.REMAINDER, help="Arguments for the command."
        )
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
            help="Interval in seconds between status checks of the running process. "
            "Sample interval should be larger than the runtime of the process or `duct` may "
            "underreport the number of processes started.",
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
        args = parser.parse_args()
        return cls(
            command=args.command,
            command_args=args.command_args,
            output_prefix=args.output_prefix,
            sample_interval=args.sample_interval,
            report_interval=args.report_interval,
            capture_outputs=args.capture_outputs,
            outputs=args.outputs,
            record_types=args.record_types,
        )


def monitor_process(
    report: Report,
    process: subprocess.Popen,
    report_interval: float,
    sample_interval: float,
    stop_event: threading.Event,
) -> None:
    while not stop_event.wait(timeout=sample_interval):
        while True:
            if process.poll() is not None:  # the passthrough command has finished
                break
            # print(f"Resource stats log path: {resource_stats_log_path}")
            sample = report.collect_sample()
            totals = report.calculate_total_usage(sample)
            report.update_max_resources(sample, totals)
            report.update_max_resources(report._sample, sample)
            if report.elapsed_time >= report.number * report_interval:
                report.write_pid_samples()
                report.update_max_resources(report.max_values, report._sample)
                report._sample = defaultdict(dict)  # Reset sample
                report.number += 1


class TailPipe:
    """TailPipe simultaneously streams to an output stream (stdout or stderr) and a specified file."""

    TAIL_CYCLE_TIME = 0.01

    def __init__(self, file_path: str, buffer: IO[bytes]) -> None:
        self.file_path = file_path
        self.buffer = buffer
        self.stop_event: threading.Event | None = None
        self.infile: IO[bytes] | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        Path(self.file_path).touch()
        self.stop_event = threading.Event()
        self.infile = open(self.file_path, "rb")
        self.thread = threading.Thread(target=self._tail, daemon=True)
        self.thread.start()

    def fileno(self) -> int:
        assert self.infile is not None
        return self.infile.fileno()

    def _catch_up(self) -> None:
        assert self.infile is not None
        data = self.infile.read()
        if data:
            self.buffer.write(data)
            self.buffer.flush()

    def _tail(self) -> None:
        assert self.stop_event is not None
        try:
            while not self.stop_event.is_set():
                self._catch_up()
                time.sleep(TailPipe.TAIL_CYCLE_TIME)
            # After stop event, collect and passthrough data one last time
            self._catch_up()
        except Exception:
            raise
        finally:
            self.buffer.flush()

    def close(self) -> None:
        assert self.stop_event is not None
        assert self.thread is not None
        assert self.infile is not None
        self.stop_event.set()
        self.thread.join()
        self.infile.close()


def prepare_outputs(
    capture_outputs: str, outputs: str, output_prefix: str
) -> tuple[TextIO | TailPipe | int | None, TextIO | TailPipe | int | None]:
    stdout: TextIO | TailPipe | int | None
    stderr: TextIO | TailPipe | int | None

    if capture_outputs in ["all", "stdout"] and outputs in ["all", "stdout"]:
        stdout = TailPipe(f"{output_prefix}stdout", buffer=sys.stdout.buffer)
        stdout.start()
    elif capture_outputs in ["all", "stdout"] and outputs in ["none", "stderr"]:
        stdout = open(f"{output_prefix}stdout", "w")
    elif capture_outputs in ["none", "stderr"] and outputs in ["all", "stdout"]:
        stdout = None
    elif capture_outputs in ["none", "stderr"] and outputs in ["none", "stderr"]:
        stdout = subprocess.DEVNULL

    if capture_outputs in ["all", "stderr"] and outputs in ["all", "stderr"]:
        stderr = TailPipe(f"{output_prefix}stderr", buffer=sys.stderr.buffer)
        stderr.start()
    elif capture_outputs in ["all", "stderr"] and outputs in ["none", "stdout"]:
        stderr = open(f"{output_prefix}stderr", "w")
    elif capture_outputs in ["none", "stdout"] and outputs in ["all", "stderr"]:
        stderr = None
    elif capture_outputs in ["none", "stdout"] and outputs in ["none", "stdout"]:
        stderr = subprocess.DEVNULL
    return stdout, stderr


def safe_close_files(file_list: Iterable[Any]) -> None:
    for f in file_list:
        try:
            f.close()
        except Exception:
            pass


def ensure_directories(path: str) -> None:
    if path.endswith(os.sep):  # If it ends in "/" (for linux) treat as a dir
        os.makedirs(path, exist_ok=True)
    else:
        # Path does not end with a separator, treat the last part as a filename
        directory = os.path.dirname(path)
        if directory:  # If there's a directory part, create it
            os.makedirs(directory, exist_ok=True)


def main() -> None:
    args = Arguments.from_argv()
    execute(args)


def execute(args: Arguments) -> None:
    """A wrapper to execute a command, monitor and log the process details."""
    datetime_filesafe = datetime.now().strftime("%Y.%m.%dT%H.%M.%S")
    duct_pid = os.getpid()
    formatted_output_prefix = args.output_prefix.format(
        datetime_filesafe=datetime_filesafe, pid=duct_pid
    )
    ensure_directories(formatted_output_prefix)
    stdout, stderr = prepare_outputs(
        args.capture_outputs, args.outputs, formatted_output_prefix
    )
    stdout_file: TextIO | IO[bytes] | int | None
    if isinstance(stdout, TailPipe):
        stdout_file = open(stdout.file_path, "wb")
    else:
        stdout_file = stdout
    stderr_file: TextIO | IO[bytes] | int | None
    if isinstance(stderr, TailPipe):
        stderr_file = open(stderr.file_path, "wb")
    else:
        stderr_file = stderr

    full_command = " ".join([str(args.command)] + args.command_args)
    print(f"{Colors.OKCYAN}duct is executing {full_command}...")
    print(f"Log files will be written to {formatted_output_prefix}{Colors.ENDC}")
    process = subprocess.Popen(
        [str(args.command)] + args.command_args,
        stdout=stdout_file,
        stderr=stderr_file,
        preexec_fn=os.setsid,
    )
    try:
        session_id = os.getsid(process.pid)  # Get session ID of the new process
    except ProcessLookupError:  # process has already finished
        session_id = None

    report = Report(
        args.command,
        args.command_args,
        session_id,
        formatted_output_prefix,
        process,
        datetime_filesafe,
    )
    stop_event = threading.Event()
    if args.record_types in ["all", "processes-samples"]:
        monitoring_args = [
            report,
            process,
            args.report_interval,
            args.sample_interval,
            stop_event,
        ]
        monitoring_thread = threading.Thread(
            target=monitor_process, args=monitoring_args
        )
        monitoring_thread.start()
    else:
        monitoring_thread = None

    if args.record_types in ["all", "system-summary"]:
        report.collect_environment()
        report.get_system_info()
        system_info_path = f"{args.output_prefix}info.json".format(
            pid=duct_pid, datetime_filesafe=datetime_filesafe
        )
        with open(system_info_path, "a") as system_logs:
            report.end_time = time.time()
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            report.get_system_info()
            system_logs.write(report.dump_json())

    process.wait()
    stop_event.set()
    if monitoring_thread is not None:
        monitoring_thread.join()

    # If we have any extra samples that haven't been written yet, do it now
    if report._sample:
        report.update_max_resources(report.max_values, report._sample)
        report.write_pid_samples()
    report.process = process
    report.finalize()
    safe_close_files([stdout_file, stdout, stderr_file, stderr])


if __name__ == "__main__":
    main()

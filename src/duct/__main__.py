#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import IO, Any, Generator, TextIO
from . import __version__

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


class Outputs(str, Enum):
    ALL = "all"
    NONE = "none"
    STDOUT = "stdout"
    STDERR = "stderr"

    def __str__(self) -> str:
        return self.value

    def has_stdout(self) -> bool:
        return self is Outputs.ALL or self is Outputs.STDOUT

    def has_stderr(self) -> bool:
        return self is Outputs.ALL or self is Outputs.STDERR


class RecordTypes(str, Enum):
    ALL = "all"
    SYSTEM_SUMMARY = "system-summary"
    PROCESSES_SAMPLES = "processes-samples"

    def __str__(self) -> str:
        return self.value

    def has_system_summary(self) -> bool:
        return self is RecordTypes.ALL or self is RecordTypes.SYSTEM_SUMMARY

    def has_processes_samples(self) -> bool:
        return self is RecordTypes.ALL or self is RecordTypes.PROCESSES_SAMPLES


@dataclass
class SystemInfo:
    uid: str | None
    memory_total: int
    cpu_total: int


@dataclass
class ProcessStats:
    # %CPU
    pcpu: float
    # %MEM
    pmem: float
    # Memory Resident Set Size
    rss: int
    # Virtual Memory size
    vsz: int
    timestamp: str

    def max(self, other: ProcessStats) -> ProcessStats:
        return ProcessStats(
            pcpu=max(self.pcpu, other.pcpu),
            pmem=max(self.pmem, other.pmem),
            rss=max(self.rss, other.rss),
            vsz=max(self.vsz, other.vsz),
            timestamp=max(self.timestamp, other.timestamp),
        )


@dataclass
class Suffix:
    stdout: str = "stdout"
    stderr: str = "stderr"
    usage: str = "usage.json"
    info: str = "info.json"

    def __iter__(self) -> Generator:
        for each in fields(self):
            yield each.name, getattr(self, each.name)


@dataclass
class LogPaths:
    stdout: str
    stderr: str
    usage: str
    info: str

    def __iter__(self) -> Generator:
        for each in fields(self):
            yield each.name, getattr(self, each.name)

    @property
    def prefix(self):
        return self._prefix

    @classmethod
    def create(cls, output_prefix, clobber, pid):
        datetime_filesafe = datetime.now().strftime("%Y.%m.%dT%H.%M.%S")
        formatted_prefix = output_prefix.format(pid, datetime_filesafe)
        create_dict = {name: f"{formatted_prefix}{suffix}" for name, suffix in Suffix()}
        conflicts = [path for path in create_dict.values() if Path(path).exists()]
        if conflicts and not clobber:
            raise FileExistsError(
                "Conflicting files:\n"
                + "\n".join(f"- {path}" for path in conflicts)
                + "\nUse --clobber to overrwrite conflicting files."
            )
        elif conflicts and clobber:
            [Path(path).unlink() for path in conflicts]

        if formatted_prefix.endswith(
            os.sep
        ):  # If it ends in "/" (for linux) treat as a dir
            os.makedirs(formatted_prefix, exist_ok=True)
        else:
            # Path does not end with a separator, treat the last part as a filename
            directory = os.path.dirname(formatted_prefix)
            if directory:
                os.makedirs(directory, exist_ok=True)
        new = cls(**create_dict)
        new._prefix = formatted_prefix
        return new


@dataclass
class Sample:
    stats: dict[int, ProcessStats] = field(default_factory=dict)
    total_pmem: float = 0.0
    total_pcpu: float = 0.0

    def add(self, pid: int, stats: ProcessStats) -> None:
        self.total_pmem += stats.pmem
        self.total_pcpu += stats.pcpu
        self.stats[pid] = stats

    def max(self: Sample, other: Sample) -> Sample:
        output = Sample()
        for pid in self.stats.keys() | other.stats.keys():
            if (mine := self.stats.get(pid)) is not None:
                if (theirs := other.stats.get(pid)) is not None:
                    output.add(pid, mine.max(theirs))
                else:
                    output.add(pid, mine)
            else:
                output.add(pid, other.stats[pid])
        output.total_pmem = max(self.total_pmem, other.total_pmem)
        output.total_pcpu = max(self.total_pcpu, other.total_pcpu)
        return output

    def for_json(self) -> dict[str, Any]:
        d = {str(pid): asdict(stats) for pid, stats in self.stats.items()}
        d["totals"] = {"pmem": self.total_pmem, "pcpu": self.total_pcpu}
        return d


class Report:
    """Top level report"""

    def __init__(
        self,
        command: str,
        arguments: list[str],
        session_id: int | None,
        process: subprocess.Popen,
        log_paths: LogPaths,
        clobber: bool = False,
    ) -> None:
        self.start_time = time.time()
        self._command = command
        self.arguments = arguments
        self.session_id = session_id
        self.gpus: list[dict[str, str]] | None = None
        self.env: dict[str, str] | None = None
        self.number = 0
        self.system_info: SystemInfo | None = None
        self.log_paths = log_paths
        self.max_values = Sample()
        self.process = process
        self._sample: Sample | None = None
        self.end_time: float | None = None
        self.run_time_seconds: str | None = None
        self._usage_file_exists: bool = False
        self.clobber = clobber

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
        uid = os.environ.get("USER")
        memory_total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        cpu_total = os.sysconf("SC_NPROCESSORS_CONF")
        self.system_info = SystemInfo(
            uid=uid, memory_total=memory_total, cpu_total=cpu_total
        )
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
                self.gpus = None

    def collect_sample(self) -> Sample:
        assert self.session_id is not None
        sample = Sample()
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
                    sample.add(
                        int(pid),
                        ProcessStats(
                            pcpu=float(pcpu),
                            pmem=float(pmem),
                            rss=int(rss),
                            vsz=int(vsz),
                            timestamp=datetime.now().astimezone().isoformat(),
                        ),
                    )
        except subprocess.CalledProcessError:
            pass
        return sample

    def write_pid_samples(self) -> None:
        assert self._sample is not None
        # First time only
        if not self._usage_file_exists:
            Path(self.log_paths.usage).touch()
            self._usage_file_exists = True

        with open(self.log_paths.usage, "a") as resource_statistics_log:
            resource_statistics_log.write(json.dumps(self._sample.for_json()) + "\n")

    def print_max_values(self) -> None:
        for pid, maxes in self.max_values.stats.items():
            print(f"PID {pid} Maximum Values: {asdict(maxes)}")

    def finalize(self) -> None:
        if not self.process.returncode:
            print(Colors.OKGREEN)
        else:
            print(Colors.FAIL)
        print(f"Exit Code: {self.process.returncode}")
        print(f"{Colors.OKCYAN}Command: {self.command}")
        print(f"Log files location: {self.log_paths.prefix}")
        print(f"Wall Clock Time: {self.elapsed_time:.3f} sec")
        print(
            "Memory Peak Usage:",
            f"{self.max_values.total_pmem}%" if self.max_values.stats else "unknown%",
        )
        print(
            "CPU Peak Usage:",
            f"{self.max_values.total_pcpu}%" if self.max_values.stats else "unknown%",
        )

    def dump_json(self) -> str:
        return json.dumps(
            {
                "command": self.command,
                "system": (
                    None if self.system_info is None else asdict(self.system_info)
                ),
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
    clobber: bool
    capture_outputs: Outputs
    outputs: Outputs
    record_types: RecordTypes

    @classmethod
    def from_argv(cls) -> Arguments:  # pragma: no cover
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
            "--clobber",
            action="store_true",
            help="Replace log files if they already exist.",
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
            default=os.getenv("DUCT_CAPTURE_OUTPUTS", "all"),
            choices=list(Outputs),
            type=Outputs,
            help="Record stdout, stderr, all, or none to log files. "
            "You can also provide value via DUCT_CAPTURE_OUTPUTS env variable.",
        )
        parser.add_argument(
            "-o",
            "--outputs",
            default="all",
            choices=list(Outputs),
            type=Outputs,
            help="Print stdout, stderr, all, or none to stdout/stderr respectively.",
        )
        parser.add_argument(
            "-t",
            "--record-types",
            default="all",
            choices=list(RecordTypes),
            type=RecordTypes,
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
            clobber=args.clobber,
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
            report._sample = (
                report._sample.max(sample) if report._sample is not None else sample
            )
            if report.elapsed_time >= report.number * report_interval:
                report.write_pid_samples()
                report.max_values = report.max_values.max(report._sample)
                report._sample = None  # Reset sample
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
    capture_outputs: Outputs,
    outputs: Outputs,
    log_paths: LogPaths,
) -> tuple[TextIO | TailPipe | int | None, TextIO | TailPipe | int | None]:
    stdout: TextIO | TailPipe | int | None
    stderr: TextIO | TailPipe | int | None

    if capture_outputs.has_stdout():
        Path(log_paths.stdout).touch()  # File must exist for TailPipe to read
        if outputs.has_stdout():
            stdout = TailPipe(log_paths.stdout, buffer=sys.stdout.buffer)
            stdout.start()
        else:
            stdout = open(log_paths.stdout, "w")
    elif outputs.has_stdout():
        stdout = None
    else:
        stdout = subprocess.DEVNULL

    if capture_outputs.has_stderr():
        Path(log_paths.stderr).touch()  # File must exist for TailPipe to read
        if outputs.has_stderr():
            stderr = TailPipe(log_paths.stderr, buffer=sys.stderr.buffer)
            stderr.start()
        else:
            stderr = open(log_paths.stderr, "w")
    elif outputs.has_stderr():
        stderr = None
    else:
        stderr = subprocess.DEVNULL
    return stdout, stderr


def safe_close_files(file_list: Iterable[Any]) -> None:
    for f in file_list:
        try:
            f.close()
        except Exception:
            pass


def main() -> None:
    args = Arguments.from_argv()
    execute(args)


def execute(args: Arguments) -> None:
    """A wrapper to execute a command, monitor and log the process details."""
    duct_pid = os.getpid()
    log_paths = LogPaths.create(args.output_prefix, pid=duct_pid, clobber=args.clobber)
    stdout, stderr = prepare_outputs(
        args.capture_outputs, args.outputs, log_paths, args.clobber
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
    print(f"Log files will be written to {log_paths.prefix}{Colors.ENDC}")
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
        process,
        log_paths,
        args.clobber,
    )
    stop_event = threading.Event()
    if args.record_types.has_processes_samples():
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

    if args.record_types.has_system_summary():
        report.collect_environment()
        report.get_system_info()
        with open(log_paths.info, "a") as system_logs:
            report.end_time = time.time()
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            report.get_system_info()
            system_logs.write(report.dump_json())

    process.wait()
    stop_event.set()
    if monitoring_thread is not None:
        monitoring_thread.join()

    # If we have any extra samples that haven't been written yet, do it now
    if report._sample is not None:
        report.max_values = report.max_values.max(report._sample)
        report.write_pid_samples()
    report.process = process
    report.finalize()
    safe_close_files([stdout_file, stdout, stderr_file, stderr])


if __name__ == "__main__":
    main()

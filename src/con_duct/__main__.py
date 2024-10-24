#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
import logging
import math
import os
import re
import shutil
import socket
import string
import subprocess
import sys
import textwrap
import threading
import time
from typing import IO, Any, Optional, TextIO

__version__ = "0.7.0"
__schema_version__ = "0.2.0"


lgr = logging.getLogger("con-duct")
DEFAULT_LOG_LEVEL = os.environ.get("DUCT_LOG_LEVEL", "INFO").upper()

ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")
SUFFIXES = {
    "stdout": "stdout",
    "stderr": "stderr",
    "usage": "usage.json",
    "info": "info.json",
}
EXECUTION_SUMMARY_FORMAT = (
    "Summary:\n"
    "Exit Code: {exit_code!E}\n"
    "Command: {command}\n"
    "Log files location: {logs_prefix}\n"
    "Wall Clock Time: {wall_clock_time:.3f} sec\n"
    "Memory Peak Usage (RSS): {peak_rss!S}\n"
    "Memory Average Usage (RSS): {average_rss!S}\n"
    "Virtual Memory Peak Usage (VSZ): {peak_vsz!S}\n"
    "Virtual Memory Average Usage (VSZ): {average_vsz!S}\n"
    "Memory Peak Percentage: {peak_pmem!N}%\n"
    "Memory Average Percentage: {average_pmem!N}%\n"
    "CPU Peak Usage: {peak_pcpu!N}%\n"
    "Average CPU Usage: {average_pcpu!N}%\n"
)


ABOUT_DUCT = """
duct is a lightweight wrapper that collects execution data for an arbitrary
command.  Execution data includes execution time, system information, and
resource usage statistics of the command and all its child processes. It is
intended to simplify the problem of recording the resources necessary to
execute a command, particularly in an HPC environment.

Resource usage is determined by polling (at a sample-interval).
During execution, duct produces a JSON lines (see https://jsonlines.org) file
with one data point recorded for each report (at a report-interval).

environment variables:
  Many duct options can be configured by environment variables (which are
  overridden by command line options).

  DUCT_LOG_LEVEL: see --log-level
  DUCT_OUTPUT_PREFIX: see --output-prefix
  DUCT_SUMMARY_FORMAT: see --summary-format
  DUCT_SAMPLE_INTERVAL: see --sample-interval
  DUCT_REPORT_INTERVAL: see --report-interval
  DUCT_CAPTURE_OUTPUTS: see --capture-outputs
"""


class CustomHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _fill_text(self, text: str, width: int, _indent: str) -> str:
        # Override _fill_text to respect the newlines and indentation in descriptions
        return "\n".join([textwrap.fill(line, width) for line in text.splitlines()])


def assert_num(*values: Any) -> None:
    for value in values:
        assert isinstance(value, (float, int))


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
    cpu_total: int
    memory_total: int
    hostname: str | None
    uid: int
    user: str | None


@dataclass
class ProcessStats:
    pcpu: float  # %CPU
    pmem: float  # %MEM
    rss: int  # Memory Resident Set Size in Bytes
    vsz: int  # Virtual Memory size in Bytes
    timestamp: str
    etime: str
    stat: Counter
    cmd: str

    def aggregate(self, other: ProcessStats) -> ProcessStats:
        cmd = self.cmd
        if self.cmd != other.cmd:
            lgr.debug(
                f"cmd has changed. Previous measurement was {self.cmd}, now {other.cmd}."
            )
            # Brackets indicate that the kernel has substituted an abbreviation.
            surrounded_by_brackets = r"^\[.+\]"
            if re.search(surrounded_by_brackets, self.cmd):
                lgr.debug(f"using {other.cmd}.")
                cmd = other.cmd
            lgr.debug(f"using {self.cmd}.")

        new_counter: Counter = Counter()
        new_counter.update(self.stat)
        new_counter.update(other.stat)
        return ProcessStats(
            pcpu=max(self.pcpu, other.pcpu),
            pmem=max(self.pmem, other.pmem),
            rss=max(self.rss, other.rss),
            vsz=max(self.vsz, other.vsz),
            timestamp=max(self.timestamp, other.timestamp),
            etime=other.etime,  # For the aggregate always take the latest
            stat=new_counter,
            cmd=cmd,
        )

    def for_json(self) -> dict:
        ret = asdict(self)
        ret["stat"] = dict(self.stat)
        return ret

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        assert_num(self.pcpu, self.pmem, self.rss, self.vsz)


@dataclass
class LogPaths:
    stdout: str
    stderr: str
    usage: str
    info: str
    prefix: str

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for name, path in asdict(self).items():
            if name != "prefix":
                yield name, path

    @classmethod
    def create(cls, output_prefix: str, pid: None | int = None) -> LogPaths:
        datetime_filesafe = datetime.now().strftime("%Y.%m.%dT%H.%M.%S")
        formatted_prefix = output_prefix.format(
            pid=pid, datetime_filesafe=datetime_filesafe
        )
        return cls(
            stdout=f"{formatted_prefix}{SUFFIXES['stdout']}",
            stderr=f"{formatted_prefix}{SUFFIXES['stderr']}",
            usage=f"{formatted_prefix}{SUFFIXES['usage']}",
            info=f"{formatted_prefix}{SUFFIXES['info']}",
            prefix=formatted_prefix,
        )

    def prepare_paths(self, clobber: bool, capture_outputs: Outputs) -> None:
        conflicts = [path for _name, path in self if os.path.exists(path)]
        if conflicts and not clobber:
            raise FileExistsError(
                "Conflicting files:\n"
                + "\n".join(f"- {path}" for path in conflicts)
                + "\nUse --clobber to overrwrite conflicting files."
            )

        if self.prefix.endswith(os.sep):  # If it ends in "/" (for linux) treat as a dir
            os.makedirs(self.prefix, exist_ok=True)
        else:
            # Path does not end with a separator, treat the last part as a filename
            directory = os.path.dirname(self.prefix)
            if directory:
                os.makedirs(directory, exist_ok=True)
        for name, path in self:
            if name == SUFFIXES["stdout"] and not capture_outputs.has_stdout():
                continue
            elif name == SUFFIXES["stderr"] and not capture_outputs.has_stderr():
                continue
            # usage and info should always be created
            open(path, "w").close()


@dataclass
class Averages:
    rss: Optional[float] = None
    vsz: Optional[float] = None
    pmem: Optional[float] = None
    pcpu: Optional[float] = None
    num_samples: int = 0

    def update(self: Averages, other: Sample) -> None:
        assert_num(other.total_rss, other.total_vsz, other.total_pmem, other.total_pcpu)
        if not self.num_samples:
            self.num_samples += 1
            self.rss = other.total_rss
            self.vsz = other.total_vsz
            self.pmem = other.total_pmem
            self.pcpu = other.total_pcpu
        else:
            assert self.rss is not None
            assert self.vsz is not None
            assert self.pmem is not None
            assert self.pcpu is not None
            assert other.total_rss is not None
            assert other.total_vsz is not None
            assert other.total_pmem is not None
            assert other.total_pcpu is not None
            self.num_samples += 1
            self.rss += (other.total_rss - self.rss) / self.num_samples
            self.vsz += (other.total_vsz - self.vsz) / self.num_samples
            self.pmem += (other.total_pmem - self.pmem) / self.num_samples
            self.pcpu += (other.total_pcpu - self.pcpu) / self.num_samples

    @classmethod
    def from_sample(cls, sample: Sample) -> Averages:
        assert_num(
            sample.total_rss, sample.total_vsz, sample.total_pmem, sample.total_pcpu
        )
        return cls(
            rss=sample.total_rss,
            vsz=sample.total_vsz,
            pmem=sample.total_pmem,
            pcpu=sample.total_pcpu,
            num_samples=1,
        )


@dataclass
class Sample:
    stats: dict[int, ProcessStats] = field(default_factory=dict)
    averages: Averages = field(default_factory=Averages)
    total_rss: Optional[int] = None
    total_vsz: Optional[int] = None
    total_pmem: Optional[float] = None
    total_pcpu: Optional[float] = None
    timestamp: str = ""  # TS of last sample collected

    def add_pid(self, pid: int, stats: ProcessStats) -> None:
        # We do not calculate averages when we add a pid because we require all pids first
        assert (
            self.stats.get(pid) is None
        )  # add_pid should only be called when pid not in Sample
        self.total_rss = (self.total_rss or 0) + stats.rss
        self.total_vsz = (self.total_vsz or 0) + stats.vsz
        self.total_pmem = (self.total_pmem or 0.0) + stats.pmem
        self.total_pcpu = (self.total_pcpu or 0.0) + stats.pcpu
        self.stats[pid] = stats
        self.timestamp = max(self.timestamp, stats.timestamp)

    def aggregate(self: Sample, other: Sample) -> Sample:
        output = Sample()
        for pid in self.stats.keys() | other.stats.keys():
            if (mine := self.stats.get(pid)) is not None:
                if (theirs := other.stats.get(pid)) is not None:
                    output.add_pid(pid, mine.aggregate(theirs))
                else:
                    output.add_pid(pid, mine)
            else:
                output.add_pid(pid, other.stats[pid])
        assert other.total_pmem is not None
        assert other.total_pcpu is not None
        assert other.total_rss is not None
        assert other.total_vsz is not None
        output.total_pmem = max(self.total_pmem or 0.0, other.total_pmem)
        output.total_pcpu = max(self.total_pcpu or 0.0, other.total_pcpu)
        output.total_rss = max(self.total_rss or 0, other.total_rss)
        output.total_vsz = max(self.total_vsz or 0, other.total_vsz)
        output.averages = self.averages
        output.averages.update(other)
        return output

    def for_json(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "num_samples": self.averages.num_samples,
            "processes": {
                str(pid): stats.for_json() for pid, stats in self.stats.items()
            },
            "totals": {  # total of all processes during this sample
                "pmem": self.total_pmem,
                "pcpu": self.total_pcpu,
                "rss": self.total_rss,
                "vsz": self.total_vsz,
            },
            "averages": asdict(self.averages) if self.averages.num_samples >= 1 else {},
        }
        return d


class Report:
    """Top level report"""

    def __init__(
        self,
        command: str,
        arguments: list[str],
        log_paths: LogPaths,
        summary_format: str,
        colors: bool = False,
        clobber: bool = False,
        process: subprocess.Popen | None = None,
    ) -> None:
        self._command = command
        self.arguments = arguments
        self.log_paths = log_paths
        self.summary_format: str = summary_format
        self.clobber = clobber
        self.colors = colors
        # Defaults to be set later
        self.start_time: float | None = None
        self.process = process
        self.session_id: int | None = None
        self.gpus: list[dict[str, str]] | None = None
        self.env: dict[str, str] | None = None
        self.number = 1
        self.system_info: SystemInfo | None = None
        self.full_run_stats = Sample()
        self.current_sample: Optional[Sample] = None
        self.end_time: float | None = None
        self.run_time_seconds: str | None = None

    @property
    def command(self) -> str:
        return " ".join([self._command] + self.arguments)

    @property
    def elapsed_time(self) -> float:
        assert self.start_time is not None
        return time.time() - self.start_time

    @property
    def wall_clock_time(self) -> Optional[float]:
        if self.start_time is None:
            return math.nan
        if self.end_time is None:
            # if no end_time -- must be still ongoing
            # Cannot happen ATM but could in "library mode" later
            return time.time() - self.start_time
        # we reached the end
        return self.end_time - self.start_time

    def collect_environment(self) -> None:
        self.env = {k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)}

    def get_system_info(self) -> None:
        """Gathers system information related to CPU, GPU, memory, and environment variables."""
        self.system_info = SystemInfo(
            cpu_total=os.sysconf("SC_NPROCESSORS_CONF"),
            memory_total=os.sysconf("SC_PAGESIZE") * os.sysconf("SC_PHYS_PAGES"),
            hostname=socket.gethostname(),
            uid=os.getuid(),
            user=os.environ.get("USER"),
        )
        # GPU information
        if shutil.which("nvidia-smi") is not None:
            lgr.debug("Checking NVIDIA GPU using nvidia-smi")
            try:
                out = subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-gpu=index,name,pci.bus_id,driver_version,memory.total,compute_mode",
                        "--format=csv",
                    ]
                )
            except subprocess.CalledProcessError as e:
                lgr.warning("Error collecting gpu information: %s", str(e))
                self.gpus = None
                return
            try:
                decoded = out.decode("utf-8")
                lines = decoded.strip().split("\n")
                _ = lines.pop(0)  # header
                self.gpus = []
                for line in lines:
                    cols = line.split(", ")
                    self.gpus.append(
                        {
                            "index": cols[0],
                            "name": cols[1],
                            "bus_id": cols[2],
                            "driver_version": cols[3],
                            "memory.total": cols[4],
                            "compute_mode": cols[5],
                        }
                    )
            except Exception as e:
                lgr.warning("Error parsing gpu information: %s", str(e))
                self.gpus = None

    def collect_sample(self) -> Optional[Sample]:
        assert self.session_id is not None
        sample = Sample()
        try:
            output = subprocess.check_output(
                [
                    "ps",
                    "-s",
                    str(self.session_id),
                    "-o",
                    "pid,pcpu,pmem,rss,vsz,etime,stat,cmd",
                ],
                text=True,
            )
            for line in output.splitlines()[1:]:
                if line:
                    pid, pcpu, pmem, rss_kib, vsz_kib, etime, stat, cmd = line.split(
                        maxsplit=7,
                    )
                    sample.add_pid(
                        int(pid),
                        ProcessStats(
                            pcpu=float(pcpu),
                            pmem=float(pmem),
                            rss=int(rss_kib) * 1024,
                            vsz=int(vsz_kib) * 1024,
                            timestamp=datetime.now().astimezone().isoformat(),
                            etime=etime,
                            stat=Counter([stat]),
                            cmd=cmd,
                        ),
                    )
        except subprocess.CalledProcessError as exc:  # when session_id has no processes
            lgr.debug("Error collecting sample: %s", str(exc))
            return None

        sample.averages = Averages.from_sample(sample)
        return sample

    def update_from_sample(self, sample: Sample) -> None:
        self.full_run_stats = self.full_run_stats.aggregate(sample)
        if self.current_sample is None:
            self.current_sample = Sample().aggregate(sample)
        else:
            assert self.current_sample.averages is not None
            self.current_sample = self.current_sample.aggregate(sample)
        assert self.current_sample is not None

    def write_subreport(self) -> None:
        assert self.current_sample is not None
        with open(self.log_paths.usage, "a") as resource_statistics_log:
            resource_statistics_log.write(
                json.dumps(self.current_sample.for_json()) + "\n"
            )

    @property
    def execution_summary(self) -> dict[str, Any]:
        # killed by a signal
        # https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_08_02
        if self.process and self.process.returncode < 0:
            self.process.returncode = 128 + abs(self.process.returncode)
        # prepare the base, but enrich if we did get process running
        return {
            "exit_code": self.process.returncode if self.process else None,
            "command": self.command,
            "logs_prefix": self.log_paths.prefix if self.log_paths else "",
            "wall_clock_time": self.wall_clock_time,
            "peak_rss": self.full_run_stats.total_rss,
            "average_rss": self.full_run_stats.averages.rss,
            "peak_vsz": self.full_run_stats.total_vsz,
            "average_vsz": self.full_run_stats.averages.vsz,
            "peak_pmem": self.full_run_stats.total_pmem,
            "average_pmem": self.full_run_stats.averages.pmem,
            "peak_pcpu": self.full_run_stats.total_pcpu,
            "average_pcpu": self.full_run_stats.averages.pcpu,
            "num_samples": self.full_run_stats.averages.num_samples,
            "num_reports": self.number,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

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
                "schema_version": __schema_version__,
                "execution_summary": self.execution_summary,
                "output_paths": asdict(self.log_paths),
            }
        )

    @property
    def execution_summary_formatted(self) -> str:
        formatter = SummaryFormatter(enable_colors=self.colors)
        return formatter.format(self.summary_format, **self.execution_summary)


class SummaryFormatter(string.Formatter):
    OK = "OK"
    NOK = "X"
    NONE = "-"
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[1;%dm"
    FILESIZE_SUFFIXES = (" kB", " MB", " GB", " TB", " PB", " EB", " ZB", " YB")

    def __init__(self, enable_colors: bool = False) -> None:
        self.enable_colors = enable_colors

    def naturalsize(
        self,
        value: float | str,
        format: str = "%.1f",  # noqa: A002
    ) -> str:
        """Format a number of bytes like a human readable decimal filesize (e.g. 10 kB).

        Examples:
            ```pycon
            >>> formatter = SummaryFormatter()
            >>> formatter.naturalsize(3000000)
            '3.0 MB'
            >>> formatter.naturalsize(3000, "%.3f")
            '2.930 kB'
            >>> formatter.naturalsize(10**28)
            '10000.0 YB'
            ```

        Args:
            value (int, float, str): Integer to convert.
            format (str): Custom formatter.

        Returns:
            str: Human readable representation of a filesize.
        """
        base = 1000
        bytes_ = float(value)
        abs_bytes = abs(bytes_)

        if abs_bytes == 1:
            return "%d Byte" % bytes_

        if abs_bytes < base:
            return "%d Bytes" % bytes_

        for i, _s in enumerate(self.FILESIZE_SUFFIXES):
            unit = base ** (i + 2)

            if abs_bytes < unit:
                break

        ret: str = format % (base * bytes_ / unit) + _s
        return ret

    def color_word(self, s: str, color: int) -> str:
        """Color `s` with `color`.

        Parameters
        ----------
        s : string
        color : int
            Code for color. If the value evaluates to false, the string will not be
            colored.
        enable_colors: boolean, optional

        Returns
        -------
        str
        """
        if color and self.enable_colors:
            return "%s%s%s" % (self.COLOR_SEQ % color, s, self.RESET_SEQ)
        return s

    def convert_field(self, value: str | None, conversion: str | None) -> Any:
        if conversion == "S":  # Human size
            if value is not None:
                return self.color_word(self.naturalsize(value), self.GREEN)
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "E":  # colored non-zero is bad
            return self.color_word(
                value if value is not None else self.NONE,
                self.RED if value or value is None else self.GREEN,
            )
        elif conversion == "X":  # colored truthy
            col = self.GREEN if value else self.RED
            return self.color_word(value if value is not None else self.NONE, col)
        elif conversion == "N":  # colored Red - if None
            if value is None:
                return self.color_word(self.NONE, self.RED)
            else:
                return self.color_word(value, self.GREEN)

        return super().convert_field(value, conversion)

    def format_field(self, value: Any, format_spec: str) -> Any:
        # TODO: move all the "coloring" into formatting, so we could correctly indent
        # given the format and only then color it up
        # print "> %r, %r" % (value, format_spec)
        if value is None:
            # TODO: could still use our formatter and make it red or smth like that
            return self.NONE
        try:
            return super().format_field(value, format_spec)
        except ValueError:
            lgr.warning(
                f"Value: {value} is invalid for format spec {format_spec}, falling back to `str`"
            )
            return str(value)


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
    summary_format: str
    colors: bool
    log_level: str
    quiet: bool

    def __post_init__(self) -> None:
        if self.report_interval < self.sample_interval:
            raise argparse.ArgumentError(
                None,
                "--report-interval must be greater than or equal to --sample-interval.",
            )

    @classmethod
    def from_argv(
        cls, cli_args: Optional[list[str]] = None, **cli_kwargs: Any
    ) -> Arguments:
        parser = argparse.ArgumentParser(
            allow_abbrev=False,
            description=ABOUT_DUCT,
            formatter_class=CustomHelpFormatter,
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
            "--summary-format",
            type=str,
            default=os.getenv("DUCT_SUMMARY_FORMAT", EXECUTION_SUMMARY_FORMAT),
            help="Output template to use when printing the summary following execution. "
            "Accepts custom conversion flags: "
            "!S: Converts filesizes to human readable units, green if measured, red if None. "
            "!E: Colors exit code, green if falsey, red if truthy, and red if None. "
            "!X: Colors green if truthy, red if falsey. "
            "!N: Colors green if not None, red if None",
        )
        parser.add_argument(
            "--colors",
            action="store_true",
            default=os.getenv("DUCT_COLORS", False),
            help="Use colors in duct output.",
        )
        parser.add_argument(
            "--clobber",
            action="store_true",
            help="Replace log files if they already exist.",
        )
        parser.add_argument(
            "-l",
            "--log_level",
            default=DEFAULT_LOG_LEVEL,
            choices=("NONE", "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
            help="Level of log output to stderr, use NONE to entirely disable.",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="[deprecated, use log level NONE] Disable duct logging output (to stderr)",
        )
        parser.add_argument(
            "--sample-interval",
            "--s-i",
            type=float,
            default=float(os.getenv("DUCT_SAMPLE_INTERVAL", "1.0")),
            help="Interval in seconds between status checks of the running process. "
            "Sample interval must be less than or equal to report interval, and it achieves the "
            "best results when sample is significantly less than the runtime of the process.",
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
        args = parser.parse_args(
            args=cli_args,
            namespace=cli_kwargs and argparse.Namespace(**cli_kwargs) or None,
        )
        return cls(
            command=args.command,
            command_args=args.command_args,
            output_prefix=args.output_prefix,
            sample_interval=args.sample_interval,
            report_interval=args.report_interval,
            capture_outputs=args.capture_outputs,
            outputs=args.outputs,
            record_types=args.record_types,
            summary_format=args.summary_format,
            clobber=args.clobber,
            colors=args.colors,
            log_level=args.log_level,
            quiet=args.quiet,
        )


def monitor_process(
    report: Report,
    process: subprocess.Popen,
    report_interval: float,
    sample_interval: float,
    stop_event: threading.Event,
) -> None:
    lgr.debug(
        "Starting monitoring of the process %s on sample interval %f for report interval %f",
        process,
        sample_interval,
        report_interval,
    )
    while True:
        if process.poll() is not None:
            lgr.debug(
                "Breaking out of the monitor since the passthrough command has finished"
            )
            break
        sample = report.collect_sample()
        # Report averages should be updated prior to sample aggregation
        if (
            sample is None
        ):  # passthrough has probably finished before sample could be collected
            if process.poll() is not None:
                lgr.debug(
                    "Breaking out of the monitor since the passthrough command has finished "
                    "before we could collect sample"
                )
                break
            # process is still running, but we could not collect sample
            continue
        report.update_from_sample(sample)
        if (
            report.start_time
            and report.elapsed_time >= (report.number - 1) * report_interval
        ):
            report.write_subreport()
            report.current_sample = None
            report.number += 1
        if stop_event.wait(timeout=sample_interval):
            lgr.debug("Breaking out because stop event was set")
            break


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
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        level=getattr(logging, DEFAULT_LOG_LEVEL),
    )
    args = Arguments.from_argv()
    sys.exit(execute(args))


def execute(args: Arguments) -> int:
    """A wrapper to execute a command, monitor and log the process details.

    Returns exit code of the executed process.
    """
    if args.log_level == "NONE" or args.quiet:
        lgr.disabled = True
    else:
        lgr.setLevel(args.log_level)
    log_paths = LogPaths.create(args.output_prefix, pid=os.getpid())
    log_paths.prepare_paths(args.clobber, args.capture_outputs)
    stdout, stderr = prepare_outputs(args.capture_outputs, args.outputs, log_paths)
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
    files_to_close = [stdout_file, stdout, stderr_file, stderr]

    report = Report(
        args.command,
        args.command_args,
        log_paths,
        args.summary_format,
        args.colors,
        args.clobber,
    )

    report.start_time = time.time()
    try:
        report.process = process = subprocess.Popen(
            [str(args.command)] + args.command_args,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )
    except FileNotFoundError:
        # We failed to execute due to file not found in PATH
        # We should remove log etc files since they are 0-sized
        # degenerates etc
        safe_close_files(files_to_close)
        for _, file_path in log_paths:
            if os.path.exists(file_path):
                assert os.stat(file_path).st_size == 0
                os.remove(file_path)
        # mimicking behavior of bash and zsh.
        print(f"{args.command}: command not found", file=sys.stderr)
        return 127  # seems what zsh and bash return then

    lgr.info("duct is executing %r...", full_command)
    lgr.info("Log files will be written to %s", log_paths.prefix)
    try:
        report.session_id = os.getsid(process.pid)  # Get session ID of the new process
    except ProcessLookupError:  # process has already finished
        # TODO: log this at least.
        pass
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
        env_thread = threading.Thread(target=report.collect_environment)
        env_thread.start()
        sys_info_thread = threading.Thread(target=report.get_system_info)
        sys_info_thread.start()
    else:
        env_thread, sys_info_thread = None, None

    process.wait()
    report.end_time = time.time()
    lgr.debug("Process ended, setting stop_event to stop monitoring thread")
    stop_event.set()
    if monitoring_thread is not None:
        lgr.debug("Waiting for monitoring thread to finish")
        monitoring_thread.join()
        lgr.debug("Monitoring thread finished")

    # If we have any extra samples that haven't been written yet, do it now
    if report.current_sample is not None:
        report.write_subreport()

    report.process = process
    if env_thread is not None:
        lgr.debug("Waiting for environment collection thread to finish")
        env_thread.join()
        lgr.debug("Environment collection finished")

    if sys_info_thread is not None:
        lgr.debug("Waiting for system information collection thread to finish")
        sys_info_thread.join()
        lgr.debug("System information collection finished")

    if args.record_types.has_system_summary():
        with open(log_paths.info, "a") as system_logs:
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            system_logs.write(report.dump_json())
    safe_close_files(files_to_close)
    lgr.info(report.execution_summary_formatted)
    return report.process.returncode


if __name__ == "__main__":
    main()

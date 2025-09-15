#!/usr/bin/env python3
from __future__ import annotations
import argparse
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from importlib.metadata import version
import json
import logging
import math
import os
import re
import shutil
import signal
import socket
import string
import subprocess
import sys
import textwrap
import threading
import time
from types import FrameType
from typing import IO, Any, Callable, Dict, List, Optional, TextIO, Tuple

__version__ = version("con-duct")
__schema_version__ = "0.2.2"


ABOUT_DUCT = """
duct is a lightweight wrapper that collects execution data for an arbitrary
command.  Execution data includes execution time, system information, and
resource usage statistics of the command and all its child processes. It is
intended to simplify the problem of recording the resources necessary to
execute a command, particularly in an HPC environment.

Resource usage is determined by polling (at a sample-interval).
During execution, duct produces a JSON lines (see https://jsonlines.org) file
with one data point recorded for each report (at a report-interval).

limitations:
  Duct uses session id to track the command process and its children, so it
  cannot handle the situation where a process creates a new session.
  If a command spawns child processes, duct will collect data on them, but
  duct exits as soon as the primary process exits.

configuration:
  Many options can be configured via JSON config file (--config), environment
  variables, or command line arguments. Precedence: built-in defaults < config
  file < environment variables < command line arguments.

  Default values shown below reflect the current configuration (built-in defaults
  or loaded from config file). Environment variables are listed with each option.
"""

DEFAULT_CONFIG_PATHS = "/etc/duct/config.json:${XDG_CONFIG_HOME:-~/.config}/duct/config.json:.duct/config.json"  # noqa B950
ENV_PREFIXES = ("PBS_", "SLURM_", "OSG")
SUFFIXES = {
    "stdout": "stdout",
    "stderr": "stderr",
    "usage": "usage.json",
    "info": "info.json",
}
_EXECUTION_SUMMARY_FORMAT = (
    "Summary:\n"
    "Exit Code: {exit_code!E}\n"
    "Command: {command}\n"
    "Log files location: {logs_prefix}\n"
    "Wall Clock Time: {wall_clock_time:.3f} sec\n"
    "Memory Peak Usage (RSS): {peak_rss!S}\n"
    "Memory Average Usage (RSS): {average_rss!S}\n"
    "Virtual Memory Peak Usage (VSZ): {peak_vsz!S}\n"
    "Virtual Memory Average Usage (VSZ): {average_vsz!S}\n"
    "Memory Peak Percentage: {peak_pmem:.2f!N}%\n"
    "Memory Average Percentage: {average_pmem:.2f!N}%\n"
    "CPU Peak Usage: {peak_pcpu:.2f!N}%\n"
    "Average CPU Usage: {average_pcpu:.2f!N}%\n"
)


lgr = logging.getLogger("con-duct")


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


class SessionMode(str, Enum):
    NEW_SESSION = "new-session"
    CURRENT_SESSION = "current-session"

    def __str__(self) -> str:
        return self.value


# ---------- Config system helper functions ----------
def bool_from_str(x: Any) -> bool:
    """Convert various string representations to boolean."""
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean: {x!r}")


def src_default(name: str) -> str:
    """Format source label for default value."""
    return f"default ({name})"


def src_file(path: str) -> str:
    """Format source label for config file."""
    return f"config file: {path}"


def src_env(var: str) -> str:
    """Format source label for environment variable."""
    return f"env var: {var}"


def src_cli(flag: str) -> str:
    """Format source label for CLI argument."""
    return f"CLI: {flag}"


# ---------- Field specification ----------
@dataclass(frozen=True)
class FieldSpec:
    """Specification for a configuration field."""

    kind: str  # "bool" | "value" | "positional"
    default: Any
    cast: Callable[[Any], Any]
    help: str
    config_key: str  # Hyphenated key used in config files and CLI flags
    env_var: Optional[str] = None  # Environment variable name (optional)
    choices: Optional[Iterable[Any]] = None
    validate: Optional[Callable[[Any], Any]] = None
    file_configurable: bool = True  # Whether this can be set in config files
    alt_flag_names: Optional[List[str]] = None
    # Additional metadata for argparse
    metavar: Optional[str] = None
    nargs: Optional[Any] = None


# ---------- Validation functions ----------
def validate_positive(v: float) -> float:
    """Validate that a value is positive."""
    if v <= 0:
        raise ValueError("must be greater than 0")
    return v


def validate_sample_report_interval(sample: float, report: float) -> None:
    """Validate that report interval >= sample interval."""
    if report < sample:
        raise ValueError(
            "report-interval must be greater than or equal to sample-interval"
        )


# ---------- Field specifications ----------
FIELD_SPECS: Dict[str, FieldSpec] = {
    "output_prefix": FieldSpec(
        kind="value",
        default=".duct/logs/{datetime_filesafe}-{pid}_",
        cast=str,
        help="File string format prefix for output files",
        config_key="output-prefix",
        env_var="DUCT_OUTPUT_PREFIX",
        alt_flag_names=["-p"],
    ),
    "summary_format": FieldSpec(
        kind="value",
        default=_EXECUTION_SUMMARY_FORMAT,
        cast=str,
        help="Output template for execution summary",
        config_key="summary-format",
        env_var="DUCT_SUMMARY_FORMAT",
    ),
    "colors": FieldSpec(
        kind="bool",
        default=False,
        cast=bool_from_str,
        help="Use colors in duct output",
        config_key="colors",
        env_var="DUCT_COLORS",
    ),
    "log_level": FieldSpec(
        kind="value",
        default="INFO",
        cast=str.upper,
        help="Level of log output to stderr",
        config_key="log-level",
        env_var="DUCT_LOG_LEVEL",
        choices=["NONE", "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        alt_flag_names=["-l"],
    ),
    "clobber": FieldSpec(
        kind="bool",
        default=False,
        cast=bool_from_str,
        help="Replace log files if they already exist",
        config_key="clobber",
        env_var="DUCT_CLOBBER",
    ),
    "sample_interval": FieldSpec(
        kind="value",
        default=1.0,
        cast=float,
        help="Interval in seconds between status checks",
        config_key="sample-interval",
        env_var="DUCT_SAMPLE_INTERVAL",
        validate=validate_positive,
        alt_flag_names=["--s-i"],
    ),
    "report_interval": FieldSpec(
        kind="value",
        default=60.0,
        cast=float,
        help="Interval in seconds for reporting aggregated data",
        config_key="report-interval",
        env_var="DUCT_REPORT_INTERVAL",
        validate=validate_positive,
        alt_flag_names=["--r-i"],
    ),
    "fail_time": FieldSpec(
        kind="value",
        default=3.0,
        cast=float,
        help="Time threshold for keeping logs of failing commands",
        config_key="fail-time",
        env_var="DUCT_FAIL_TIME",
        alt_flag_names=["--f-t"],
    ),
    "capture_outputs": FieldSpec(
        kind="value",
        default=Outputs.ALL,
        cast=lambda x: Outputs(x) if isinstance(x, str) else x,
        help="Record stdout, stderr, all, or none to log files",
        config_key="capture-outputs",
        env_var="DUCT_CAPTURE_OUTPUTS",
        choices=list(Outputs),
        alt_flag_names=["-c"],
    ),
    "outputs": FieldSpec(
        kind="value",
        default=Outputs.ALL,
        cast=lambda x: Outputs(x) if isinstance(x, str) else x,
        help="Print stdout, stderr, all, or none",
        config_key="outputs",
        env_var="DUCT_OUTPUTS",
        choices=list(Outputs),
        alt_flag_names=["-o"],
    ),
    "record_types": FieldSpec(
        kind="value",
        default=RecordTypes.ALL,
        cast=lambda x: RecordTypes(x) if isinstance(x, str) else x,
        help="Record system-summary, processes-samples, or all",
        config_key="record-types",
        env_var="DUCT_RECORD_TYPES",
        choices=list(RecordTypes),
        alt_flag_names=["-t"],
    ),
    "mode": FieldSpec(
        kind="value",
        default=SessionMode.NEW_SESSION,
        cast=lambda x: SessionMode(x) if isinstance(x, str) else x,
        help="Session mode for command execution",
        config_key="mode",
        env_var="DUCT_MODE",
        choices=list(SessionMode),
    ),
    "message": FieldSpec(
        kind="value",
        default="",
        cast=str,
        help="Descriptive message about this execution",
        config_key="message",
        env_var="DUCT_MESSAGE",
        alt_flag_names=["-m"],
    ),
    "quiet": FieldSpec(
        kind="bool",
        default=False,
        cast=bool_from_str,
        help="[deprecated] Disable duct logging output",
        config_key="quiet",
        env_var="DUCT_QUIET",
        alt_flag_names=["-q"],
    ),
}


def canonical_default(name: str) -> Any:
    """Get the canonical default value for a field."""
    return FIELD_SPECS[name].default


def cli_flag(name: str) -> str:
    """Get the CLI flag representation for a field."""
    spec = FIELD_SPECS[name]
    return f"--{spec.config_key}"


class CustomHelpFormatter(argparse.HelpFormatter):
    """Custom help formatter that shows defaults and environment variables."""

    def _fill_text(self, text: str, width: int, _indent: str) -> str:
        # Override _fill_text to respect the newlines and indentation in descriptions
        return "\n".join([textwrap.fill(line, width) for line in text.splitlines()])

    def _get_help_string(self, action):
        # Start with the base help text
        help_text = action.help or ""

        # Add default value if available
        if (
            hasattr(action, "canonical_default")
            and action.canonical_default is not None
        ):
            if help_text:
                help_text = help_text.rstrip()
            # Format the default value nicely
            default_str = str(action.canonical_default)
            if isinstance(action.canonical_default, str):
                # Truncate long strings
                if len(default_str) > 50:
                    default_str = default_str[:47] + "..."
            help_text += f" (default: {default_str})"

        # Add environment variable info if available
        if hasattr(action, "env_var") and action.env_var:
            if help_text:
                help_text = help_text.rstrip()
            help_text += f" [env: {action.env_var}]"

        return help_text


def build_parser() -> argparse.ArgumentParser:
    """Build argparse parser from FIELD_SPECS without injecting defaults."""
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description=ABOUT_DUCT,
        formatter_class=CustomHelpFormatter,
    )

    # Add --version
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    # Add config manually (not in FIELD_SPECS)
    config_action = parser.add_argument(
        "-C",
        "--config",
        default=DEFAULT_CONFIG_PATHS,
        help="Configuration file path",
    )
    # Store canonical default for help text
    config_action.canonical_default = DEFAULT_CONFIG_PATHS

    # Add --dump-config
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="Print the final merged config with value sources and exit",
    )

    # Add command and command_args as positional arguments (not in FIELD_SPECS)
    parser.add_argument(
        "command",
        help="The command to execute",
        metavar="command [command_args ...]",
    )
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help="Arguments for the command",
    )

    # Add all fields from specs
    for name, spec in FIELD_SPECS.items():

        if spec.kind == "positional":
            # Skip positional arguments (we don't have any in FIELD_SPECS now)
            continue

        elif spec.kind == "bool":
            # Simple boolean flags (just --flag, no --no-flag)
            names = []
            if spec.alt_flag_names:
                names.extend(spec.alt_flag_names)
            names.append(f"--{spec.config_key}")

            action = parser.add_argument(
                *names,
                dest=name,
                action="store_true",
                default=argparse.SUPPRESS,
                help=spec.help,
            )

            # Store canonical default and env_var for help text
            action.canonical_default = spec.default
            if spec.env_var:
                action.env_var = spec.env_var

        else:  # kind == "value"
            # Regular value arguments - use SUPPRESS so only explicit values override config
            kwargs = {
                "default": argparse.SUPPRESS,  # Don't inject defaults
                "help": spec.help,
                "type": spec.cast,
            }
            if spec.choices is not None:
                kwargs["choices"] = list(spec.choices)

            # Build argument names using alt_flag_names if available
            names = []
            if spec.alt_flag_names:
                names.extend(spec.alt_flag_names)
            names.append(f"--{spec.config_key}")

            # Special handling for quiet (boolean action)
            if spec.config_key == "quiet":
                kwargs.pop("type")  # quiet is action store_true
                kwargs["action"] = "store_true"

            action = parser.add_argument(*names, dest=name, **kwargs)

            # Store canonical default and env_var for help text
            action.canonical_default = spec.default
            if spec.env_var:
                action.env_var = spec.env_var

    return parser


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
                + "\nUse --clobber to overwrite conflicting files."
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
            # TODO: AVOID PRECREATION -- would interfere e.g. with git-annex
            # assistant monitoring new files to be created and committing
            # as soon as they are closed
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
        working_directory: str,
        colors: bool = False,
        clobber: bool = False,
        process: subprocess.Popen | None = None,
        message: str = "",
    ) -> None:
        self._command = command
        self.arguments = arguments
        self.log_paths = log_paths
        self.summary_format: str = summary_format
        self.clobber = clobber
        self.colors = colors
        self.message = message
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
        self.usage_file: TextIO | None = None
        self.working_directory: str = working_directory

    def __del__(self) -> None:
        safe_close_files([self.usage_file])

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
                    "-w",
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
        if self.usage_file is None:
            self.usage_file = open(self.log_paths.usage, "w")
        self.usage_file.write(json.dumps(self.current_sample.for_json()) + "\n")
        self.usage_file.flush()  # Force flush immediately

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
            "working_directory": self.working_directory,
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
                "working_directory": self.working_directory,
                "message": self.message,
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

    def _format_duration(self, value: float) -> str:
        """Format a duration in seconds to human-readable format."""
        if value >= 3600:  # >= 1 hour
            hours = int(value // 3600)
            minutes = int((value % 3600) // 60)
            seconds = value % 60
            return f"{hours}h {minutes}m {seconds:.1f}s"
        elif value >= 60:  # >= 1 minute
            minutes = int(value // 60)
            seconds = value % 60
            return f"{minutes}m {seconds:.1f}s"
        else:
            return f"{value:.2f}s"

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
        elif conversion == "P":  # Percentage
            if value is not None:
                return f"{float(value):.2f}%"
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "T":  # Time duration
            if value is not None:
                return self._format_duration(float(value))
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "D":  # DateTime from timestamp
            if value is not None:
                try:
                    dt = datetime.fromtimestamp(float(value))
                    return dt.strftime("%b %d, %Y %I:%M %p")
                except (ValueError, OSError):
                    return str(value)
            else:
                return self.color_word(self.NONE, self.RED)

        return super().convert_field(value, conversion)

    def format_field(self, value: Any, format_spec: str) -> Any:
        # TODO: move all the "coloring" into formatting, so we could correctly indent
        # given the format and only then color it up
        # print "> %r, %r" % (value, format_spec)
        if value is None:
            # TODO: could still use our formatter and make it red or smth like that
            return self.NONE
        # if it is a composite :format!conversion, we need to split it
        if "!" in format_spec and format_spec.index("!") > 1:
            format_spec, conversion = format_spec.split("!", 1)
        else:
            conversion = None
        try:
            value_ = super().format_field(value, format_spec)
        except ValueError as exc:
            lgr.warning(
                "Falling back to `str` formatting for %r due to exception: %s",
                value,
                exc,
            )
            return str(value)
        if conversion:
            return self.convert_field(value_, conversion)
        return value_


class Config:
    """Configuration management for duct.

    This class loads configuration from multiple sources (files, env vars, CLI)
    and provides validated access to all configuration values.
    """

    def __init__(self, cli_args: Dict[str, Any]):
        """Initialize and load configuration from all sources.

        Args:
            cli_args: Parsed CLI arguments dictionary from argparse
                     (with command, command_args, and config already removed)

        Raises:
            SystemExit: If configuration validation fails
        """
        self._cli_args = cli_args
        self._load_and_validate()

    def _load_and_validate(self) -> None:
        """Load configuration from all sources and validate it."""
        # Expand and load configuration files
        config_paths = self._expand_config_paths(self._cli_args["config"])
        file_layers = self._load_files(config_paths)

        # Load environment variables
        env_vals, env_src = self._load_env()

        # Merge all sources with provenance tracking
        merged, provenance = self._merge_with_provenance(
            defaults_as_source=True,
            file_layers=file_layers,
            env_vals=env_vals,
            env_src=env_src,
            cli_vals=self._cli_args,
        )

        # Coerce and validate
        final, errors = self._coerce_and_validate(merged, provenance)

        if errors:
            print("Configuration errors:", file=sys.stderr)
            for error in errors:
                print(error, file=sys.stderr)
            sys.exit(1)

        # Set all configuration values as instance attributes
        for name, spec in FIELD_SPECS.items():
            if name in final:
                setattr(self, name, final[name])
                # Store provenance information
                setattr(
                    self,
                    f"_source_{name}",
                    provenance.get(spec.config_key, src_default(name)),
                )
            elif spec.default is not None:
                setattr(self, name, spec.default)
                setattr(self, f"_source_{name}", src_default(name))

        # Validate cross-field constraints
        self._validate_constraints()

    def _validate_constraints(self) -> None:
        """Validate cross-field constraints."""
        if self.report_interval < self.sample_interval:
            raise argparse.ArgumentError(
                None,
                "--report-interval must be greater than or equal to --sample-interval.",
            )

    def _expand_config_paths(self, paths_str: str) -> List[str]:
        """Expand environment variables and user paths in config path string."""
        expanded = paths_str.replace(
            "${XDG_CONFIG_HOME:-~/.config}",
            os.getenv("XDG_CONFIG_HOME", "~/.config"),
        )
        expanded = os.path.expandvars(expanded)
        return [os.path.expanduser(p.strip()) for p in expanded.split(":") if p.strip()]

    def _load_files(self, paths: List[str]) -> List[Tuple[Dict[str, Any], str]]:
        """Load config files and return list of (dict, source_label)."""
        out: List[Tuple[Dict[str, Any], str]] = []
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                out.append((data, src_file(path)))
            except FileNotFoundError:
                continue
            except (json.JSONDecodeError, OSError) as e:
                raise SystemExit(f"Error loading config from {path}: {e}")
        return out

    def _load_env(self) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Load configuration from environment variables."""
        vals: Dict[str, Any] = {}
        prov: Dict[str, str] = {}
        for _name, spec in FIELD_SPECS.items():
            var = spec.env_var
            if var and var in os.environ:
                vals[spec.config_key] = os.environ[var]
                prov[spec.config_key] = src_env(var)
        return vals, prov

    def _merge_with_provenance(
        self,
        defaults_as_source: bool,
        file_layers: List[Tuple[Dict[str, Any], str]],
        env_vals: Dict[str, Any],
        env_src: Dict[str, str],
        cli_vals: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Merge configuration from all sources with provenance tracking."""
        merged: Dict[str, Any] = {}
        src: Dict[str, str] = {}

        # Defaults first
        for name, spec in FIELD_SPECS.items():
            if spec.default is not None:
                merged[spec.config_key] = spec.default
                if defaults_as_source:
                    src[spec.config_key] = src_default(name)

        # Files in order
        for data, label in file_layers:
            for k, v in data.items():
                # Convert both hyphen and underscore formats to underscore to match FIELD_SPECS
                spec_key = k.replace("-", "_")
                if spec_key in FIELD_SPECS and FIELD_SPECS[spec_key].file_configurable:
                    # Use the spec's config_key for consistency
                    config_key = FIELD_SPECS[spec_key].config_key
                    merged[config_key] = v
                    src[config_key] = label

        # Environment variables
        for k, v in env_vals.items():
            merged[k] = v
            src[k] = env_src[k]

        # CLI arguments
        for k, v in cli_vals.items():
            if k == "config":  # Skip special CLI-only options
                continue
            # Look up the spec to get the config_key
            if k in FIELD_SPECS:
                config_key = FIELD_SPECS[k].config_key
                merged[config_key] = v
                src[config_key] = src_cli(cli_flag(k))

        return merged, src

    def _coerce_and_validate(
        self, raw: Dict[str, Any], provenance: Dict[str, str]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Coerce types and validate all configuration values."""
        clean: Dict[str, Any] = {}
        errors: List[str] = []

        for name, spec in FIELD_SPECS.items():
            # Skip CLI-only positional args
            if not spec.file_configurable and spec.kind == "positional":
                continue

            val = raw.get(spec.config_key, spec.default)

            if val is None and spec.default is None:
                continue

            try:
                val = spec.cast(val)

                if spec.choices is not None and val not in spec.choices:
                    raise ValueError(f"must be one of {list(spec.choices)}")

                if spec.validate is not None:
                    val = spec.validate(val)

                clean[name] = val
            except Exception as e:
                src_label = provenance.get(spec.config_key, src_default(name))
                errors.append(
                    f"- {spec.config_key}: {e} (value {val!r} from {src_label})"
                )

        # Cross-field validation
        if "sample_interval" in clean and "report_interval" in clean:
            try:
                validate_sample_report_interval(
                    clean["sample_interval"], clean["report_interval"]
                )
            except ValueError as e:
                errors.append(f"- interval validation: {e}")

        return clean, errors

    # Provide compatibility properties for special names that differ from field names
    @property
    def session_mode(self) -> SessionMode:
        """Alias for mode field for backward compatibility."""
        return self.mode

    def dump_config(self) -> None:
        """Print the final merged config with value sources."""
        import json

        # Build the output structure
        config_dump = {}

        for name, spec in FIELD_SPECS.items():
            value = getattr(self, name, spec.default)
            source = getattr(self, f"_source_{name}", "default")

            config_dump[spec.config_key] = {
                "value": value,
                "source": source,
                "type": type(value).__name__,
            }

        print(json.dumps(config_dump, indent=2, default=str))


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


def remove_files(log_paths: LogPaths, assert_empty: bool = False) -> None:
    for _, file_path in log_paths:
        if os.path.exists(file_path):
            if assert_empty:
                assert os.stat(file_path).st_size == 0
            os.remove(file_path)


def main() -> None:
    # Set up basic logging configuration (level will be set properly in execute)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        level=logging.INFO,  # Use default level initially
    )
    parser = build_parser()

    # Check for --dump-config first to avoid command validation
    if "--dump-config" in sys.argv:
        # Add dummy command to avoid positional arg error, then parse
        argv_with_dummy = [arg for arg in sys.argv if arg != "--dump-config"] + [
            "--dump-config",
            "dummy",
        ]
        cli_args = vars(parser.parse_args(argv_with_dummy[1:]))  # Skip script name
        # Remove non FieldSpec Args
        cli_args.pop("dump_config", False)
        cli_args.pop("command", None)
        cli_args.pop("command_args", None)
        config = Config(cli_args)
        config.dump_config()
        sys.exit(0)

    # Normal parsing with full validation
    cli_args = vars(parser.parse_args())

    # Extract positional args and special flags (not part of FieldSpec)
    command = cli_args.pop("command", "")
    command_args = cli_args.pop("command_args", [])
    config = Config(cli_args)

    sys.exit(execute(config, command, command_args))


class ProcessSignalHandler:
    def __init__(self, pid: int) -> None:
        self.pid: int = pid
        self.sigcount: int = 0

    def handle_signal(self, _sig: int, _frame: Optional[FrameType]) -> None:
        self.sigcount += 1
        if self.sigcount == 1:
            lgr.info("Received SIGINT, passing to command")
            os.kill(self.pid, signal.SIGINT)
        elif self.sigcount == 2:
            lgr.info("Received second SIGINT, again passing to command")
            os.kill(self.pid, signal.SIGINT)
        elif self.sigcount == 3:
            lgr.warning("Received third SIGINT, forcefully killing command process")
            os.kill(self.pid, signal.SIGKILL)
        elif self.sigcount >= 4:
            lgr.critical("Exiting duct, skipping cleanup")
            os._exit(1)


def execute(config: Config, command: str, command_args: List[str]) -> int:
    """A wrapper to execute a command, monitor and log the process details.

    Args:
        config: Configuration object with all settings
        command: The command to execute
        command_args: Arguments for the command

    Returns:
        Exit code of the executed process.
    """
    if config.log_level == "NONE" or config.quiet:
        lgr.disabled = True
    else:
        lgr.setLevel(config.log_level)
    log_paths = LogPaths.create(config.output_prefix, pid=os.getpid())
    log_paths.prepare_paths(config.clobber, config.capture_outputs)
    stdout, stderr = prepare_outputs(config.capture_outputs, config.outputs, log_paths)
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

    working_directory = os.getcwd()
    full_command = " ".join([str(command)] + command_args)
    files_to_close = [stdout_file, stdout, stderr_file, stderr]

    report = Report(
        command,
        command_args,
        log_paths,
        config.summary_format,
        working_directory,
        config.colors,
        config.clobber,
        message=config.message,
    )
    files_to_close.append(report.usage_file)

    report.start_time = time.time()
    try:
        report.process = process = subprocess.Popen(
            [str(command)] + command_args,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=(config.session_mode == SessionMode.NEW_SESSION),
            cwd=report.working_directory,
        )
    except FileNotFoundError:
        # We failed to execute due to file not found in PATH
        # We should remove log etc files since they are 0-sized
        # degenerates etc
        safe_close_files(files_to_close)
        remove_files(log_paths, assert_empty=True)
        # mimicking behavior of bash and zsh.
        lgr.error("%s: command not found", command)
        return 127  # seems what zsh and bash return then

    handler = ProcessSignalHandler(process.pid)
    signal.signal(signal.SIGINT, handler.handle_signal)
    lgr.info("duct %s is executing %r...", __version__, full_command)
    lgr.info("Log files will be written to %s", log_paths.prefix)
    try:
        if config.session_mode == SessionMode.NEW_SESSION:
            report.session_id = os.getsid(
                process.pid
            )  # Get session ID of the new process
        else:  # CURRENT_SESSION mode
            report.session_id = os.getsid(
                os.getpid()
            )  # Get session ID of duct's own process
    except ProcessLookupError:  # process has already finished
        # TODO: log this at least.
        pass
    stop_event = threading.Event()
    if config.record_types.has_processes_samples():
        monitoring_args = [
            report,
            process,
            config.report_interval,
            config.sample_interval,
            stop_event,
        ]
        monitoring_thread = threading.Thread(
            target=monitor_process, args=monitoring_args
        )
        monitoring_thread.start()
    else:
        monitoring_thread = None

    if config.record_types.has_system_summary():
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

    if config.record_types.has_system_summary():
        with open(log_paths.info, "w") as system_logs:
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            system_logs.write(report.dump_json())
    safe_close_files(files_to_close)
    if process.returncode != 0 and (
        report.elapsed_time < config.fail_time or config.fail_time < 0
    ):
        lgr.info(
            "Removing log files since command failed%s.",
            f" in less than {config.fail_time} seconds" if config.fail_time > 0 else "",
        )
        remove_files(log_paths)
    else:
        lgr.info(report.execution_summary_formatted)
    return report.process.returncode


if __name__ == "__main__":
    main()

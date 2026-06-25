"""Process tracking and reporting for con-duct."""

from __future__ import annotations
from dataclasses import asdict
from importlib.metadata import version
import json
import logging
import math
import os
import shutil
import socket
import subprocess
import threading
import time
from typing import Any, List, Optional, TextIO
from con_duct._aggregation import Aggregator, null_summary
from con_duct._collectors import Measurement
from con_duct._constants import ENV_PREFIXES, __schema_version__
from con_duct._formatter import SummaryFormatter
from con_duct._models import LogPaths, SystemInfo
from con_duct._output import safe_close_files

__version__ = version("con-duct")

lgr = logging.getLogger("con-duct")


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
        measurements: Optional[List[Measurement]] = None,
    ) -> None:
        self._command = command
        self.arguments = arguments
        self.log_paths = log_paths
        self.summary_format: str = summary_format
        self.clobber = clobber
        self.colors = colors
        self.message = message
        # The resolved measurement selection (empty => nothing to record).
        self.measurements: List[Measurement] = measurements or []
        # Defaults to be set later
        self.start_time: float | None = None
        self.process = process
        self.session_id: int | None = None
        self.gpus: list[dict[str, str]] | None = None
        self.env: dict[str, str] | None = None
        self.number = 1
        self.system_info: SystemInfo | None = None
        # The collect -> buffer -> aggregate-once engine; built once the tracked
        # session id is known (see start_aggregator).
        self.aggregator: Optional[Aggregator] = None
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

    def start_aggregator(self) -> None:
        """Build the aggregation engine once the tracked session id is known."""
        assert self.session_id is not None
        self.aggregator = Aggregator(self.measurements, self.session_id)

    def write_record(self, record: dict) -> None:
        """Append one aggregated usage record as a JSON line."""
        if self.usage_file is None:
            self.usage_file = open(self.log_paths.usage, "w")
        self.usage_file.write(json.dumps(record) + "\n")
        self.usage_file.flush()  # Force flush immediately

    @property
    def execution_summary(self) -> dict[str, Any]:
        # killed by a signal
        # https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_08_02
        if self.process and self.process.returncode < 0:
            self.process.returncode = 128 + abs(self.process.returncode)
        # Measurement-derived keys (always present; None when unselected) plus
        # run/meta keys.  Built from the aggregator, or nulls if monitoring was
        # disabled so info.json schema stays stable.
        measurement_summary = (
            self.aggregator.summary() if self.aggregator is not None else null_summary()
        )
        num_samples = self.aggregator.num_samples if self.aggregator else 0
        num_reports = self.aggregator.num_reports if self.aggregator else 0
        return {
            "exit_code": self.process.returncode if self.process else None,
            "command": self.command,
            "logs_prefix": self.log_paths.prefix if self.log_paths else "",
            "wall_clock_time": self.wall_clock_time,
            **measurement_summary,
            "num_samples": num_samples,
            "num_reports": num_reports,
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
    if report.aggregator is None:
        report.start_aggregator()
    assert report.aggregator is not None
    while True:
        if process.poll() is not None:
            lgr.debug(
                "Breaking out of the monitor since the passthrough command has finished"
            )
            break
        recorded = report.aggregator.add_sample()
        if not recorded:
            # ps found no processes -- passthrough has probably finished before
            # a sample could be collected.
            if process.poll() is not None:
                lgr.debug(
                    "Breaking out of the monitor since the passthrough command has finished "
                    "before we could collect sample"
                )
                break
            # process is still running, but we could not collect sample
            continue
        if (
            report.start_time
            and report.elapsed_time >= (report.number - 1) * report_interval
        ):
            record = report.aggregator.report()
            if record is not None:
                report.write_record(record)
            report.number += 1
        if stop_event.wait(timeout=sample_interval):
            lgr.debug("Breaking out because stop event was set")
            break

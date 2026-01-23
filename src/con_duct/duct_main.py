#!/usr/bin/env python3
from __future__ import annotations
from collections.abc import Iterable
from dataclasses import asdict
from importlib.metadata import version
import json
import logging
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import IO, Any, Optional, TextIO
from con_duct._constants import ENV_PREFIXES
from con_duct._formatter import SummaryFormatter
from con_duct._models import (
    LogPaths,
    Outputs,
    RecordTypes,
    Sample,
    SessionMode,
    SystemInfo,
)
from con_duct._sampling import _get_sample
from con_duct._signals import SigIntHandler

__version__ = version("con-duct")
__schema_version__ = "0.2.2"

lgr = logging.getLogger("con-duct")

DUCT_OUTPUT_PREFIX = os.getenv(
    "DUCT_OUTPUT_PREFIX", ".duct/logs/{datetime_filesafe}-{pid}_"
)
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
    "Memory Peak Percentage: {peak_pmem:.2f!N}%\n"
    "Memory Average Percentage: {average_pmem:.2f!N}%\n"
    "CPU Peak Usage: {peak_pcpu:.2f!N}%\n"
    "Average CPU Usage: {average_pcpu:.2f!N}%\n"
)


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
        try:
            sample = _get_sample(self.session_id)
            return sample
        except subprocess.CalledProcessError as exc:  # when session_id has no processes
            lgr.debug("Error collecting sample: %s", str(exc))
            return None

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


def execute(
    command: str,
    command_args: list[str],
    output_prefix: str,
    sample_interval: float,
    report_interval: float,
    fail_time: float,
    clobber: bool,
    capture_outputs: Outputs,
    outputs: Outputs,
    record_types: RecordTypes,
    summary_format: str,
    colors: bool,
    mode: SessionMode,
    message: str = "",
) -> int:
    """A wrapper to execute a command, monitor and log the process details.

    Returns exit code of the executed process.
    """
    if report_interval < sample_interval:
        raise ValueError(
            "--report-interval must be greater than or equal to --sample-interval."
        )

    log_paths = LogPaths.create(output_prefix, pid=os.getpid())
    log_paths.prepare_paths(clobber, capture_outputs)
    stdout, stderr = prepare_outputs(capture_outputs, outputs, log_paths)
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
        summary_format,
        working_directory,
        colors,
        clobber,
        message=message,
    )
    files_to_close.append(report.usage_file)

    report.start_time = time.time()
    try:
        report.process = process = subprocess.Popen(
            [str(command)] + command_args,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=(mode == SessionMode.NEW_SESSION),
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

    signal.signal(signal.SIGINT, SigIntHandler(process.pid))
    lgr.info("duct %s is executing %r...", __version__, full_command)
    lgr.info("Log files will be written to %s", log_paths.prefix)
    try:
        if mode == SessionMode.NEW_SESSION:
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
    if record_types.has_processes_samples():
        monitoring_args = [
            report,
            process,
            report_interval,
            sample_interval,
            stop_event,
        ]
        monitoring_thread = threading.Thread(
            target=monitor_process, args=monitoring_args
        )
        monitoring_thread.start()
    else:
        monitoring_thread = None

    if record_types.has_system_summary():
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

    if record_types.has_system_summary():
        with open(log_paths.info, "w") as system_logs:
            report.run_time_seconds = f"{report.end_time - report.start_time}"
            system_logs.write(report.dump_json())
    safe_close_files(files_to_close)
    if process.returncode != 0 and (report.elapsed_time < fail_time or fail_time < 0):
        lgr.info(
            "Removing log files since command failed%s.",
            f" in less than {fail_time} seconds" if fail_time > 0 else "",
        )
        remove_files(log_paths)
    else:
        lgr.info(report.execution_summary_formatted)
    return report.process.returncode

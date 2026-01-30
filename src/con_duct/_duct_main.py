from __future__ import annotations
from importlib.metadata import version
import logging
import os
import signal
import subprocess
import threading
import time
from typing import IO, TextIO
from con_duct._models import LogPaths, Outputs, RecordTypes, SessionMode
from con_duct._output import TailPipe, prepare_outputs, remove_files, safe_close_files
from con_duct._signals import SigIntHandler
from con_duct._tracker import Report, monitor_process

__version__ = version("con-duct")

lgr = logging.getLogger("con-duct")

DUCT_OUTPUT_PREFIX = os.getenv("DUCT_OUTPUT_PREFIX", ".duct/logs/{datetime}-{pid}_")
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

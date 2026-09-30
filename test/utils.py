from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any

# duct logs this right after installing its SIGINT handler (_duct_main.execute).
# Anchored on the log format so the wrapped command's echoed stderr can't match.
DUCT_READY = re.compile(r"\] con-duct: duct \S+ is executing ")


def run_duct_command(cli_args: list[str], **kwargs: Any) -> int:
    """Helper to run duct with test-friendly defaults.

    Args:
        cli_args: Command and its arguments as a list (e.g., ["echo", "hello"])
        **kwargs: Override any duct_execute parameters

    Returns:
        Exit code from the executed command
    """
    from con_duct._duct_main import DUCT_OUTPUT_PREFIX, EXECUTION_SUMMARY_FORMAT
    from con_duct._duct_main import execute as duct_execute
    from con_duct._models import Outputs, RecordTypes, SessionMode

    command = cli_args[0]
    command_args = cli_args[1:] if len(cli_args) > 1 else []

    defaults = {
        "output_prefix": DUCT_OUTPUT_PREFIX,
        "sample_interval": 1.0,
        "report_interval": 60.0,
        "fail_time": 3.0,
        "clobber": False,
        "capture_outputs": Outputs.ALL,
        "outputs": Outputs.ALL,
        "record_types": RecordTypes.ALL,
        "summary_format": EXECUTION_SUMMARY_FORMAT,
        "colors": False,
        "mode": SessionMode.NEW_SESSION,
        "message": "",
    }
    defaults.update(kwargs)

    return duct_execute(command=command, command_args=command_args, **defaults)  # type: ignore[arg-type]


def start_duct(duct_cmd: str, args: list[str]) -> subprocess.Popen[str]:
    """Start duct as a subprocess and return once it is ready for signals.

    Reads duct's stderr until the log line emitted just after the SIGINT
    handler is installed. The caller should finish with ``communicate()``,
    which drains the rest of stderr and waits for duct to exit.

    Args:
        duct_cmd: How to invoke duct, e.g. "duct" or "con-duct run"
        args: Arguments for duct, including the command to run

    Returns:
        The running duct process, with its SIGINT handler installed
    """
    proc = subprocess.Popen(
        [*shlex.split(duct_cmd), *args], stderr=subprocess.PIPE, text=True
    )
    assert proc.stderr is not None  # for mypy
    for line in proc.stderr:
        if DUCT_READY.search(line):
            return proc
    raise RuntimeError(
        f"duct exited with {proc.wait()} before logging that it is executing"
    )


class MockStream:
    """Mocks stderr or stdout"""

    def __init__(self) -> None:
        self.buffer = BytesIO()

    def getvalue(self) -> bytes:
        return self.buffer.getvalue()


def assert_files(parent_dir: str, file_list: list[str], exists: bool = True) -> None:
    if exists:
        for file_path in file_list:
            assert Path(
                parent_dir, file_path
            ).exists(), f"Expected file does not exist: {file_path}"
    else:
        for file_path in file_list:
            assert not Path(
                parent_dir, file_path
            ).exists(), f"Unexpected file should not exist: {file_path}"

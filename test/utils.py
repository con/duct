from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Any


def run_duct_command(cli_args: list[str], **kwargs: Any) -> int:
    """Helper to run duct with test-friendly defaults.

    Args:
        cli_args: Command and its arguments as a list (e.g., ["echo", "hello"])
        **kwargs: Override any duct_execute parameters

    Returns:
        Exit code from the executed command
    """
    from con_duct.duct_main import (
        DUCT_OUTPUT_PREFIX,
        EXECUTION_SUMMARY_FORMAT,
        Outputs,
        RecordTypes,
        SessionMode,
    )
    from con_duct.duct_main import execute as duct_execute

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

from __future__ import annotations
import json
import logging
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
from time import sleep, time
import pytest
from utils import assert_files, run_duct_command
from con_duct import duct_main
from con_duct.duct_main import SUFFIXES, Outputs


def test_sample_less_than_report_interval(temp_output_dir: str) -> None:
    run_duct_command(
        ["echo", "test"],
        sample_interval=0.01,
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )


def test_sample_equal_to_report_interval(temp_output_dir: str) -> None:
    run_duct_command(
        ["echo", "test"],
        sample_interval=0.1,
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )


def test_sample_greater_than_report_interval() -> None:
    with pytest.raises(
        ValueError,
        match="--report-interval must be greater than or equal to --sample-interval",
    ):
        run_duct_command(
            ["echo", "test"],
            sample_interval=1.0,
            report_interval=0.1,
        )


TEST_SCRIPT_DIR = Path(__file__).parent.parent / "data"

expected_files = [
    SUFFIXES["stdout"],
    SUFFIXES["stderr"],
    SUFFIXES["info"],
    SUFFIXES["usage"],
]


def assert_expected_files(temp_output_dir: str, exists: bool = True) -> None:
    assert_files(temp_output_dir, expected_files, exists=exists)


def test_sanity_green(temp_output_dir: str) -> None:
    t0 = time()
    expected_exit_code = 0
    assert (
        run_duct_command(
            ["echo", "hello", "world"],
            sample_interval=4.0,
            report_interval=60.0,
            output_prefix=temp_output_dir,
        )
        == expected_exit_code
    )
    assert time() - t0 < 0.4  # we should not wait for a sample or report interval
    assert_expected_files(temp_output_dir)


def test_execution_summary(temp_output_dir: str) -> None:
    assert (
        run_duct_command(
            ["sleep", "0.1"],
            sample_interval=0.05,  # small enough to ensure we collect at least 1 sample
            report_interval=0.1,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_dict = json.loads(info.read())
    execution_summary = info_dict["execution_summary"]
    # Since resources used should be small lets make sure values are roughly sane
    assert execution_summary["average_pmem"] < 10
    assert execution_summary["peak_pmem"] < 10
    assert execution_summary["average_pcpu"] < 10
    assert execution_summary["peak_pcpu"] < 10
    assert execution_summary["exit_code"] == 0
    assert execution_summary["working_directory"] == os.getcwd()


@pytest.mark.parametrize("exit_code", [1, 2, 128])
def test_sanity_red(
    caplog: pytest.LogCaptureFixture, exit_code: int, temp_output_dir: str
) -> None:
    caplog.set_level("INFO")
    assert (
        run_duct_command(
            ["sh", "-c", f"exit {exit_code}"],
            output_prefix=temp_output_dir,
            fail_time=0,  # keep log files regardless of exit code
        )
        == exit_code
    )
    assert f"Exit Code: {exit_code}" in caplog.records[-1].message

    # We still should execute normally
    assert_expected_files(temp_output_dir)


def test_outputs_full(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    assert (
        run_duct_command(
            [script_path, "--duration", "1"],
            # It is our default, but let's be explicit
            capture_outputs=Outputs.ALL,
            outputs=Outputs.ALL,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    assert_expected_files(temp_output_dir)


def test_outputs_passthrough(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    assert (
        run_duct_command(
            [script_path, "--duration", "1"],
            capture_outputs=Outputs.NONE,
            outputs=Outputs.ALL,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_capture(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    assert (
        run_duct_command(
            [script_path, "--duration", "1"],
            capture_outputs=Outputs.ALL,
            outputs=Outputs.NONE,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    assert_expected_files(temp_output_dir)


def test_outputs_none(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    assert (
        run_duct_command(
            [script_path, "--duration", "1"],
            capture_outputs=Outputs.NONE,
            outputs=Outputs.NONE,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    # assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)

    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_exit_before_first_sample(temp_output_dir: str) -> None:
    assert (
        run_duct_command(
            ["ls"],
            sample_interval=0.1,
            report_interval=0.1,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    assert_expected_files(temp_output_dir)
    # TODO check usagefile


def test_run_less_than_report_interval(temp_output_dir: str) -> None:
    assert (
        run_duct_command(
            ["sleep", "0.01"],
            sample_interval=0.001,
            report_interval=0.1,
            output_prefix=temp_output_dir,
        )
        == 0
    )
    # Specifically we need to assert that usage file gets written anyway.
    assert_expected_files(temp_output_dir)


def test_execute_unknown_command(
    temp_output_dir: str, caplog: pytest.LogCaptureFixture
) -> None:
    cmd = "this_command_does_not_exist_123abrakadabra"
    with caplog.at_level(logging.ERROR):
        assert run_duct_command([cmd]) == 127
    assert f"{cmd}: command not found" in caplog.text
    assert_expected_files(temp_output_dir, exists=False)


def _runner_for_signal_int(temp_output_dir: str, fail_time: float | None) -> int:
    kws = {}
    if fail_time is not None:
        kws["fail_time"] = fail_time
    return run_duct_command(
        ["sleep", "60.74016230000801"], output_prefix=temp_output_dir, **kws
    )


@pytest.mark.parametrize("fail_time", [None, 0, 10, -1, -3.14])
def test_signal_int(temp_output_dir: str, fail_time: float | None) -> None:

    wait_time = 0.3
    proc = multiprocessing.Process(
        target=_runner_for_signal_int, args=(temp_output_dir, fail_time)
    )
    proc.start()
    sleep(wait_time)
    assert proc.pid is not None, "Process PID should not be None"  # for mypy
    os.kill(proc.pid, signal.SIGINT)
    proc.join()

    # Once the command has been killed, duct should exit gracefully with exit code 0
    assert proc.exitcode == 0

    if fail_time is None or fail_time != 0:
        assert_expected_files(temp_output_dir, exists=False)
    else:
        # proc exit code should Cannot retrieve the exit code from the thread, it is written to the file
        with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
            info_data = json.loads(info.read())

        command_exit_code = info_data["execution_summary"]["exit_code"]
        # SIGINT
        assert command_exit_code == 128 + 2


def _runner_for_signal_kill(temp_output_dir: str, fail_time: float | None) -> int:
    script_path = str(TEST_SCRIPT_DIR / "signal_ignorer.py")
    kws = {}
    if fail_time is not None:
        kws["fail_time"] = fail_time
    return run_duct_command([script_path], output_prefix=temp_output_dir, **kws)


@pytest.mark.parametrize("fail_time", [None, 0, 10, -1, -3.14])
def test_signal_kill(temp_output_dir: str, fail_time: float | None) -> None:

    wait_time = 0.6
    proc = multiprocessing.Process(
        target=_runner_for_signal_kill, args=(temp_output_dir, fail_time)
    )
    proc.start()
    sleep(wait_time)
    assert proc.pid is not None, "Process PID should not be None"  # for mypy
    os.kill(proc.pid, signal.SIGINT)
    sleep(wait_time)
    os.kill(proc.pid, signal.SIGINT)
    sleep(wait_time)
    os.kill(proc.pid, signal.SIGINT)
    proc.join()

    # Once the command has been killed, duct should exit gracefully with exit code 0
    assert proc.exitcode == 0

    if fail_time is None or fail_time != 0:
        assert_expected_files(temp_output_dir, exists=False)
    else:
        # Cannot retrieve the command exit code from the thread, get from duct log
        with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
            info_data = json.loads(info.read())

        command_exit_code = info_data["execution_summary"]["exit_code"]
        # SIGKILL
        assert command_exit_code == 128 + 9


def test_duct_as_executable(temp_output_dir: str) -> None:
    ps_command = [
        sys.executable,
        duct_main.__file__,
        "-p",
        temp_output_dir,
        "-q",
        "sleep",
        "0.01",
    ]
    # Assert does not raise
    subprocess.check_output(ps_command, shell=False).decode()


def test_message_in_json_output(temp_output_dir: str) -> None:
    """Test that message appears in JSON output when provided."""
    test_message = "Electrolytes, its what plants crave"
    assert (
        run_duct_command(
            ["echo", "hello"],
            output_prefix=temp_output_dir,
            message=test_message,
        )
        == 0
    )

    # Check that message appears in info.json
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_dict = json.loads(info.read())

    assert "message" in info_dict
    assert info_dict["message"] == test_message


def test_no_message_in_json_output(temp_output_dir: str) -> None:
    """Test that message field is empty string when not provided."""
    assert (
        run_duct_command(
            ["echo", "hello"],
            output_prefix=temp_output_dir,
        )
        == 0
    )

    # Check that message field is empty string in info.json
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_dict = json.loads(info.read())

    assert "message" in info_dict
    assert info_dict["message"] == ""

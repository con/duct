from __future__ import annotations
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
from time import sleep, time
import pytest
from utils import assert_files
import con_duct.__main__ as __main__
from con_duct.__main__ import SUFFIXES, Arguments, Outputs, execute

TEST_SCRIPT_DIR = Path(__file__).with_name("data")

expected_files = [
    SUFFIXES["stdout"],
    SUFFIXES["stderr"],
    SUFFIXES["info"],
    SUFFIXES["usage"],
]


def assert_expected_files(temp_output_dir: str, exists: bool = True) -> None:
    assert_files(temp_output_dir, expected_files, exists=exists)


def test_sanity_green(caplog: pytest.LogCaptureFixture, temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        ["echo", "hello", "world"],
        sample_interval=4.0,
        report_interval=60.0,
        output_prefix=temp_output_dir,
    )
    t0 = time()
    exit_code = 0
    assert execute(args) == exit_code
    assert time() - t0 < 0.4  # we should not wait for a sample or report interval
    assert_expected_files(temp_output_dir)
    assert "Exit Code: 0" in caplog.records[-1].message


def test_execution_summary(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        ["sleep", "0.1"],
        sample_interval=0.05,  # small enough to ensure we collect at least 1 sample
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
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
    args = Arguments.from_argv(
        ["sh", "-c", f"exit {exit_code}"],
        output_prefix=temp_output_dir,
        fail_time=0,  # keep log files regardless of exit code
    )
    caplog.set_level("INFO")
    assert execute(args) == exit_code
    assert f"Exit Code: {exit_code}" in caplog.records[-1].message

    # We still should execute normally
    assert_expected_files(temp_output_dir)


def test_outputs_full(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    args = Arguments.from_argv(
        [script_path, "--duration", "1"],
        # It is our default, but let's be explicit
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    assert_expected_files(temp_output_dir)


def test_outputs_passthrough(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    args = Arguments.from_argv(
        [script_path, "--duration", "1"],
        capture_outputs=Outputs.NONE,
        outputs=Outputs.ALL,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_capture(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    args = Arguments.from_argv(
        [script_path, "--duration", "1"],
        capture_outputs=Outputs.ALL,
        outputs=Outputs.NONE,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    assert_expected_files(temp_output_dir)


def test_outputs_none(temp_output_dir: str) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    args = Arguments.from_argv(
        [script_path, "--duration", "1"],
        capture_outputs=Outputs.NONE,
        outputs=Outputs.NONE,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    # assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)

    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_none_quiet(
    temp_output_dir: str,
    capsys: pytest.CaptureFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    script_path = str(TEST_SCRIPT_DIR / "test_script.py")
    args = Arguments.from_argv(
        [script_path, "--duration", "1"],
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    r1 = capsys.readouterr()
    assert r1.out.startswith("this is of test of STDOUT")
    assert "this is of test of STDERR" in r1.err
    assert "Summary" in caplog.text
    caplog_text1 = caplog.text

    # now quiet please
    args.quiet = True
    args.clobber = True  # to avoid the file already exists error
    assert execute(args) == 0
    r2 = capsys.readouterr()
    # Still have all the outputs
    assert r1 == r2
    # But nothing new to the log
    assert caplog.text == caplog_text1

    # log_level NONE should have the same behavior as quiet
    args.log_level = "NONE"
    args.quiet = False
    args.clobber = True  # to avoid the file already exists error
    assert execute(args) == 0
    r3 = capsys.readouterr()
    # Still have all the outputs
    assert r1 == r3
    # But nothing new to the log
    assert caplog.text == caplog_text1


def test_exit_before_first_sample(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        ["ls"], sample_interval=0.1, report_interval=0.1, output_prefix=temp_output_dir
    )

    assert execute(args) == 0
    assert_expected_files(temp_output_dir)
    # TODO check usagefile


def test_run_less_than_report_interval(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        ["sleep", "0.01"],
        sample_interval=0.001,
        report_interval=0.1,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    # Specifically we need to assert that usage.json gets written anyway.
    assert_expected_files(temp_output_dir)


def test_execute_unknown_command(
    temp_output_dir: str, capsys: pytest.CaptureFixture
) -> None:
    cmd = "this_command_does_not_exist_123abrakadabra"
    args = Arguments.from_argv([cmd])
    assert execute(args) == 127
    assert f"{cmd}: command not found\n" == capsys.readouterr().err
    assert_expected_files(temp_output_dir, exists=False)


@pytest.mark.parametrize("fail_time", [None, 0, 10, -1, -3.14])
def test_signal_int(temp_output_dir: str, fail_time: float | None) -> None:

    def runner() -> int:
        kws = {}
        if fail_time is not None:
            kws["fail_time"] = fail_time
        args = Arguments.from_argv(
            ["sleep", "60.74016230000801"], output_prefix=temp_output_dir, **kws
        )
        return execute(args)

    wait_time = 0.3
    proc = multiprocessing.Process(target=runner)
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


@pytest.mark.parametrize("fail_time", [None, 0, 10, -1, -3.14])
def test_signal_kill(temp_output_dir: str, fail_time: float | None) -> None:

    def runner() -> int:
        script_path = str(TEST_SCRIPT_DIR / "signal_ignorer.py")
        kws = {}
        if fail_time is not None:
            kws["fail_time"] = fail_time
        args = Arguments.from_argv([script_path], output_prefix=temp_output_dir, **kws)
        return execute(args)

    wait_time = 0.6
    proc = multiprocessing.Process(target=runner)
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
        __main__.__file__,
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
    args = Arguments.from_argv(
        ["-m", test_message, "echo", "hello"],
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0

    # Check that message appears in info.json
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_dict = json.loads(info.read())

    assert "message" in info_dict
    assert info_dict["message"] == test_message


def test_no_message_in_json_output(temp_output_dir: str) -> None:
    """Test that message field is empty string when not provided."""
    args = Arguments.from_argv(
        ["echo", "hello"],
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0

    # Check that message field is empty string in info.json
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_dict = json.loads(info.read())

    assert "message" in info_dict
    assert info_dict["message"] == ""

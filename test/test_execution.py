from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
from time import sleep, time
import pytest
from utils import assert_files
import con_duct.__main__ as __main__
from con_duct.__main__ import SUFFIXES, Arguments, Outputs, execute

TEST_SCRIPT = str(Path(__file__).with_name("data") / "test_script.py")

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


@pytest.mark.parametrize("exit_code", [1, 2, 128])
def test_sanity_red(
    caplog: pytest.LogCaptureFixture, exit_code: int, temp_output_dir: str
) -> None:
    args = Arguments.from_argv(
        ["sh", "-c", f"exit {exit_code}"],
        output_prefix=temp_output_dir,
    )
    caplog.set_level("INFO")
    assert execute(args) == exit_code
    assert f"Exit Code: {exit_code}" in caplog.records[-1].message

    # We still should execute normally
    assert_expected_files(temp_output_dir)


def test_outputs_full(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        [TEST_SCRIPT, "--duration", "1"],
        # It is our default, but let's be explicit
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    assert_expected_files(temp_output_dir)


def test_outputs_passthrough(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        [TEST_SCRIPT, "--duration", "1"],
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
    args = Arguments.from_argv(
        [TEST_SCRIPT, "--duration", "1"],
        capture_outputs=Outputs.ALL,
        outputs=Outputs.NONE,
        output_prefix=temp_output_dir,
    )
    assert execute(args) == 0
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    assert_expected_files(temp_output_dir)


def test_outputs_none(temp_output_dir: str) -> None:
    args = Arguments.from_argv(
        [TEST_SCRIPT, "--duration", "1"],
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
    args = Arguments.from_argv(
        [TEST_SCRIPT, "--duration", "1"],
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


def test_signal_exit(temp_output_dir: str) -> None:

    def runner() -> int:
        args = Arguments.from_argv(
            ["sleep", "60.74016230000801"],
            output_prefix=temp_output_dir,
        )
        return execute(args)

    thread = threading.Thread(target=runner)
    thread.start()
    sleep(0.03)  # make sure the process is started
    ps_command = "ps aux | grep '[s]leep 60.74016230000801'"  # brackets to not match grep process
    ps_output = subprocess.check_output(ps_command, shell=True).decode()
    pid = int(ps_output.split()[1])
    os.kill(pid, signal.SIGTERM)

    thread.join()
    # Cannot retrieve the exit code from the thread, it is written to the file
    with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
        info_data = json.loads(info.read())

    exit_code = info_data["execution_summary"]["exit_code"]
    assert exit_code == 128 + 15


def test_duct_as_executable(temp_output_dir: str) -> None:
    ps_command = f"{sys.executable} {__main__.__file__} -p {temp_output_dir} sleep 0.01"
    # Assert does not raise
    subprocess.check_output(ps_command, shell=True).decode()

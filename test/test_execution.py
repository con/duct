from __future__ import annotations
from pathlib import Path
from unittest import mock
import pytest
from utils import assert_files
from con_duct.__main__ import (
    EXECUTION_SUMMARY_FORMAT,
    SUFFIXES,
    Arguments,
    Outputs,
    RecordTypes,
    execute,
)

TEST_SCRIPT = str(Path(__file__).with_name("data") / "test_script.py")

expected_files = [
    SUFFIXES["stdout"],
    SUFFIXES["stderr"],
    SUFFIXES["info"],
    SUFFIXES["usage"],
]


def assert_expected_files(temp_output_dir: str, exists: bool = True) -> None:
    assert_files(temp_output_dir, expected_files, exists=exists)


def test_sanity_green(temp_output_dir: str) -> None:
    args = Arguments(
        command="echo",
        command_args=["hello", "world"],
        output_prefix=temp_output_dir,
        sample_interval=1.0,
        report_interval=60.0,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0

    assert_expected_files(temp_output_dir)
    # TODO check usagefile empty


@pytest.mark.parametrize("exit_code", [0, 1, 2, 128])
def test_sanity_red(
    caplog: pytest.LogCaptureFixture, exit_code: int, temp_output_dir: str
) -> None:
    args = Arguments(
        command="sh",
        command_args=["-c", f"exit {exit_code}"],
        output_prefix=temp_output_dir,
        sample_interval=1.0,
        report_interval=60.0,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format=EXECUTION_SUMMARY_FORMAT,
        log_level="INFO",
        quiet=False,
    )
    caplog.set_level("INFO")
    assert execute(args) == exit_code
    assert f"Exit Code: {exit_code}" in caplog.records[-1].message

    # We still should execute normally
    assert_expected_files(temp_output_dir)


def test_outputs_full(temp_output_dir: str) -> None:
    args = Arguments(
        command=TEST_SCRIPT,
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0
    assert_expected_files(temp_output_dir)


def test_outputs_passthrough(temp_output_dir: str) -> None:
    args = Arguments(
        command=TEST_SCRIPT,
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.NONE,
        outputs=Outputs.ALL,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0
    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_capture(temp_output_dir: str) -> None:
    args = Arguments(
        command=TEST_SCRIPT,
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.NONE,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    assert_expected_files(temp_output_dir)


def test_outputs_none(temp_output_dir: str) -> None:
    args = Arguments(
        command=TEST_SCRIPT,
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.NONE,
        outputs=Outputs.NONE,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0
    # assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = [SUFFIXES["info"], SUFFIXES["usage"]]
    assert_files(temp_output_dir, expected_files, exists=True)

    not_expected_files = [SUFFIXES["stdout"], SUFFIXES["stderr"]]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_none_quiet(temp_output_dir: str) -> None:
    args = Arguments(
        command=TEST_SCRIPT,
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs=Outputs.NONE,
        outputs=Outputs.NONE,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="ERROR",
        quiet=False,
    )
    with mock.patch("sys.stderr", new_callable=mock.MagicMock) as mock_stderr:
        assert execute(args) == 0
        mock_stderr.write.assert_not_called()


def test_exit_before_first_sample(temp_output_dir: str) -> None:
    args = Arguments(
        command="ls",
        command_args=[],
        output_prefix=temp_output_dir,
        sample_interval=0.1,
        report_interval=0.1,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.NONE,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
    )
    assert execute(args) == 0
    assert_expected_files(temp_output_dir)
    # TODO check usagefile


def test_run_less_than_report_interval(temp_output_dir: str) -> None:
    args = Arguments(
        command="sleep",
        command_args=["0.01"],
        output_prefix=temp_output_dir,
        sample_interval=0.001,
        report_interval=0.1,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.NONE,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format="",
        log_level="INFO",
        quiet=False,
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

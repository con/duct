from __future__ import annotations
from pathlib import Path
from unittest import mock
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
        quiet=False,
    )
    execute(args)
    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["info"],
        SUFFIXES["usage"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)
    # TODO check usagefile empty


def test_sanity_red(temp_output_dir: str) -> None:
    args = Arguments(
        command="false",
        command_args=[],
        output_prefix=temp_output_dir,
        sample_interval=1.0,
        report_interval=60.0,
        capture_outputs=Outputs.ALL,
        outputs=Outputs.ALL,
        record_types=RecordTypes.ALL,
        clobber=False,
        summary_format=EXECUTION_SUMMARY_FORMAT,
        quiet=False,
    )
    with mock.patch("sys.stdout", new_callable=mock.MagicMock) as mock_stdout:
        execute(args)
        call_args = [call.args for call in mock_stdout.write.call_args_list]
        assert any("Exit Code: 1" in call_arg[0] for call_arg in call_args)

    # We still should execute normally
    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["info"],
        SUFFIXES["usage"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)


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
        quiet=False,
    )
    execute(args)
    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["info"],
        SUFFIXES["usage"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)


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
        quiet=False,
    )
    execute(args)
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
        quiet=False,
    )
    execute(args)
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["info"],
        SUFFIXES["usage"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)


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
        quiet=False,
    )
    execute(args)
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
        quiet=True,
    )
    with mock.patch("sys.stdout", new_callable=mock.MagicMock) as mock_stdout:
        execute(args)
        mock_stdout.write.assert_not_called()


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
        quiet=False,
    )
    execute(args)
    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["info"],
        SUFFIXES["usage"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)
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
        quiet=False,
    )
    execute(args)
    # Specifically we need to assert that usage.json gets written anyway.
    expected_files = [
        SUFFIXES["stdout"],
        SUFFIXES["stderr"],
        SUFFIXES["usage"],
        SUFFIXES["info"],
    ]
    assert_files(temp_output_dir, expected_files, exists=True)

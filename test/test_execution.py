from __future__ import annotations
import os
from pathlib import Path
from unittest import mock
import pytest
from utils import assert_files
from duct.__main__ import Arguments, Outputs, RecordTypes, execute

TEST_SCRIPT = str(Path(__file__).with_name("data") / "test_script.py")


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> str:
    # Append path separator so that value is recognized as a directory when
    # passed to `output_prefix`
    return str(tmp_path) + os.sep


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
    )
    execute(args)
    # When runtime < sample_interval, we won't have a usage.json
    expected_files = ["stdout", "stderr", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)


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
    )
    with mock.patch("sys.stdout", new_callable=mock.MagicMock) as mock_stdout:
        execute(args)
        mock_stdout.write.assert_has_calls([mock.call("Exit Code: 1")])

    # We still should execute normally
    expected_files = ["stdout", "stderr", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)
    # But no polling of the already failed command
    not_expected_files = ["usage.json"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


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
    )
    execute(args)
    expected_files = ["stdout", "stderr", "info.json", "usage.json"]
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
    )
    execute(args)
    expected_files = ["info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = ["stdout", "stderr"]
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
    )
    execute(args)
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = ["stdout", "stderr", "info.json", "usage.json"]
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
    )
    execute(args)
    # assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = ["info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)

    not_expected_files = ["stdout", "stderr"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


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
    )
    execute(args)
    expected_files = ["stdout", "stderr", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = ["usage.json"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


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
    )
    execute(args)
    # Specifically we need to assert that usage.json gets written anyway.
    expected_files = ["stdout", "stderr", "usage.json", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)

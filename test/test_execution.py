import argparse
import os
import shutil
from unittest import mock
import pytest
from utils import assert_files
from duct import execute


@pytest.fixture
def temp_output_dir(tmp_path):
    yield str(tmp_path) + os.sep
    shutil.rmtree(tmp_path)


def test_sanity_green(temp_output_dir):
    args = argparse.Namespace(
        command="echo",
        command_args=["hello", "world"],
        output_prefix=temp_output_dir,
        sample_interval=1.0,
        report_interval=60.0,
        capture_outputs="all",
        outputs="all",
        record_types="all",
    )
    execute(args)
    # When runtime < sample_interval, we won't have a usage.json
    expected_files = ["stdout", "stderr", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)


def test_sanity_red(temp_output_dir):
    args = argparse.Namespace(
        command="false",
        command_args=[],
        output_prefix=temp_output_dir,
        sample_interval=1.0,
        report_interval=60.0,
        capture_outputs="all",
        outputs="all",
        record_types="all",
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


def test_outputs_full(temp_output_dir):
    args = argparse.Namespace(
        command="./test_script.py",
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs="all",
        outputs="all",
        record_types="all",
    )
    execute(args)
    expected_files = ["stdout", "stderr", "info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)


def test_outputs_passthrough(temp_output_dir):
    args = argparse.Namespace(
        command="./test_script.py",
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs="none",
        outputs="all",
        record_types="all",
    )
    execute(args)
    expected_files = ["info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = ["stdout", "stderr"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_outputs_capture(temp_output_dir):
    args = argparse.Namespace(
        command="./test_script.py",
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs="all",
        outputs="none",
        record_types="all",
    )
    execute(args)
    # TODO make this work assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = ["stdout", "stderr", "info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)


def test_outputs_none(temp_output_dir):
    args = argparse.Namespace(
        command="./test_script.py",
        command_args=["--duration", "1"],
        output_prefix=temp_output_dir,
        sample_interval=0.01,
        report_interval=0.1,
        capture_outputs="none",
        outputs="none",
        record_types="all",
    )
    execute(args)
    # assert mock.call("this is of test of STDOUT\n") not in mock_stdout.write.mock_calls

    expected_files = ["info.json", "usage.json"]
    assert_files(temp_output_dir, expected_files, exists=True)

    not_expected_files = ["stdout", "stderr"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_exit_before_first_sample(temp_output_dir):
    args = argparse.Namespace(
        command="ls",
        command_args=[],
        output_prefix=temp_output_dir,
        sample_interval=0.1,
        report_interval=0.1,
        capture_outputs="all",
        outputs="none",
        record_types="all",
    )
    execute(args)
    expected_files = ["stdout", "stderr", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)
    not_expected_files = ["usage.json"]
    assert_files(temp_output_dir, not_expected_files, exists=False)


def test_run_less_than_report_interval(temp_output_dir):
    args = argparse.Namespace(
        command="sleep",
        command_args=["0.01"],
        output_prefix=temp_output_dir,
        sample_interval=0.001,
        report_interval=0.1,
        capture_outputs="all",
        outputs="none",
        record_types="all",
    )
    execute(args)
    # Specifically we need to assert that usage.json gets written anyway.
    expected_files = ["stdout", "stderr", "usage.json", "info.json"]
    assert_files(temp_output_dir, expected_files, exists=True)

import argparse
import os
import re
import subprocess
from unittest import mock
import pytest
from con_duct.cli import RunArguments as Arguments


def test_duct_help() -> None:
    out = subprocess.check_output(["duct", "--help", "ps"])
    # duct delegates to con-duct run, so usage shows con-duct
    assert "usage: con-duct <command> [options] run" in str(out)
    # Help text should mention both entry points
    assert "'duct' or 'con-duct run'" in str(out)


def test_duct_version() -> None:
    out = subprocess.check_output(["duct", "--version"])
    output_str = out.decode("utf-8").strip()
    # duct now delegates to con-duct run, so version shows con-duct with full prog name
    assert output_str.startswith("con-duct ")
    # Check that it has a version pattern (version appears after prog name)
    assert re.search(r"\d+\.\d+\.\d+", output_str)


def test_con_duct_version() -> None:
    out = subprocess.check_output(["con-duct", "--version"])
    output_str = out.decode("utf-8").strip()
    assert output_str.startswith("con-duct ")
    # Check that it has a version pattern
    assert re.match(r"con-duct \d+\.\d+\.\d+", output_str)


def test_cmd_help() -> None:
    out = subprocess.check_output(["duct", "ps", "--help"])
    assert "ps [options]" in str(out)
    # Should show ps help, not duct/con-duct help
    assert "usage: con-duct <command> [options] run" not in str(out)


@pytest.mark.parametrize(
    "args",
    [
        ["duct", "--unknown", "ps"],
        ["duct", "--unknown", "ps", "--shouldhavenoeffect"],
    ],
)
def test_duct_unrecognized_arg(args: list) -> None:
    try:
        subprocess.check_output(args, stderr=subprocess.STDOUT)
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "error: unrecognized arguments: --unknown" in str(e.stdout)


def test_duct_missing_cmd() -> None:
    try:
        subprocess.check_output(
            ["duct", "--sample-interval", "1"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "error: the following arguments are required: command" in str(e.stdout)


def test_abreviation_disabled() -> None:
    """
    If abbreviation is enabled, options passed to command (not duct) are still
    filtered through the argparse and causes problems.
    """
    try:
        subprocess.check_output(["duct", "ps", "--output"], stderr=subprocess.STDOUT)
        raise AssertionError("Invocation of 'ps' should have failed")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 1
        assert "duct: error: ambiguous option: --output could match" not in str(
            e.stdout
        )
        assert "ps [options]" in str(e.stdout)


@pytest.mark.parametrize(
    "mode_arg,expected_mode",
    [
        ([], "new-session"),  # default
        (["--mode", "new-session"], "new-session"),
        (["--mode", "current-session"], "current-session"),
    ],
)
def test_mode_argument_parsing(mode_arg: list, expected_mode: str) -> None:
    """Test that --mode argument is parsed correctly with both long and short forms."""
    cmd_args = mode_arg + ["echo", "test"]
    args = Arguments.from_argv(cmd_args)
    assert str(args.session_mode) == expected_mode


def test_mode_invalid_value() -> None:
    """Test that invalid --mode values are rejected."""
    try:
        subprocess.check_output(
            ["duct", "--mode", "invalid-mode", "echo", "test"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with invalid mode value")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "invalid SessionMode value: 'invalid-mode'" in str(e.stdout)


def test_message_parsing() -> None:
    """Test that -m/--message flag is correctly parsed."""
    # Test short flag
    args = Arguments.from_argv(["-m", "test message", "echo", "hello"])
    assert args.message == "test message"
    assert args.command == "echo"
    assert args.command_args == ["hello"]

    # Test long flag
    args = Arguments.from_argv(["--message", "another message", "ls"])
    assert args.message == "another message"
    assert args.command == "ls"

    # Test without message (should be empty string)
    args = Arguments.from_argv(["echo", "hello"])
    assert args.message == ""


def test_message_env_variable() -> None:
    """Test that DUCT_MESSAGE environment variable is used as default."""
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        args = Arguments.from_argv(["echo", "hello"])
        assert args.message == "env message"

    # Command line should override env variable
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        args = Arguments.from_argv(["-m", "cli message", "echo", "hello"])
        assert args.message == "cli message"


def test_sample_less_than_report_interval() -> None:
    args = Arguments.from_argv(
        ["fake"],
        sample_interval=0.01,
        report_interval=0.1,
    )
    assert args.sample_interval <= args.report_interval


def test_sample_equal_to_report_interval() -> None:
    args = Arguments.from_argv(
        ["fake"],
        sample_interval=0.1,
        report_interval=0.1,
    )
    assert args.sample_interval == args.report_interval


def test_sample_equal_greater_than_report_interval() -> None:
    with pytest.raises(argparse.ArgumentError):
        Arguments.from_argv(
            ["fake"],
            sample_interval=1.0,
            report_interval=0.1,
        )

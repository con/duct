import re
import subprocess
import pytest
from con_duct.__main__ import Outputs, build_parser


def test_duct_help() -> None:
    out = subprocess.check_output(["duct", "--help", "ps"])
    assert "usage: duct [-h]" in str(out)


def test_duct_version() -> None:
    out = subprocess.check_output(["duct", "--version"])
    output_str = out.decode("utf-8").strip()
    assert output_str.startswith("duct ")
    # Check that it has a version pattern
    assert re.match(r"duct \d+\.\d+\.\d+", output_str)


def test_con_duct_version() -> None:
    out = subprocess.check_output(["con-duct", "--version"])
    output_str = out.decode("utf-8").strip()
    assert output_str.startswith("con-duct ")
    # Check that it has a version pattern
    assert re.match(r"con-duct \d+\.\d+\.\d+", output_str)


def test_cmd_help() -> None:
    out = subprocess.check_output(["duct", "ps", "--help"])
    assert "ps [options]" in str(out)
    assert "usage: duct [-h]" not in str(out)


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
        assert "duct: error: unrecognized arguments: --unknown" in str(e.stdout)


def test_duct_missing_cmd() -> None:
    try:
        subprocess.check_output(
            ["duct", "--sample-interval", "1"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        assert "duct: error: the following arguments are required: command" in str(
            e.stdout
        )


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
    """Test that --mode argument is parsed correctly."""
    parser = build_parser()
    cmd_args = mode_arg + ["echo", "test"]
    args = parser.parse_args(cmd_args)
    # When no mode is provided, it won't be in args due to argparse.SUPPRESS
    if mode_arg:
        assert hasattr(args, "mode")
        assert str(args.mode) == expected_mode
    else:
        # Default case - mode won't be in args namespace
        assert not hasattr(args, "mode")


def test_mode_invalid_value() -> None:
    """Test that invalid --mode values are rejected."""
    try:
        subprocess.check_output(
            ["duct", "--mode", "invalid-mode", "echo", "test"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with invalid mode value")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        # Enum shows class name but argparse includes the choices
        assert "invalid SessionMode value: 'invalid-mode'" in str(e.stdout)


# TODO pytest parametrize
def test_message_parsing() -> None:
    """Test that -m/--message flag is correctly parsed."""
    parser = build_parser()

    # Test short flag
    args = parser.parse_args(["-m", "test message", "echo", "hello"])
    assert args.message == "test message"
    assert args.command == "echo"
    assert args.command_args == ["hello"]

    # Test long flag
    args = parser.parse_args(["--message", "another message", "ls"])
    assert args.message == "another message"
    assert args.command == "ls"

    # Test without message (should not have attribute due to SUPPRESS)
    args = parser.parse_args(["echo", "hello"])
    assert not hasattr(args, "message")


def test_parser_arguments() -> None:
    """Test that parser accepts all expected arguments."""
    parser = build_parser()

    # Test that all main arguments are accepted
    args = parser.parse_args(
        [
            "--output-prefix",
            "/tmp/test",
            "--sample-interval",
            "2",
            "--report-interval",
            "10",
            "--capture-outputs",
            "all",
            "--mode",
            "new-session",
            "-m",
            "test message",
            "--log-level",
            "DEBUG",
            "--config",
            "/path/to/config.json",
            "echo",
            "hello",
        ]
    )

    assert args.output_prefix == "/tmp/test"
    assert args.sample_interval == 2
    assert args.report_interval == 10
    assert args.capture_outputs == Outputs.ALL
    assert str(args.mode) == "new-session"
    assert args.message == "test message"
    assert args.log_level == "DEBUG"
    assert args.config == "/path/to/config.json"
    assert args.command == "echo"
    assert args.command_args == ["hello"]

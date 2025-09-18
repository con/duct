import re
import subprocess
import pytest
from con_duct.__main__ import build_parser


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


@pytest.mark.parametrize(
    "cli_args,expected_key,expected_value",
    [
        # Message parsing tests
        (["-m", "test message", "echo", "hello"], "message", "test message"),
        (["-m", "test message", "echo", "hello"], "command", "echo"),
        (["-m", "test message", "echo", "hello"], "command_args", ["hello"]),
        (["--message", "another message", "ls"], "message", "another message"),
        (["--message", "another message", "ls"], "command", "ls"),
        (["--message", "another message", "ls"], "command_args", []),
        # Comprehensive argument parsing tests
        (
            ["--output-prefix", "/tmp/test", "echo", "test"],
            "output_prefix",
            "/tmp/test",
        ),
        (["--sample-interval", "2", "echo", "test"], "sample_interval", 2),
        (["--report-interval", "10", "echo", "test"], "report_interval", 10),
        (["--log-level", "DEBUG", "echo", "test"], "log_level", "DEBUG"),
        (
            ["--config", "/path/to/config.json", "echo", "test"],
            "config",
            "/path/to/config.json",
        ),
        # Basic command parsing
        (["echo", "hello"], "command", "echo"),
        (["echo", "hello"], "command_args", ["hello"]),
    ],
)
def test_argument_parsing(cli_args: list, expected_key: str, expected_value) -> None:
    """Test that parser correctly handles various argument combinations."""
    parser = build_parser()
    args = parser.parse_args(cli_args)

    assert getattr(args, expected_key) == expected_value


@pytest.mark.parametrize(
    "cli_args,expected_key,expected_value",
    [
        (["--capture-outputs", "all", "echo", "test"], "capture_outputs", "all"),
        (["--capture-outputs", "stderr", "echo", "test"], "capture_outputs", "stderr"),
        (["--outputs", "stdout", "echo", "test"], "outputs", "stdout"),
        (["--outputs", "none", "echo", "test"], "outputs", "none"),
        (
            ["--record-types", "system-summary", "echo", "test"],
            "record_types",
            "system-summary",
        ),
        (
            ["--record-types", "processes-samples", "echo", "test"],
            "record_types",
            "processes-samples",
        ),
        (["--mode", "new-session", "echo", "test"], "mode", "new-session"),
        (["--mode", "current-session", "echo", "test"], "mode", "current-session"),
    ],
)
def test_enum_argument_parsing(
    cli_args: list, expected_key: str, expected_value: str
) -> None:
    """Test that parser correctly handles enum arguments."""
    parser = build_parser()
    args = parser.parse_args(cli_args)
    # For enums, compare string representation
    assert str(getattr(args, expected_key)) == expected_value


@pytest.mark.parametrize(
    "attribute_name",
    [
        "message",
        "output_prefix",
        "sample_interval",
        "report_interval",
        "capture_outputs",
        "outputs",
        "record_types",
        "mode",
        "log_level",
        "colors",
        "clobber",
        "fail_time",
        "summary_format",
        "quiet",
    ],
)
def test_optional_attributes_absent_without_flags(attribute_name: str) -> None:
    """Test that optional attributes are absent when their flags aren't provided."""
    parser = build_parser()
    args = parser.parse_args(["echo", "hello"])
    assert not hasattr(args, attribute_name)

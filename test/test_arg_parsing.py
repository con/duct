import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest import mock
import pytest
from con_duct.__main__ import HAS_JSONARGPARSE, Arguments


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
    """Test that --mode argument is parsed correctly with both long and short forms."""
    # Import here to avoid module loading issues in tests
    from con_duct.__main__ import Arguments

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


@pytest.mark.skipif(
    not HAS_JSONARGPARSE, reason="Env var support requires jsonargparse"
)
def test_message_env_variable() -> None:
    """Test that DUCT_MESSAGE environment variable is used as default."""
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        args = Arguments.from_argv(["echo", "hello"])
        assert args.message == "env message"

    # Command line should override env variable
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        args = Arguments.from_argv(["-m", "cli message", "echo", "hello"])
        assert args.message == "cli message"


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_config_file_loading() -> None:
    """Test that config files are loaded when jsonargparse is available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text("sample_interval: 2.5\n" 'message: "from config"\n')
        args = Arguments.from_argv(["--config", str(config_file), "echo", "hello"])
        assert args.sample_interval == 2.5
        assert args.message == "from config"


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_config_precedence() -> None:
    """Test precedence: config < env < CLI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text(
            "sample_interval: 2.5\n"
            "report_interval: 120.0\n"
            'message: "from config"\n'
        )
        # Config value should be used
        args = Arguments.from_argv(["--config", str(config_file), "echo", "hello"])
        assert args.sample_interval == 2.5
        assert args.report_interval == 120.0
        assert args.message == "from config"

        # Env var should override config
        with mock.patch.dict(os.environ, {"DUCT_SAMPLE_INTERVAL": "5.0"}):
            args = Arguments.from_argv(["--config", str(config_file), "echo", "hello"])
            assert args.sample_interval == 5.0
            assert args.report_interval == 120.0  # Still from config

        # CLI should override both env and config
        with mock.patch.dict(os.environ, {"DUCT_SAMPLE_INTERVAL": "5.0"}):
            args = Arguments.from_argv(
                [
                    "--config",
                    str(config_file),
                    "--sample-interval",
                    "10.0",
                    "echo",
                    "hello",
                ]
            )
            assert args.sample_interval == 10.0


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_multiple_config_files_merge() -> None:
    """Test that multiple config files are merged correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config1 = Path(tmpdir) / "config1.yaml"
        config1.write_text("sample_interval: 2.5\n" 'message: "from config1"\n')
        config2 = Path(tmpdir) / "config2.yaml"
        config2.write_text("report_interval: 120.0\n" 'message: "from config2"\n')
        args = Arguments.from_argv(
            ["--config", str(config1), "--config", str(config2), "echo", "hello"]
        )
        assert args.sample_interval == 2.5  # From config1
        assert args.report_interval == 120.0  # From config2
        assert args.message == "from config2"  # config2 overrides config1


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_missing_config_file_ignored() -> None:
    """Test that missing config files are silently ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = Path(tmpdir) / "nonexistent.yaml"
        # Should not raise an error
        args = Arguments.from_argv(["--config", str(nonexistent), "echo", "hello"])
        assert args.command == "echo"


@pytest.mark.skipif(HAS_JSONARGPARSE, reason="Test fallback mode")
def test_fallback_mode_without_jsonargparse() -> None:
    """Test that duct works without jsonargparse (fallback mode)."""
    args = Arguments.from_argv(["echo", "hello"])
    assert args.command == "echo"
    assert args.sample_interval == 1.0  # Default value

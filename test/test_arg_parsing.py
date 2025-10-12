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
        assert "unrecognized arguments" in str(e.stdout).lower()
        assert "--unknown" in str(e.stdout)


def test_duct_missing_cmd() -> None:
    try:
        subprocess.check_output(
            ["duct", "--sample-interval", "1"], stderr=subprocess.STDOUT
        )
        pytest.fail("Command should have failed with a non-zero exit code")
    except subprocess.CalledProcessError as e:
        assert e.returncode == 2
        # argparse: `error: the following arguments are required: command`
        # jsonargparse: Key "command" is required but not included
        assert "command" in str(e.stdout).lower()
        assert "required" in str(e.stdout).lower()


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
        assert "invalid parse value: 'invalid-mode'" in str(e.stdout)


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
def test_config_precedence(no_test_config: None) -> None:  # noqa: U100
    """Test precedence: CLI args > env vars > config files > defaults."""
    from con_duct import __main__

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / ".duct" / "config.yaml"
        config_file.parent.mkdir()
        config_file.write_text("sample_interval: 2.5\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            # Patch to only use .duct/config.yaml in this temp directory
            with mock.patch.object(
                __main__, "DEFAULT_CONFIG_PATHS", [".duct/config.yaml"]
            ):
                # Config value should be used from default location
                args = Arguments.from_argv(["echo", "hello"])
                assert args.sample_interval == 2.5

                # Env var should override config
                with mock.patch.dict(os.environ, {"DUCT_SAMPLE_INTERVAL": "5.0"}):
                    args = Arguments.from_argv(["echo", "hello"])
                    assert args.sample_interval == 5.0

                # CLI should override both env and config
                with mock.patch.dict(os.environ, {"DUCT_SAMPLE_INTERVAL": "5.0"}):
                    args = Arguments.from_argv(
                        ["--sample-interval", "10.0", "echo", "hello"]
                    )
                    assert args.sample_interval == 10.0
        finally:
            os.chdir(old_cwd)


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_duct_config_paths_env_var(no_test_config: None) -> None:  # noqa: U100
    """Test that DUCT_CONFIG_PATHS environment variable overrides default paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config1 = Path(tmpdir) / "config1.yaml"
        config1.write_text("sample_interval: 3.5\n" 'message: "from config1"\n')
        config2 = Path(tmpdir) / "config2.yaml"
        config2.write_text("report_interval: 120.0\n" 'message: "from config2"\n')

        config_paths = f"{config1}:{config2}"
        with mock.patch.dict(
            os.environ, {"DUCT_CONFIG_PATHS": config_paths}, clear=False
        ):
            args = Arguments.from_argv(["echo", "hello"])
            assert args.sample_interval == 3.5  # From config1
            assert args.report_interval == 120.0  # From config2
            assert args.message == "from config2"  # config2 overrides config1


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_default_config_paths_missing_ignored(
    no_test_config: None,  # noqa: U100
) -> None:
    """Test that missing default config paths are silently ignored."""
    from con_duct import __main__

    nonexistent_paths = ["/tmp/duct_nonexistent_1.yaml", "/tmp/duct_nonexistent_2.yaml"]
    with mock.patch.object(__main__, "DEFAULT_CONFIG_PATHS", nonexistent_paths):
        args = Arguments.from_argv(["echo", "hello"])
        assert args.command == "echo"
        assert args.sample_interval == 1.0


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_default_config_in_cwd_loaded(no_test_config: None) -> None:  # noqa: U100
    """Test that .duct/config.yaml in cwd is loaded by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        duct_dir = Path(tmpdir) / ".duct"
        duct_dir.mkdir()
        config_file = duct_dir / "config.yaml"
        config_file.write_text("sample_interval: 7.5\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            args = Arguments.from_argv(["echo", "hello"])
            assert args.sample_interval == 7.5
        finally:
            os.chdir(old_cwd)


@pytest.mark.skipif(HAS_JSONARGPARSE, reason="Test fallback mode")
def test_fallback_mode_without_jsonargparse() -> None:
    """Test that duct works without jsonargparse (fallback mode)."""
    args = Arguments.from_argv(["echo", "hello"])
    assert args.command == "echo"
    assert args.sample_interval == 1.0  # Default value


@pytest.mark.parametrize(
    "record_types_arg,expected_value",
    [
        ([], "all"),  # default
        (["--record-types", "all"], "all"),
        (["--record-types", "system-summary"], "system-summary"),
        (["--record-types", "processes-samples"], "processes-samples"),
    ],
)
def test_record_types_argument_parsing(
    record_types_arg: list, expected_value: str
) -> None:
    """Test that --record-types argument with hyphenated values is parsed correctly."""
    from con_duct.__main__ import RecordTypes

    cmd_args = record_types_arg + ["echo", "test"]
    args = Arguments.from_argv(cmd_args)
    assert str(args.record_types) == expected_value
    # Verify it's actually an enum instance, not a string
    assert isinstance(args.record_types, RecordTypes)


def test_enum_defaults_are_enum_instances() -> None:
    """Test that enum defaults are enum instances, not strings."""
    from con_duct.__main__ import Outputs, RecordTypes, SessionMode

    args = Arguments.from_argv(["echo", "test"])
    # Verify defaults are enum instances
    assert isinstance(args.session_mode, SessionMode)
    assert isinstance(args.record_types, RecordTypes)
    assert isinstance(args.capture_outputs, Outputs)
    assert isinstance(args.outputs, Outputs)


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_enum_conversion_from_config_file(no_test_config: None) -> None:  # noqa: U100
    """Test that hyphenated enum values in config files are converted correctly."""
    from con_duct.__main__ import RecordTypes, SessionMode

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.yaml"
        config_file.write_text(
            "mode: current-session\n"
            "record_types: system-summary\n"
            "capture_outputs: stdout\n"
        )
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(config_file)}):
            args = Arguments.from_argv(["echo", "hello"])

            # Verify values are correct
            assert str(args.session_mode) == "current-session"
            assert str(args.record_types) == "system-summary"
            assert str(args.capture_outputs) == "stdout"

            # Verify they are enum instances, not strings
            assert isinstance(args.session_mode, SessionMode)
            assert isinstance(args.record_types, RecordTypes)
            # Verify enum methods work (would fail if they were strings)
            assert args.record_types.has_system_summary()
            assert not args.record_types.has_processes_samples()


@pytest.mark.skipif(not HAS_JSONARGPARSE, reason="jsonargparse not available")
def test_all_enum_values_from_config(no_test_config: None) -> None:  # noqa: U100
    """Test all possible enum values can be loaded from config files."""
    from con_duct.__main__ import RecordTypes, SessionMode

    test_cases = [
        ("mode: new-session\n", "session_mode", SessionMode.NEW_SESSION),
        ("mode: current-session\n", "session_mode", SessionMode.CURRENT_SESSION),
        ("record_types: all\n", "record_types", RecordTypes.ALL),
        (
            "record_types: system-summary\n",
            "record_types",
            RecordTypes.SYSTEM_SUMMARY,
        ),
        (
            "record_types: processes-samples\n",
            "record_types",
            RecordTypes.PROCESSES_SAMPLES,
        ),
    ]

    for config_content, attr_name, expected_value in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(config_content)
            with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(config_file)}):
                args = Arguments.from_argv(["echo", "test"])
                actual_value = getattr(args, attr_name)
                assert (
                    actual_value == expected_value
                ), f"Failed for {config_content.strip()}: got {actual_value}, expected {expected_value}"

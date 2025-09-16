"""Tests for the Config class and validation functions."""

import json
import os
import tempfile
from unittest import mock
import pytest
from con_duct.__main__ import (
    FIELD_SPECS,
    Config,
    SessionMode,
    build_parser,
    handle_dump_config,
)


class TestValidationFunctions:
    """Test validation helper functions."""

    def test_bool_from_str(self):
        """Test string to boolean conversion."""
        # True values
        assert Config.bool_from_str("true") is True
        assert Config.bool_from_str("True") is True
        assert Config.bool_from_str("TRUE") is True
        assert Config.bool_from_str("yes") is True
        assert Config.bool_from_str("Yes") is True
        assert Config.bool_from_str("1") is True

        # False values
        assert Config.bool_from_str("false") is False
        assert Config.bool_from_str("False") is False
        assert Config.bool_from_str("FALSE") is False
        assert Config.bool_from_str("no") is False
        assert Config.bool_from_str("No") is False
        assert Config.bool_from_str("0") is False

        # Invalid values
        with pytest.raises(ValueError):
            Config.bool_from_str("maybe")
        with pytest.raises(ValueError):
            Config.bool_from_str("2")
        with pytest.raises(ValueError):
            Config.bool_from_str("")

    def test_validate_positive(self):
        """Test positive number validation."""
        # Valid positive numbers
        assert Config.validate_positive(1) == 1
        assert Config.validate_positive(0.5) == 0.5
        assert Config.validate_positive(100) == 100

        # Invalid non-positive numbers
        with pytest.raises(ValueError, match="must be greater than 0"):
            Config.validate_positive(0)
        with pytest.raises(ValueError, match="must be greater than 0"):
            Config.validate_positive(-1)
        with pytest.raises(ValueError, match="must be greater than 0"):
            Config.validate_positive(-0.5)

    @pytest.mark.parametrize(
        "sample_interval,report_interval,should_raise,expected_message",
        [
            # Valid cases: report >= sample
            (1.0, 5.0, False, None),
            (2.0, 2.0, False, None),  # Equal is valid
            (0.5, 1.0, False, None),
            # Invalid cases: report < sample
            (
                5.0,
                4.0,
                True,
                "report-interval must be greater than or equal to sample-interval",
            ),
            (
                10.0,
                5.0,
                True,
                "report-interval must be greater than or equal to sample-interval",
            ),
            (
                3.5,
                2.1,
                True,
                "report-interval must be greater than or equal to sample-interval",
            ),
        ],
    )
    def test_validate_sample_report_interval(
        self, sample_interval, report_interval, should_raise, expected_message
    ):
        """Test sample/report interval validation."""
        if should_raise:
            with pytest.raises(ValueError, match=expected_message):
                Config.validate_sample_report_interval(sample_interval, report_interval)
        else:
            Config.validate_sample_report_interval(
                sample_interval, report_interval
            )  # Should not raise


class TestConfig:
    """Test Config class functionality."""

    def test_config_default_initialization(self):
        """Test Config initialization with defaults."""
        config = Config({})

        # Check some default values
        assert config.sample_interval == 0.5
        assert config.report_interval == 60.0
        assert config.capture_outputs == "all"
        assert config.mode == SessionMode.NEW_SESSION
        assert config.message == ""
        assert config.log_level == "INFO"

    def test_config_with_cli_args(self):
        """Test Config initialization with CLI arguments."""
        cli_args = {
            "sample_interval": 2.0,
            "report_interval": 120.0,
            "message": "test message",
            "log_level": "DEBUG",
        }
        config = Config(cli_args)

        assert config.sample_interval == 2.0
        assert config.report_interval == 120.0
        assert config.message == "test message"
        assert config.log_level == "DEBUG"

    def test_config_with_env_vars(self):
        """Test Config initialization with environment variables."""
        with mock.patch.dict(
            os.environ,
            {
                "DUCT_SAMPLE_INTERVAL": "3.0",
                "DUCT_REPORT_INTERVAL": "180.0",
                "DUCT_MESSAGE": "env message",
                "DUCT_LOG_LEVEL": "WARNING",
            },
        ):
            config = Config({})

            assert config.sample_interval == 3.0
            assert config.report_interval == 180.0
            assert config.message == "env message"
            assert config.log_level == "WARNING"

    def test_config_precedence(self):
        """Test configuration precedence: defaults < config file < env vars < CLI."""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "sample-interval": 10.0,
                "report-interval": 100.0,
                "message": "file message",
                "log-level": "ERROR",
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Test with config file (clear env vars to prevent conftest interference)
            with mock.patch.dict(os.environ, {"DUCT_CONFIG": config_file}, clear=True):
                config = Config({})
                assert config.sample_interval == 10.0
                assert config.message == "file message"

            # Test env vars override config file
            with mock.patch.dict(
                os.environ,
                {
                    "DUCT_CONFIG": config_file,
                    "DUCT_MESSAGE": "env message",
                    "DUCT_SAMPLE_INTERVAL": "15.0",
                },
                clear=True,
            ):
                config = Config({})
                assert config.sample_interval == 15.0
                assert config.message == "env message"

            # Test CLI args override everything
            with mock.patch.dict(
                os.environ,
                {
                    "DUCT_CONFIG": config_file,
                    "DUCT_MESSAGE": "env message",
                },
                clear=True,
            ):
                cli_args = {"message": "cli message", "sample_interval": 20.0}
                config = Config(cli_args)
                assert config.sample_interval == 20.0
                assert config.message == "cli message"

        finally:
            os.unlink(config_file)

    def test_config_invalid_json_file(self):
        """Test Config handles invalid JSON files gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            config_file = f.name

        try:
            with mock.patch.dict(os.environ, {"DUCT_CONFIG": config_file}, clear=True):
                with pytest.raises(SystemExit):
                    Config({})
        finally:
            os.unlink(config_file)

    def test_config_nonexistent_file(self):
        """Test Config handles nonexistent config files gracefully."""
        # Nonexistent file in DUCT_CONFIG should cause error
        # Clear env vars to test true defaults, then set only DUCT_CONFIG
        with mock.patch.dict(
            os.environ, {"DUCT_CONFIG": "/nonexistent/config.json"}, clear=True
        ):
            # Should log warning but not fail (uses defaults)
            config = Config({})
            assert (
                config.sample_interval == FIELD_SPECS["sample_interval"].default
            )  # default value

    def test_config_dump(self, capsys):
        """Test Config.dump_config() method."""
        config = Config({"message": "test"})
        config.dump_config()

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "values" in output
        assert "sources" in output
        assert output["values"]["message"] == "test"
        assert "CLI:" in output["sources"]["message"]


class TestHandleDumpConfig:
    """Test handle_dump_config function."""

    def test_handle_dump_config_exits(self):
        """Test that --dump-config causes early exit."""
        parser = build_parser()

        with pytest.raises(SystemExit) as exc_info:
            with mock.patch("sys.argv", ["duct", "--dump-config", "echo", "test"]):
                handle_dump_config(parser)

        assert exc_info.value.code == 0

    def test_handle_dump_config_no_flag(self):
        """Test that without --dump-config, function returns normally."""
        parser = build_parser()

        with mock.patch("sys.argv", ["duct", "echo", "test"]):
            result = handle_dump_config(parser)
            assert result is None  # Should return without raising


class TestBuildParser:
    """Test build_parser function."""

    def test_build_parser_creates_parser(self):
        """Test that build_parser creates a valid ArgumentParser."""
        parser = build_parser()

        # Check parser has expected arguments
        args = parser.parse_args(["echo", "test"])
        assert args.command == "echo"
        assert args.command_args == ["test"]

    def test_build_parser_includes_all_field_specs(self):
        """Test that parser includes all FieldSpec arguments."""
        parser = build_parser()

        # Test various arguments are accepted
        args = parser.parse_args(
            [
                "--output-prefix",
                "/tmp/test",
                "--sample-interval",
                "2",
                "--report-interval",
                "10",
                "--capture-outputs",
                "none",
                "--mode",
                "current-session",
                "-m",
                "test message",
                "--log-level",
                "DEBUG",
                "echo",
                "hello",
            ]
        )

        assert args.output_prefix == "/tmp/test"
        assert args.sample_interval == 2.0
        assert args.report_interval == 10.0
        assert args.capture_outputs == "none"
        assert str(args.mode) == "current-session"
        assert args.message == "test message"
        assert args.log_level == "DEBUG"

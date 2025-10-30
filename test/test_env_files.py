from __future__ import annotations
import os
from pathlib import Path
from unittest import mock
import pytest


@pytest.fixture
def temp_env_files(tmp_path: Path) -> dict[str, Path]:
    """Create temporary .env files for testing."""
    # System-level config
    system_env = tmp_path / "system.env"
    system_env.write_text("DUCT_LOG_LEVEL=WARNING\nDUCT_SAMPLE_INTERVAL=2.0\n")

    # User-level config
    user_env = tmp_path / "user.env"
    user_env.write_text("DUCT_LOG_LEVEL=DEBUG\nDUCT_REPORT_INTERVAL=120.0\n")

    # Project-level config
    project_env = tmp_path / "project.env"
    project_env.write_text("DUCT_LOG_LEVEL=INFO\nDUCT_MESSAGE=test message\n")

    return {
        "system": system_env,
        "user": user_env,
        "project": project_env,
    }


def test_load_env_files_basic(temp_env_files: dict[str, Path]) -> None:
    """Test basic .env file loading."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    config_paths = f"{temp_env_files['system']}:{temp_env_files['user']}"

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": config_paths}):
            load_duct_env_files()
            # User config should override system config
            assert os.environ.get("DUCT_LOG_LEVEL") == "DEBUG"
            assert os.environ.get("DUCT_SAMPLE_INTERVAL") == "2.0"
            assert os.environ.get("DUCT_REPORT_INTERVAL") == "120.0"


def test_load_env_files_precedence(temp_env_files: dict[str, Path]) -> None:
    """Test that later files override earlier files."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    config_paths = (
        f"{temp_env_files['system']}:"
        f"{temp_env_files['user']}:"
        f"{temp_env_files['project']}"
    )

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": config_paths}):
            load_duct_env_files()
            # Project should override user which overrides system
            assert os.environ.get("DUCT_LOG_LEVEL") == "INFO"
            assert os.environ.get("DUCT_MESSAGE") == "test message"
            # Values from earlier files that weren't overridden
            assert os.environ.get("DUCT_SAMPLE_INTERVAL") == "2.0"
            assert os.environ.get("DUCT_REPORT_INTERVAL") == "120.0"


def test_explicit_env_vars_win(temp_env_files: dict[str, Path]) -> None:
    """Test that explicit environment variables are not overridden by .env files."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    config_paths = f"{temp_env_files['project']}"

    # Set explicit env var
    with mock.patch.dict(
        os.environ, {"DUCT_LOG_LEVEL": "CRITICAL", "DUCT_CONFIG_PATHS": config_paths}
    ):
        load_duct_env_files()
        # Explicit env var should NOT be overridden
        assert os.environ.get("DUCT_LOG_LEVEL") == "CRITICAL"
        # But .env file should still set other vars
        assert os.environ.get("DUCT_MESSAGE") == "test message"


def test_missing_env_file_ignored(tmp_path: Path) -> None:
    """Test that missing .env files are silently ignored."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    nonexistent = tmp_path / "nonexistent.env"
    config_paths = str(nonexistent)

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": config_paths}):
            # Should not raise an exception
            load_duct_env_files()


def test_xdg_config_home_expansion(tmp_path: Path) -> None:
    """Test that ${XDG_CONFIG_HOME:-~/.config} syntax is expanded correctly."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    # Create a .env file in a custom XDG location
    xdg_dir = tmp_path / "xdg_config"
    xdg_dir.mkdir()
    duct_dir = xdg_dir / "duct"
    duct_dir.mkdir()
    env_file = duct_dir / ".env"
    env_file.write_text("DUCT_LOG_LEVEL=ERROR\n")

    config_paths = "${XDG_CONFIG_HOME:-~/.config}/duct/.env"

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": str(xdg_dir),
                "DUCT_CONFIG_PATHS": config_paths,
            },
        ):
            load_duct_env_files()
            assert os.environ.get("DUCT_LOG_LEVEL") == "ERROR"


def test_multiline_values(tmp_path: Path) -> None:
    """Test that multiline values in .env files are handled correctly."""
    pytest.importorskip("dotenv")
    from con_duct.cli import load_duct_env_files

    # Create .env file with multiline value
    env_file = tmp_path / "multiline.env"
    env_file.write_text('DUCT_MESSAGE="Line 1\nLine 2\nLine 3"\n')

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(env_file)}):
            load_duct_env_files()
            message = os.environ.get("DUCT_MESSAGE")
            assert message is not None
            assert "Line 1" in message
            assert "Line 2" in message
            assert "Line 3" in message


def test_without_python_dotenv() -> None:
    """Test graceful degradation when python-dotenv is not installed."""
    from con_duct.cli import load_duct_env_files

    # Mock ImportError for dotenv
    with mock.patch("builtins.__import__", side_effect=ImportError):
        # Should not raise an exception
        load_duct_env_files()


def test_early_logging_buffer(tmp_path: Path) -> None:
    """Test that log messages are buffered during .env loading."""
    pytest.importorskip("dotenv")
    from con_duct import cli

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    # Clear the buffer before testing
    cli._early_log_buffer.clear()

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(env_file)}):
            cli.load_duct_env_files()

    # Check that messages were buffered
    assert len(cli._early_log_buffer) > 0
    # Should have messages about searching and loading
    messages = [msg for level, msg in cli._early_log_buffer]
    assert any("Searching for .env files" in msg for msg in messages)
    assert any("Loading .env file" in msg for msg in messages)


def test_early_logging_replay(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Test that buffered messages are replayed through the logger."""
    pytest.importorskip("dotenv")
    import logging
    from con_duct import cli

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    # Clear the buffer and reload
    cli._early_log_buffer.clear()

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(env_file)}):
            cli.load_duct_env_files()

    # Buffer should have messages
    assert len(cli._early_log_buffer) > 0

    # Configure logging and replay
    with caplog.at_level(logging.DEBUG, logger="con-duct"):
        cli._replay_early_logs()

    # Check that messages were logged
    assert len(caplog.records) > 0
    logged_messages = [record.message for record in caplog.records]
    assert any("Searching for .env files" in msg for msg in logged_messages)

    # Buffer should be cleared after replay
    assert len(cli._early_log_buffer) == 0


def test_early_logging_respects_level(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that replayed messages respect the configured log level."""
    pytest.importorskip("dotenv")
    import logging
    from con_duct import cli

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    # Clear and reload
    cli._early_log_buffer.clear()

    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(env_file)}):
            cli.load_duct_env_files()

    # All buffered messages are DEBUG level
    assert all(level == "DEBUG" for level, _ in cli._early_log_buffer)

    # Replay at INFO level - DEBUG messages should NOT appear
    with caplog.at_level(logging.INFO, logger="con-duct"):
        cli._replay_early_logs()

    # Should have no DEBUG messages in the log
    assert len(caplog.records) == 0

    # Try again at DEBUG level
    cli._early_log_buffer.clear()
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch.dict(os.environ, {"DUCT_CONFIG_PATHS": str(env_file)}):
            cli.load_duct_env_files()

    with caplog.at_level(logging.DEBUG, logger="con-duct"):
        cli._replay_early_logs()

    # Now DEBUG messages should appear
    assert len(caplog.records) > 0

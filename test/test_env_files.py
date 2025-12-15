from __future__ import annotations
import logging
import os
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from con_duct import cli


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


def test_load_env_files_basic(
    temp_env_files: dict[str, Path], clean_env: pytest.MonkeyPatch
) -> None:
    """Test basic .env file loading."""
    pytest.importorskip("dotenv")

    config_paths = f"{temp_env_files['system']}{os.pathsep}{temp_env_files['user']}"
    clean_env.setenv("DUCT_CONFIG_PATHS", config_paths)

    cli.load_duct_env_files()
    # User config should override system config
    assert os.environ.get("DUCT_LOG_LEVEL") == "DEBUG"
    assert os.environ.get("DUCT_SAMPLE_INTERVAL") == "2.0"
    assert os.environ.get("DUCT_REPORT_INTERVAL") == "120.0"


def test_load_env_files_precedence(
    temp_env_files: dict[str, Path], clean_env: pytest.MonkeyPatch
) -> None:
    """Test that later files override earlier files."""
    pytest.importorskip("dotenv")

    config_paths = os.pathsep.join(
        [
            str(temp_env_files["system"]),
            str(temp_env_files["user"]),
            str(temp_env_files["project"]),
        ]
    )
    clean_env.setenv("DUCT_CONFIG_PATHS", config_paths)

    cli.load_duct_env_files()
    # Project should override user which overrides system
    assert os.environ.get("DUCT_LOG_LEVEL") == "INFO"
    assert os.environ.get("DUCT_MESSAGE") == "test message"
    # Values from earlier files that weren't overridden
    assert os.environ.get("DUCT_SAMPLE_INTERVAL") == "2.0"
    assert os.environ.get("DUCT_REPORT_INTERVAL") == "120.0"


def test_explicit_env_vars_win(
    temp_env_files: dict[str, Path], clean_env: pytest.MonkeyPatch
) -> None:
    """Test that explicit environment variables are not overridden by .env files."""
    pytest.importorskip("dotenv")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(temp_env_files["project"]))
    clean_env.setenv("DUCT_LOG_LEVEL", "CRITICAL")

    cli.load_duct_env_files()
    # Explicit env var should NOT be overridden
    assert os.environ.get("DUCT_LOG_LEVEL") == "CRITICAL"
    # But .env file should still set other vars
    assert os.environ.get("DUCT_MESSAGE") == "test message"


def test_missing_env_file_ignored(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that missing .env files are silently ignored."""
    pytest.importorskip("dotenv")

    nonexistent = tmp_path / "nonexistent.env"
    clean_env.setenv("DUCT_CONFIG_PATHS", str(nonexistent))

    # Should not raise an exception
    cli.load_duct_env_files()


def test_xdg_config_home_expansion(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that ${XDG_CONFIG_HOME:-~/.config} syntax is expanded correctly."""
    pytest.importorskip("dotenv")

    # Create a .env file in a custom XDG location
    xdg_dir = tmp_path / "xdg_config"
    xdg_dir.mkdir()
    duct_dir = xdg_dir / "duct"
    duct_dir.mkdir()
    env_file = duct_dir / ".env"
    env_file.write_text("DUCT_LOG_LEVEL=ERROR\n")

    clean_env.setenv("XDG_CONFIG_HOME", str(xdg_dir))
    clean_env.setenv("DUCT_CONFIG_PATHS", "${XDG_CONFIG_HOME:-~/.config}/duct/.env")

    cli.load_duct_env_files()
    assert os.environ.get("DUCT_LOG_LEVEL") == "ERROR"


def test_multiline_values(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    """Test that multiline values in .env files are handled correctly."""
    pytest.importorskip("dotenv")

    # Create .env file with multiline value
    env_file = tmp_path / "multiline.env"
    env_file.write_text('DUCT_MESSAGE="Line 1\nLine 2\nLine 3"\n')

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    cli.load_duct_env_files()
    message = os.environ.get("DUCT_MESSAGE")
    assert message is not None
    assert "Line 1" in message
    assert "Line 2" in message
    assert "Line 3" in message


def test_without_python_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test graceful degradation when python-dotenv is not installed."""
    # Setting module to None in sys.modules causes ImportError on import
    monkeypatch.setitem(sys.modules, "dotenv", None)

    log_buffer = cli.load_duct_env_files()

    # Should have a message about dotenv not being installed
    messages = [msg for level, msg in log_buffer]
    assert any("python-dotenv not installed" in msg for msg in messages)


def test_early_logging_buffer(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    """Test that log messages are buffered during .env loading."""
    pytest.importorskip("dotenv")

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    log_buffer = cli.load_duct_env_files()

    # Check that messages were buffered
    assert len(log_buffer) > 0
    # Should have messages about searching and loading
    messages = [msg for level, msg in log_buffer]
    assert any("Searching for .env files" in msg for msg in messages)
    assert any("Loading .env file" in msg for msg in messages)


def test_early_logging_replay(
    tmp_path: Path, clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that buffered messages are replayed through the logger."""
    pytest.importorskip("dotenv")

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    log_buffer = cli.load_duct_env_files()

    # Buffer should have messages
    assert len(log_buffer) > 0

    # Configure logging and replay
    with caplog.at_level(logging.DEBUG, logger="con-duct"):
        cli._replay_early_logs(log_buffer)

    # Check that messages were logged
    assert len(caplog.records) > 0
    logged_messages = [record.message for record in caplog.records]
    assert any("Searching for .env files" in msg for msg in logged_messages)


def test_early_logging_respects_level(
    tmp_path: Path, clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that replayed messages respect the configured log level."""
    pytest.importorskip("dotenv")

    # Create a test .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("TEST_VAR=test_value\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    log_buffer = cli.load_duct_env_files()

    # Buffer should have both DEBUG and INFO messages
    levels = {level for level, _ in log_buffer}
    assert "DEBUG" in levels  # "Searching for .env files"
    assert "INFO" in levels  # "Loading .env file"

    # Replay at WARNING level - neither DEBUG nor INFO should appear
    with caplog.at_level(logging.WARNING, logger="con-duct"):
        cli._replay_early_logs(log_buffer)

    assert len(caplog.records) == 0

    # Replay at INFO level - only INFO messages should appear
    caplog.clear()
    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    log_buffer2 = cli.load_duct_env_files()

    with caplog.at_level(logging.INFO, logger="con-duct"):
        cli._replay_early_logs(log_buffer2)

    assert len(caplog.records) > 0
    assert all(r.levelno >= logging.INFO for r in caplog.records)


def test_permission_denied_handling(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that permission denied errors are handled gracefully."""
    dotenv = pytest.importorskip("dotenv")

    # Create a .env file that exists (so it passes the exists() check)
    env_file = tmp_path / "unreadable.env"
    env_file.write_text("DUCT_LOG_LEVEL=DEBUG\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    # Mock load_dotenv to raise PermissionError (works even as root)
    with patch.object(
        dotenv, "load_dotenv", side_effect=PermissionError("Permission denied")
    ):
        # Should not raise an exception
        log_buffer = cli.load_duct_env_files()

    # Should have a WARNING message about permission denied
    messages = [msg for level, msg in log_buffer]
    assert any("Cannot read .env file" in msg for msg in messages)
    assert any("Permission denied" in msg for msg in messages)


def test_malformed_env_file_handling(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that malformed .env files (null bytes) are handled gracefully."""
    pytest.importorskip("dotenv")

    # Create a .env file with null bytes
    env_file = tmp_path / "malformed.env"
    env_file.write_bytes(b"DUCT_MESSAGE=before\x00after\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    # Should not raise an exception
    log_buffer = cli.load_duct_env_files()

    # Should have a WARNING message about malformed file
    messages = [msg for level, msg in log_buffer]
    assert any("Skipping malformed .env file" in msg for msg in messages)
    # The error message varies by python-dotenv version, so just check it's there
    assert any(level == "WARNING" for level, _ in log_buffer)


def test_invalid_utf8_env_file_handling(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that .env files with invalid UTF-8 are handled gracefully."""
    pytest.importorskip("dotenv")

    # Create a .env file with invalid UTF-8 bytes
    env_file = tmp_path / "bad_encoding.env"
    env_file.write_bytes(b"DUCT_MESSAGE=hello\xff\xfeworld\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    # Should not raise an exception
    log_buffer = cli.load_duct_env_files()

    # Should have a WARNING message about malformed file
    messages = [msg for level, msg in log_buffer]
    assert any("Skipping malformed .env file" in msg for msg in messages)
    assert any("utf-8" in msg.lower() or "unicode" in msg.lower() for msg in messages)


def test_default_config_paths_used(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that DEFAULT_CONFIG_PATHS is used when DUCT_CONFIG_PATHS is not set."""
    pytest.importorskip("dotenv")

    # Create a .env file at the project-level default path (.duct/.env)
    duct_dir = tmp_path / ".duct"
    duct_dir.mkdir()
    env_file = duct_dir / ".env"
    env_file.write_text("DUCT_TEST_DEFAULT_PATH=found\n")

    # Patch DEFAULT_CONFIG_PATHS to use our temp path
    clean_env.setattr(cli, "DEFAULT_CONFIG_PATHS", str(env_file))
    # Ensure DUCT_CONFIG_PATHS is not set (clean_env already handles this)

    cli.load_duct_env_files()
    assert os.environ.get("DUCT_TEST_DEFAULT_PATH") == "found"


def test_bare_variable_expansion(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    """Test that ${VAR} without default is expanded correctly."""
    pytest.importorskip("dotenv")

    # Create a .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("DUCT_TEST_BARE_VAR=found\n")

    # Set up path using bare ${VAR} syntax
    clean_env.setenv("MY_CONFIG_DIR", str(tmp_path))
    clean_env.setenv("DUCT_CONFIG_PATHS", "${MY_CONFIG_DIR}/test.env")

    cli.load_duct_env_files()
    assert os.environ.get("DUCT_TEST_BARE_VAR") == "found"


def test_empty_config_paths(clean_env: pytest.MonkeyPatch) -> None:
    """Test that empty DUCT_CONFIG_PATHS is handled gracefully."""
    pytest.importorskip("dotenv")

    clean_env.setenv("DUCT_CONFIG_PATHS", "")

    # Should not raise an exception
    log_buffer = cli.load_duct_env_files()

    # Should have logged that no files were found
    messages = [msg for level, msg in log_buffer]
    assert any("No .env files found" in msg for msg in messages)


def test_tilde_expansion(tmp_path: Path, clean_env: pytest.MonkeyPatch) -> None:
    """Test that ~ is expanded to home directory in paths."""
    pytest.importorskip("dotenv")

    # Create a .env file
    env_file = tmp_path / "test.env"
    env_file.write_text("DUCT_TEST_TILDE=found\n")

    # Temporarily change HOME to our temp directory
    clean_env.setenv("HOME", str(tmp_path))
    clean_env.setenv("DUCT_CONFIG_PATHS", "~/test.env")

    cli.load_duct_env_files()
    assert os.environ.get("DUCT_TEST_TILDE") == "found"


def test_env_values_flow_to_argparse(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that .env values are picked up by argparse defaults."""
    pytest.importorskip("dotenv")

    # Create a .env file with duct settings
    env_file = tmp_path / "test.env"
    env_file.write_text("DUCT_SAMPLE_INTERVAL=99.5\nDUCT_REPORT_INTERVAL=300.0\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    # Load .env files (normally called at start of main())
    cli.load_duct_env_files()

    # Now parse args - the defaults should come from env vars set by .env
    args = cli._create_run_parser().parse_args(["echo", "test"])

    assert args.sample_interval == 99.5
    assert args.report_interval == 300.0


def test_env_log_level_flows_to_argparse(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that DUCT_LOG_LEVEL from .env is picked up by the common parser."""
    pytest.importorskip("dotenv")

    # Create a .env file with log level
    env_file = tmp_path / "test.env"
    env_file.write_text("DUCT_LOG_LEVEL=DEBUG\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    # Load .env files
    cli.load_duct_env_files()

    # Parse using main() flow - log_level is in the common parser
    args = cli._create_common_parser().parse_args([])

    assert args.log_level == "DEBUG"


def test_whitespace_in_config_paths(
    tmp_path: Path, clean_env: pytest.MonkeyPatch
) -> None:
    """Test that paths with spaces are handled correctly."""
    pytest.importorskip("dotenv")

    # Create a directory with spaces in the name
    spaced_dir = tmp_path / "path with spaces"
    spaced_dir.mkdir()
    env_file = spaced_dir / "test.env"
    env_file.write_text("DUCT_TEST_SPACES=found\n")

    clean_env.setenv("DUCT_CONFIG_PATHS", str(env_file))

    cli.load_duct_env_files()
    assert os.environ.get("DUCT_TEST_SPACES") == "found"

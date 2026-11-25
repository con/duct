import argparse
import os
import platform
import re
import subprocess
from typing import Any, Optional
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
import pytest
from con_duct import cli
from con_duct.cli import EXIT_BROKEN_PIPE, _create_ls_parser, _create_run_parser

SYSTEM = platform.system()


class TestSuiteHelpers(unittest.TestCase):

    def test_execute_returns_int(self) -> None:
        def return_non_int(*_args: Any) -> str:
            return "NOPE"

        args = argparse.Namespace(
            command="invalid",
            file_path="dummy.json",
            func=return_non_int,
            log_level="INFO",
        )
        with pytest.raises(TypeError):
            cli.execute(args)

    @patch("con_duct.cli.argparse.ArgumentParser")
    def test_parser_mock_sanity(self, mock_parser: MagicMock) -> None:
        mock_args = MagicMock
        mock_args.command = None
        mock_parser.parse_args.return_value = mock_args
        argv = ["/path/to/con-duct", "plot", "--help"]
        cli.main(argv)
        mock_parser.return_value.print_help.assert_called_once()

    @patch("con_duct.cli.sys.exit", new_callable=MagicMock)
    @patch("con_duct.cli.sys.stderr", new_callable=MagicMock)
    @patch("con_duct.cli.sys.stdout", new_callable=MagicMock)
    def test_parser_sanity_green(
        self, mock_stdout: MagicMock, mock_stderr: MagicMock, mock_exit: MagicMock
    ) -> None:
        argv = ["--help"]
        cli.main(argv)
        # [0][1][0]: [first call][positional args set(0 is self)][first positional]
        out = mock_stdout.write.mock_calls[0][1][0]
        assert "usage: con-duct <command> [options]" in out
        mock_stderr.write.assert_not_called()
        mock_exit.assert_called_once_with(0)

    @patch("con_duct.cli.sys.exit", new_callable=MagicMock)
    @patch("con_duct.cli.sys.stderr", new_callable=MagicMock)
    @patch("con_duct.cli.sys.stdout", new_callable=MagicMock)
    def test_parser_sanity_red(
        self, mock_stdout: MagicMock, mock_stderr: MagicMock, mock_exit: MagicMock
    ) -> None:
        argv = ["--fakehelp"]
        cli.main(argv)
        # [0][1][0]: [first call][positional args set(0 is self)][first positional]
        out = mock_stdout.write.mock_calls[0][1][0]
        assert "usage: con-duct <command> [options]" in out
        mock_stderr.write.ssert_not_called()
        # First call
        assert (
            "usage: con-duct <command> [options]"
            in mock_stderr.write.mock_calls[0][1][0]
        )
        # second call
        assert "--fakehelp" in mock_stderr.write.mock_calls[1][1][0]
        mock_exit.assert_called_once_with(2)


def test_duct_help() -> None:
    out = subprocess.check_output(["duct", "--help", "ps"])
    output_str = out.decode("utf-8")
    # duct delegates to con-duct run, so usage shows con-duct run
    assert "usage: con-duct run" in output_str
    # Help text should mention both entry points
    assert "'duct' or 'con-duct run'" in output_str


def test_duct_version() -> None:
    out = subprocess.check_output(["duct", "--version"])
    output_str = out.decode("utf-8").strip()
    # duct now delegates to con-duct run, so version shows con-duct with full prog name
    assert output_str.startswith("con-duct ")
    # Check that it has a version pattern (version appears after prog name)
    assert re.search(r"\d+\.\d+\.\d+", output_str)


@pytest.mark.parametrize("subcommand", [None, "run", "ls", "pp", "plot"])
def test_con_duct_version(subcommand: Optional[str]) -> None:
    cmd = ["con-duct"] + ([subcommand] if subcommand else []) + ["--version"]
    out = subprocess.check_output(cmd)
    output_str = out.decode("utf-8").strip()
    expected_prefix = f"con-duct {subcommand}" if subcommand else "con-duct"
    assert output_str.startswith(expected_prefix)
    assert re.search(r"\d+\.\d+\.\d+", output_str)


@pytest.mark.skipif(SYSTEM != "Linux", reason="Test specific to Linux behavior")
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


@pytest.mark.skipif(SYSTEM != "Linux", reason="Test specific to Linux behavior")
def test_abbreviation_disabled() -> None:
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
    parser = _create_run_parser()
    args = parser.parse_args(cmd_args)
    assert str(args.mode) == expected_mode


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
    parser = _create_run_parser()

    # Test short flag
    args = parser.parse_args(["-m", "test message", "echo", "hello"])
    assert args.message == "test message"
    assert args.command == "echo"
    assert args.command_args == ["hello"]

    # Test long flag
    args = parser.parse_args(["--message", "another message", "ls"])
    assert args.message == "another message"
    assert args.command == "ls"

    # Test without message (should be empty string)
    args = parser.parse_args(["echo", "hello"])
    assert args.message == ""


def test_message_env_variable() -> None:
    """Test that DUCT_MESSAGE environment variable is used as default."""
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        parser = _create_run_parser()
        args = parser.parse_args(["echo", "hello"])
        assert args.message == "env message"

    # Command line should override env variable
    with mock.patch.dict(os.environ, {"DUCT_MESSAGE": "env message"}):
        parser = _create_run_parser()
        args = parser.parse_args(["-m", "cli message", "echo", "hello"])
        assert args.message == "cli message"


def test_ls_sort_by_parsing() -> None:
    """--sort-by accepts one or more known fields and defaults to None."""
    parser = _create_ls_parser()

    assert parser.parse_args([]).sort_by is None
    assert parser.parse_args(["--sort-by", "prefix"]).sort_by == ["prefix"]
    assert parser.parse_args(["--sort-by", "command", "prefix"]).sort_by == [
        "command",
        "prefix",
    ]


def test_ls_sort_by_rejects_unknown_field(capsys: pytest.CaptureFixture) -> None:
    parser = _create_ls_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--sort-by", "not_a_field"])
    assert "invalid choice" in capsys.readouterr().err


def test_main_exits_with_the_subcommand_returncode() -> None:
    """main() hands the subcommand's return code to sys.exit()."""
    with patch("con_duct.cli.ls", return_value=3):
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["ls", "/no/such/file_info.json"])

    assert excinfo.value.code == 3


def test_broken_pipe_exits_without_traceback() -> None:
    """`con-duct ls | head` must not end in a BrokenPipeError traceback."""

    def raise_broken_pipe(_args: Any) -> int:
        raise BrokenPipeError(32, "Broken pipe")

    argv = ["ls", "/no/such/file_info.json"]
    # do not really point our stdout at /dev/null -- pytest is reading it
    with patch("con_duct.cli.os.dup2") as mock_dup2:
        with patch("con_duct.cli.ls", raise_broken_pipe):
            with pytest.raises(SystemExit) as excinfo:
                cli.main(argv)

    assert excinfo.value.code == EXIT_BROKEN_PIPE
    mock_dup2.assert_called_once()


def test_broken_pipe_survives_a_stdout_without_fileno() -> None:
    """Redirecting stdout to /dev/null is best effort, not a second failure."""
    fake_stdout = MagicMock()
    fake_stdout.fileno.side_effect = ValueError("no fileno")

    with patch("con_duct.cli.sys.stdout", fake_stdout):
        with pytest.raises(SystemExit) as excinfo:
            cli._exit_broken_pipe()

    assert excinfo.value.code == EXIT_BROKEN_PIPE

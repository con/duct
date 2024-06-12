from __future__ import annotations
import subprocess
from unittest.mock import MagicMock, call, patch
from utils import MockStream
from duct.__main__ import Outputs, prepare_outputs


@patch("sys.stdout", new_callable=MockStream)
def test_prepare_outputs_all_stdout(mock_stdout: MockStream) -> None:
    output_prefix = "test_outputs_"
    with patch("duct.__main__.TailPipe") as mock_tee_stream, patch(
        "builtins.open", new_callable=MagicMock
    ) as mock_open:
        mock_tee_stream.return_value.start = MagicMock()
        stdout, stderr = prepare_outputs(
            Outputs.ALL, Outputs.STDOUT, output_prefix, clobber=True
        )
        mock_tee_stream.assert_called_with(
            f"{output_prefix}stdout", buffer=mock_stdout.buffer
        )
        assert stdout == mock_tee_stream.return_value
        assert stderr == mock_open.return_value


@patch("sys.stderr", new_callable=MockStream)
def test_prepare_outputs_all_stderr(mock_stderr: MockStream) -> None:
    output_prefix = "test_outputs_"
    with patch("duct.__main__.TailPipe") as mock_tee_stream, patch(
        "builtins.open", new_callable=MagicMock
    ) as mock_open:
        mock_tee_stream.return_value.start = MagicMock()
        stdout, stderr = prepare_outputs(
            Outputs.ALL, Outputs.STDERR, output_prefix, clobber=True
        )
        mock_tee_stream.assert_called_with(
            f"{output_prefix}stderr", buffer=mock_stderr.buffer
        )
        assert stdout == mock_open.return_value
        assert stderr == mock_tee_stream.return_value


def test_prepare_outputs_all_none() -> None:
    output_prefix = "test_outputs_"
    with patch("builtins.open", new_callable=MagicMock) as mock_open:
        stdout, stderr = prepare_outputs(
            Outputs.ALL, Outputs.NONE, output_prefix, clobber=True
        )
        calls = [
            call(f"{output_prefix}stdout", "w"),
            call(f"{output_prefix}stderr", "w"),
        ]
        mock_open.assert_has_calls(calls, any_order=True)
        assert stdout == mock_open.return_value
        assert stderr == mock_open.return_value


def test_prepare_outputs_none_stdout() -> None:
    output_prefix = "test_outputs_"
    stdout, stderr = prepare_outputs(
        Outputs.NONE, Outputs.STDOUT, output_prefix, clobber=True
    )
    assert stdout is None
    assert stderr == subprocess.DEVNULL


def test_prepare_outputs_none_stderr() -> None:
    output_prefix = "test_outputs_"
    stdout, stderr = prepare_outputs(
        Outputs.NONE, Outputs.STDERR, output_prefix, clobber=True
    )
    assert stderr is None
    assert stdout == subprocess.DEVNULL


@patch("sys.stderr", new_callable=MockStream)
@patch("sys.stdout", new_callable=MockStream)
def test_prepare_outputs_all_all(
    mock_stdout: MockStream, mock_stderr: MockStream
) -> None:
    output_prefix = "test_outputs_"
    with patch("duct.__main__.TailPipe") as mock_tee_stream:
        mock_tee_stream.return_value.start = MagicMock()
        stdout, stderr = prepare_outputs(
            Outputs.ALL, Outputs.ALL, output_prefix, clobber=True
        )
        assert stdout == mock_tee_stream.return_value
        assert stderr == mock_tee_stream.return_value
        calls = [
            call(f"{output_prefix}stdout", buffer=mock_stdout.buffer),
            call(f"{output_prefix}stderr", buffer=mock_stderr.buffer),
        ]
        mock_tee_stream.assert_has_calls(calls, any_order=True)

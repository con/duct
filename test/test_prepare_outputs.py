from __future__ import annotations
import subprocess
from unittest.mock import MagicMock, call, patch
from utils import MockStream
from con_duct.__main__ import LogPaths, Outputs, prepare_outputs


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_none_output_none(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.NONE, Outputs.NONE, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_not_called()
    assert stdout == subprocess.DEVNULL
    assert stderr == subprocess.DEVNULL


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_none_output_stdout(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.NONE, Outputs.STDOUT, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_not_called()
    assert stdout is None
    assert stderr == subprocess.DEVNULL


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_none_output_stderr(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.NONE, Outputs.STDERR, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_not_called()
    assert stdout == subprocess.DEVNULL
    assert stderr is None


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_none_output_all(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.NONE, Outputs.ALL, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_not_called()
    assert stdout is None
    assert stderr is None


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stdout_output_none(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDOUT, Outputs.NONE, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_called_once_with(mock_log_paths.stdout, "w")
    assert stdout == mock_open.return_value
    assert stderr == subprocess.DEVNULL


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stdout_output_stdout(
    mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDOUT, Outputs.STDOUT, mock_log_paths)
    mock_tee_stream.assert_called_once_with(
        mock_log_paths.stdout, buffer=mock_stdout.buffer
    )
    mock_open.assert_not_called()
    assert stdout == mock_tee_stream.return_value
    assert stderr == subprocess.DEVNULL


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stdout_output_stderr(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDOUT, Outputs.STDERR, mock_log_paths)
    mock_open.assert_called_once_with(mock_log_paths.stdout, "w")
    mock_tee_stream.assert_not_called()
    assert stdout == mock_open.return_value
    assert stderr is None


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stdout_output_all(
    mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDOUT, Outputs.ALL, mock_log_paths)
    mock_tee_stream.assert_called_once_with(
        mock_log_paths.stdout, buffer=mock_stdout.buffer
    )
    mock_open.assert_not_called()
    assert stdout == mock_tee_stream.return_value
    assert stderr is None


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stderr_output_none(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDERR, Outputs.NONE, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_called_once_with(mock_log_paths.stderr, "w")
    assert stdout == subprocess.DEVNULL
    assert stderr == mock_open.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stderr_output_stdout(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDERR, Outputs.STDOUT, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_called_once_with(mock_log_paths.stderr, "w")
    assert stdout is None
    assert stderr == mock_open.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stderr_output_stderr(
    _mock_stdout: MockStream,
    mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDERR, Outputs.STDERR, mock_log_paths)
    mock_tee_stream.assert_called_once_with(
        mock_log_paths.stderr, buffer=mock_stderr.buffer
    )
    mock_open.assert_not_called()
    assert stdout == subprocess.DEVNULL
    assert stderr == mock_tee_stream.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_stderr_output_all(
    _mock_stdout: MockStream,
    mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.STDERR, Outputs.ALL, mock_log_paths)
    mock_tee_stream.assert_called_once_with(
        mock_log_paths.stderr, buffer=mock_stderr.buffer
    )
    mock_open.assert_not_called()
    assert stdout is None
    assert stderr == mock_tee_stream.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_all_output_none(
    _mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.ALL, Outputs.NONE, mock_log_paths)
    mock_tee_stream.assert_not_called()
    mock_open.assert_has_calls(
        [call(mock_log_paths.stdout, "w"), call(mock_log_paths.stderr, "w")]
    )
    assert stdout == mock_open.return_value
    assert stderr == mock_open.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_all_output_stdout(
    mock_stdout: MockStream,
    _mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.ALL, Outputs.STDOUT, mock_log_paths)
    mock_tee_stream.assert_called_with(mock_log_paths.stdout, buffer=mock_stdout.buffer)
    mock_open.assert_called_once_with(mock_log_paths.stderr, "w")
    assert stdout == mock_tee_stream.return_value
    assert stderr == mock_open.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_all_output_stderr(
    _mock_stdout: MockStream,
    mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.ALL, Outputs.STDERR, mock_log_paths)
    mock_tee_stream.assert_called_once_with(
        mock_log_paths.stderr, buffer=mock_stderr.buffer
    )
    mock_open.assert_called_once_with(mock_log_paths.stdout, "w")
    assert stdout == mock_open.return_value
    assert stderr == mock_tee_stream.return_value


@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct.__main__.TailPipe")
@patch("con_duct.__main__.LogPaths")
@patch("con_duct.__main__.sys.stderr", new_callable=MockStream)
@patch("con_duct.__main__.sys.stdout", new_callable=MockStream)
def test_prepare_outputs_capture_all_output_all(
    mock_stdout: MockStream,
    mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(Outputs.ALL, Outputs.ALL, mock_log_paths)
    mock_tee_stream.assert_has_calls(
        [
            call(mock_log_paths.stdout, buffer=mock_stdout.buffer),
            call(mock_log_paths.stderr, buffer=mock_stderr.buffer),
        ],
        any_order=True,
    )
    assert stdout == mock_tee_stream.return_value
    assert stderr == mock_tee_stream.return_value
    mock_open.assert_not_called()

from __future__ import annotations
import itertools
import subprocess
from typing import Callable
from unittest.mock import MagicMock, call, patch
import pytest
from utils import MockStream
from con_duct._models import LogPaths, Outputs
from con_duct._output import prepare_outputs

_STREAMS: list[tuple[str, Callable[[Outputs], bool]]] = [
    ("stdout", Outputs.has_stdout),
    ("stderr", Outputs.has_stderr),
]


@pytest.mark.parametrize(
    "capture_outputs,outputs", list(itertools.product(Outputs, Outputs))
)
@patch("builtins.open", new_callable=MagicMock)
@patch("con_duct._output.TailPipe")
@patch("con_duct._output.LogPaths")
@patch("con_duct._output.sys.stderr", new_callable=MockStream)
@patch("con_duct._output.sys.stdout", new_callable=MockStream)
def test_prepare_outputs(
    mock_stdout: MockStream,
    mock_stderr: MockStream,
    mock_LogPaths: LogPaths,
    mock_tee_stream: MagicMock,
    mock_open: MagicMock,
    capture_outputs: Outputs,
    outputs: Outputs,
) -> None:
    mock_log_paths = mock_LogPaths.create("mock_prefix")
    mock_tee_stream.return_value.start = MagicMock()
    stdout, stderr = prepare_outputs(capture_outputs, outputs, mock_log_paths)

    buffers = {"stdout": mock_stdout.buffer, "stderr": mock_stderr.buffer}
    actuals = {"stdout": stdout, "stderr": stderr}
    log_paths = {"stdout": mock_log_paths.stdout, "stderr": mock_log_paths.stderr}
    expected_open_calls = []
    expected_tee_calls = []

    for name, has_stream in _STREAMS:
        actual = actuals[name]
        if has_stream(capture_outputs):
            if has_stream(outputs):
                expected_tee_calls.append(call(log_paths[name], buffer=buffers[name]))
                assert actual == mock_tee_stream.return_value
            else:
                expected_open_calls.append(call(log_paths[name], "w"))
                assert actual == mock_open.return_value
        elif has_stream(outputs):
            assert actual is None
        else:
            assert actual == subprocess.DEVNULL

    if expected_open_calls:
        mock_open.assert_has_calls(expected_open_calls, any_order=True)
    assert mock_open.call_count == len(expected_open_calls)
    if expected_tee_calls:
        mock_tee_stream.assert_has_calls(expected_tee_calls, any_order=True)
    assert mock_tee_stream.call_count == len(expected_tee_calls)

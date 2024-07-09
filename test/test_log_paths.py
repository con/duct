from __future__ import annotations
from dataclasses import asdict
import os
import re
from unittest.mock import MagicMock, call, patch
import pytest
from con_duct.__main__ import LogPaths, Outputs


def test_log_paths_filesafe_datetime_prefix() -> None:
    log_paths = LogPaths.create("start_{datetime_filesafe}")
    pattern = r"^start_\d{4}\.\d{2}\.\d{2}T\d{2}\.\d{2}\.\d{2}.*"
    for path in asdict(log_paths).values():
        assert re.match(pattern, path) is not None


def test_log_paths_pid_prefix() -> None:
    prefix = "prefix_{pid}_"
    log_paths = LogPaths.create(prefix, pid=123456)
    assert log_paths.prefix == prefix.format(pid=123456)


@pytest.mark.parametrize(
    "path",
    [
        "directory/",
        "nested/directory/",
        "/abs/path/",
    ],
)
@patch("con_duct.__main__.os.makedirs")
@patch("con_duct.__main__.os.path.exists")
@patch("builtins.open")
def test_prepare_dir_paths_available(
    _mock_open: MagicMock, mock_exists: MagicMock, mock_mkdir: MagicMock, path: str
) -> None:
    mock_exists.return_value = False
    log_paths = LogPaths.create(path)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_mkdir.assert_called_once_with(path, exist_ok=True)


@pytest.mark.parametrize(
    "path",
    [
        "directory/pre_",
        "nested/directory/pre_",
        "/abs/path/pre_",
    ],
)
@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prefix_with_filepart_and_directory_part(
    mock_open: MagicMock, mock_mkdir: MagicMock, mock_exists: MagicMock, path: str
) -> None:
    mock_exists.return_value = False
    log_paths = LogPaths.create(path)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_mkdir.assert_called_once_with(os.path.dirname(path), exist_ok=True)
    expected_calls = [call(each, "w") for _name, each in log_paths]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prefix_with_filepart_only(
    mock_open: MagicMock, mock_mkdir: MagicMock, mock_exists: MagicMock
) -> None:
    mock_exists.return_value = False
    log_paths = LogPaths.create("filepartonly")
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_mkdir.assert_not_called()
    expected_calls = [call(each, "w") for _name, each in log_paths]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prepare_file_paths_available_all(
    mock_open: MagicMock, _mock_mkdir: MagicMock, mock_exists: MagicMock
) -> None:
    mock_exists.return_value = False
    prefix = "prefix_"
    log_paths = LogPaths.create(prefix)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    expected_calls = [call(each, "w") for _name, each in log_paths]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prepare_file_paths_available_stdout(
    mock_open: MagicMock, _mock_mkdir: MagicMock, mock_exists: MagicMock
) -> None:
    mock_exists.return_value = False
    prefix = "prefix_"
    log_paths = LogPaths.create(prefix)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.STDOUT)
    expected_calls = [
        call(each, "w") for name, each in log_paths if name != Outputs.STDERR
    ]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prepare_file_paths_available_stderr(
    mock_open: MagicMock, _mock_mkdir: MagicMock, mock_exists: MagicMock
) -> None:
    mock_exists.return_value = False
    prefix = "prefix_"
    log_paths = LogPaths.create(prefix)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.STDERR)
    expected_calls = [
        call(each, "w") for name, each in log_paths if name != Outputs.STDOUT
    ]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.path.exists")
@patch("con_duct.__main__.os.makedirs")
@patch("builtins.open")
def test_prepare_file_paths_available_no_streams(
    mock_open: MagicMock, _mock_mkdir: MagicMock, mock_exists: MagicMock
) -> None:
    mock_exists.return_value = False
    prefix = "prefix_"
    log_paths = LogPaths.create(prefix)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.NONE)
    streams = [Outputs.STDOUT, Outputs.STDERR]
    expected_calls = [
        call(each, "w") for name, each in log_paths if name not in streams
    ]
    mock_open.assert_has_calls(expected_calls, any_order=True)


@patch("con_duct.__main__.os.makedirs")
@patch("con_duct.__main__.os.path.exists")
@patch("builtins.open")
def test_prepare_paths_not_available_no_clobber(
    mock_open: MagicMock, mock_exists: MagicMock, mock_mkdir: MagicMock
) -> None:
    mock_exists.return_value = True
    log_paths = LogPaths.create("doesntmatter")
    with pytest.raises(FileExistsError):
        log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_mkdir.assert_not_called()
    mock_open.assert_not_called()

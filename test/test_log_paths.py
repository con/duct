from __future__ import annotations
from dataclasses import asdict
import os
import pathlib
import re
from unittest.mock import MagicMock, call, patch
import pytest
from duct.__main__ import LogPaths, Outputs, Suffix


def test_log_paths_simple_prefix() -> None:
    log_paths = LogPaths.create("prefix_")
    assert log_paths.stdout == f"prefix_{Suffix.stdout}"
    assert log_paths.stderr == f"prefix_{Suffix.stderr}"
    assert log_paths.info == f"prefix_{Suffix.info}"
    assert log_paths.usage == f"prefix_{Suffix.usage}"


def test_log_paths_iter() -> None:
    test_prefix = "prefix_"
    log_paths = LogPaths.create(test_prefix)
    # prefix should not be treated like the fields
    assert "_prefix" not in asdict(log_paths)
    assert "prefix" not in asdict(log_paths)
    assert log_paths.prefix == test_prefix

    # One for each of the Suffixes
    assert asdict(log_paths).keys() == asdict(Suffix()).keys()


def test_log_paths_filesafe_datetime_prefix() -> None:
    log_paths = LogPaths.create("start_{datetime_filesafe}")
    pattern = r"^start_\d{4}\.\d{2}\.\d{2}T\d{2}\.\d{2}\.\d{2}.*"
    for path in asdict(log_paths).values():
        assert re.match(pattern, path) is not None


def test_log_paths_pid_prefix() -> None:
    prefix = "prefix_{pid}_"
    log_paths = LogPaths.create(prefix, pid=123456)
    assert log_paths.stdout == f"prefix_123456_{Suffix.stdout}"
    assert log_paths.stderr == f"prefix_123456_{Suffix.stderr}"
    assert log_paths.info == f"prefix_123456_{Suffix.info}"
    assert log_paths.usage == f"prefix_123456_{Suffix.usage}"
    assert "prefix" not in asdict(log_paths)
    assert log_paths.prefix == prefix.format(pid=123456)


@patch("duct.__main__.os.makedirs")
@patch("duct.__main__.Path", spec=pathlib.Path)
def test_prepare_file_paths_available(mock_path, mock_mkdir) -> None:
    mock_path.return_value.exists.return_value = False
    prefix = "prefix_"
    log_paths = LogPaths.create(prefix)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_path.return_value.unlink.assert_not_called()
    mock_mkdir.assert_not_called()
    expected_calls = [call(each) for each in asdict(log_paths).values()]
    mock_path.assert_has_calls(expected_calls, any_order=True)
    assert mock_path.return_value.touch.call_count == len(asdict(log_paths))


@pytest.mark.parametrize(
    "path",
    [
        "directory/",
        "nested/directory/",
        "/abs/path/",
    ],
)
@patch("duct.__main__.os.makedirs")
@patch("duct.__main__.Path", spec=pathlib.Path)
def test_prepare_dir_paths_available(mock_path, mock_mkdir, path) -> None:
    mock_path.return_value.exists.return_value = False
    log_paths = LogPaths.create(path)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_path.return_value.unlink.assert_not_called()
    mock_mkdir.assert_called_once_with(path, exist_ok=True)


@patch("duct.__main__.os.makedirs")
@patch("duct.__main__.Path", spec=pathlib.Path)
def test_prepare_dir_paths_not_available_no_clobber(mock_path, mock_mkdir) -> None:
    mock_path.return_value.exists.return_value = True
    log_paths = LogPaths.create("doesntmatter")
    with pytest.raises(FileExistsError):
        log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_path.return_value.unlink.assert_not_called()
    mock_mkdir.assert_not_called()


@patch("duct.__main__.os.makedirs")
@patch("duct.__main__.Path", spec=pathlib.Path)
def test_prepare_dir_paths_not_available_clobber(mock_path, mock_mkdir) -> None:
    mock_path.return_value.exists.return_value = True
    log_paths = LogPaths.create("file_prefix_")
    log_paths.prepare_paths(clobber=True, capture_outputs=Outputs.ALL)
    expected_calls = [call(each) for each in asdict(log_paths).values()]
    mock_path.assert_has_calls(expected_calls, any_order=True)
    assert mock_path.return_value.unlink.call_count == len(asdict(log_paths))
    assert mock_path.return_value.touch.call_count == len(asdict(log_paths))
    mock_mkdir.assert_not_called()


@pytest.mark.parametrize(
    "path",
    [
        "directory/pre_",
        "nested/directory/pre_",
        "/abs/path/pre_",
    ],
)
@patch("duct.__main__.os.makedirs")
@patch("duct.__main__.Path", spec=pathlib.Path)
def test_prefix_with_filepart_and_directory_part(
    mock_path: MagicMock, mock_mkdir: MagicMock, path
) -> None:
    mock_path.return_value.exists.return_value = False
    log_paths = LogPaths.create(path)
    log_paths.prepare_paths(clobber=False, capture_outputs=Outputs.ALL)
    mock_mkdir.assert_called_once_with(os.path.dirname(path), exist_ok=True)
    expected_calls = [call(each) for each in asdict(log_paths).values()]
    mock_path.assert_has_calls(expected_calls, any_order=True)
    assert mock_path.return_value.touch.call_count == len(asdict(log_paths))

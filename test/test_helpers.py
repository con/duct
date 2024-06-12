from __future__ import annotations
import pathlib
from unittest import mock
import pytest
from duct.__main__ import clobber_or_clear, ensure_directories


@pytest.mark.parametrize(
    "path",
    [
        "directory/",
        "nested/directory/",
        "/abs/path/",
    ],
)
@mock.patch("duct.__main__.os.makedirs")
def test_ensure_directories_with_dirs(mock_mkdir: mock.MagicMock, path: str) -> None:
    ensure_directories(path)
    mock_mkdir.assert_called_once_with(path, exist_ok=True)


@mock.patch("duct.__main__.Path", spec=pathlib.Path)
@mock.patch("duct.__main__.os.makedirs")
def test_ensure_directories_with_conflicts(
    mock_mkdir: mock.MagicMock, mock_path: mock.MagicMock
) -> None:
    mock_path.return_value.exists.return_value = True
    with pytest.raises(FileExistsError):
        ensure_directories("fakepath", clobber=False)
    mock_mkdir.assert_not_called()


@mock.patch("duct.__main__.Path", spec=pathlib.Path)
@mock.patch("duct.__main__.os.makedirs")
def test_ensure_directories_with_conflicts_clobber(
    mock_mkdir: mock.MagicMock, mock_path: mock.MagicMock
) -> None:
    mock_prefix = "fakepath/"
    mock_path.return_value.exists.return_value = True
    ensure_directories(mock_prefix, clobber=True)
    mock_mkdir.assert_called_once_with(mock_prefix, exist_ok=True)


@mock.patch("duct.__main__.os.makedirs")
def test_ensure_directories_with_file(mock_mkdir: mock.MagicMock) -> None:
    ensure_directories("just_a_file_name")
    mock_mkdir.assert_not_called()


@mock.patch("duct.__main__.os.makedirs")
def test_ensure_directories_with_filepart_and_directory_part(
    mock_mkdir: mock.MagicMock,
) -> None:
    ensure_directories("nested/dir/file_name")
    mock_mkdir.assert_called_once_with("nested/dir", exist_ok=True)


@mock.patch("duct.__main__.Path")
def test_clobber_or_clear_clear(mock_path: mock.MagicMock) -> None:
    mock_path.return_value.exists.return_value = False
    clobber_or_clear("mockpath", clobber=False)
    mock_path.return_value.unlink.assert_not_called()


@mock.patch("duct.__main__.Path")
def test_clobber_or_clear_clear_clobber(mock_path: mock.MagicMock) -> None:
    mock_path.return_value.exists.return_value = False
    clobber_or_clear("mockpath", clobber=True)
    mock_path.return_value.unlink.assert_not_called()


@mock.patch("duct.__main__.Path")
def test_clobber_or_clear_conflict(mock_path: mock.MagicMock) -> None:
    mock_path.return_value.exists.return_value = True
    with pytest.raises(FileExistsError):
        clobber_or_clear("mockpath", clobber=False)
    mock_path.return_value.unlink.assert_not_called()


@mock.patch("duct.__main__.Path")
def test_clobber_or_clear_clobber_conflict_clobber(mock_path: mock.MagicMock) -> None:
    mock_path.return_value.exists.return_value = True
    clobber_or_clear("mockpath", clobber=True)
    mock_path.return_value.unlink.assert_called()

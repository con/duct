from unittest import mock
import pytest
from duct import ensure_directories


@pytest.mark.parametrize(
    "path",
    [
        "directory/",
        "nested/directory/",
        "/abs/path/",
    ],
)
@mock.patch("duct.os.makedirs")
def test_ensure_directories_with_dirs(mock_mkdir, path):
    ensure_directories(path)
    mock_mkdir.assert_called_once_with(path, exist_ok=True)


@mock.patch("duct.os.makedirs")
def test_ensure_directories_with_file(mock_mkdir):
    ensure_directories("just_a_file_name")
    mock_mkdir.assert_not_called()


@mock.patch("duct.os.makedirs")
def test_ensure_directories_with_filepart_and_directory_part(mock_mkdir):
    ensure_directories("nested/dir/file_name")
    mock_mkdir.assert_called_once_with("nested/dir", exist_ok=True)

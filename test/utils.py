from io import BytesIO
from pathlib import Path


class MockStream:
    """Mocks stderr or stdout"""

    def __init__(self):
        self.buffer = BytesIO()

    def getvalue(self):
        return self.buffer.getvalue()


def assert_files(parent_dir, file_list, exists=True):
    if exists:
        for file_path in file_list:
            assert Path(
                parent_dir, file_path
            ).exists(), f"Expected file does not exist: {file_path}"
    else:
        for file_path in file_list:
            assert not Path(
                parent_dir, file_path
            ).exists(), f"Unexpected file should not exist: {file_path}"

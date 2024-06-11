from __future__ import annotations
from io import BytesIO
from pathlib import Path


class MockStream:
    """Mocks stderr or stdout"""

    def __init__(self) -> None:
        self.buffer = BytesIO()

    def getvalue(self) -> bytes:
        return self.buffer.getvalue()


def assert_files(parent_dir: str, file_list: list[str], exists: bool = True) -> None:
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

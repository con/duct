import os
from pathlib import Path
import pytest


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> str:
    # Append path separator so that value is recognized as a directory when
    # passed to `output_prefix`
    return str(tmp_path) + os.sep

import os
import subprocess
import tempfile
from unittest.mock import patch
import pytest
from utils import MockStream
from duct import TailPipe

# 10^7 line fixture is about 70MB
FIXTURE_LIST = [f"ten_{i}" for i in range(1, 8)]


@pytest.fixture(scope="module", params=FIXTURE_LIST)
def fixture_path(request, tmp_path_factory):
    num_lines_exponent = int(request.param.split("_")[1])
    base_temp_dir = tmp_path_factory.mktemp("fixture_data")
    file_path = base_temp_dir / f"{request.param}.txt"
    with open(file_path, "w") as f:
        for i in range(10**num_lines_exponent):
            f.write(f"{i}\n")
    # print(f"10 ^ {num_lines_exponent}: {10 ** num_lines_exponent}")
    # print(f"Fixture file size: {os.path.getsize(file_path)} bytes")
    yield str(file_path)

    os.remove(file_path)


@pytest.mark.parametrize("fixture_path", FIXTURE_LIST, indirect=True)
@patch("sys.stdout", new_callable=lambda: MockStream())
def test_high_throughput_stdout(mock_stdout, fixture_path):
    with tempfile.NamedTemporaryFile(mode="wb") as tmpfile:
        process = subprocess.Popen(
            ["cat", fixture_path],
            stdout=tmpfile,
        )
        stream = TailPipe(tmpfile.name, mock_stdout.buffer)
        stream.start()
        process.wait()
        stream.close()

    assert process.returncode == 0
    with open(fixture_path, "rb") as fixture:
        expected = fixture.read()
    assert mock_stdout.getvalue() == expected


@pytest.mark.parametrize("fixture_path", FIXTURE_LIST, indirect=True)
@patch("sys.stderr", new_callable=lambda: MockStream())
def test_high_throughput_stderr(mock_stderr, fixture_path):
    with tempfile.NamedTemporaryFile(mode="wb") as tmpfile:
        process = subprocess.Popen(
            ["./test/cat_to_err.py", fixture_path],
            stdout=subprocess.DEVNULL,
            stderr=tmpfile,
        )
        stream = TailPipe(tmpfile.name, mock_stderr.buffer)
        stream.start()
        process.wait()
        stream.close()

    assert process.returncode == 0
    with open(fixture_path, "rb") as fixture:
        expected = fixture.read()
    assert mock_stderr.getvalue() == expected


@patch("sys.stdout", new_callable=lambda: MockStream())
def test_close(mock_stdout):
    with tempfile.NamedTemporaryFile(mode="wb") as tmpfile:
        stream = TailPipe(tmpfile.name, mock_stdout.buffer)
        stream.start()
        stream.close()
        assert stream.infile.closed

import os
import subprocess
from unittest.mock import patch
import pytest
from utils import MockStream
from duct import TailPipe

FIXTURE_LIST = [f"ten_{i}" for i in range(1, 7)]


@pytest.fixture(scope="module", params=FIXTURE_LIST)
def fixture_path(request, tmp_path_factory):
    num_lines_exponent = int(request.param.split("_")[1])
    base_temp_dir = tmp_path_factory.mktemp("fixture_data")
    file_path = base_temp_dir / f"{request.param}.txt"
    print(f"Creating fixture for {num_lines_exponent}")
    print(f"10 ^ {num_lines_exponent}: {10 ** num_lines_exponent}")
    with open(file_path, "w") as f:
        for i in range(10**num_lines_exponent):
            f.write(f"{i}\n")
        # print(10 ^ num_lines_exponent)
    yield str(file_path)

    print(f"cleaning up {file_path}")
    with open(file_path, "r") as sanity:
        print(sanity.read())
    os.remove(file_path)


@pytest.mark.parametrize("fixture_path", FIXTURE_LIST, indirect=True)
@patch("sys.stdout", new_callable=lambda: MockStream())
def test_high_throughput(mock_stdout, fixture_path):
    outfile = "TEST"
    with open(outfile, "wb") as stdout:
        process = subprocess.Popen(
            ["cat", fixture_path],
            stdout=stdout,
        )
        tail_stream = TailPipe(outfile, mock_stdout.buffer)
        tail_stream.start()
        process.wait()
        tail_stream.close()

    assert process.returncode == 0
    with open(fixture_path, "rb") as fixture:
        expected = fixture.read()
    assert mock_stdout.getvalue() == expected


if __name__ == "__main__":
    test_high_throughput()

from io import StringIO
import os
import subprocess
import threading
import time
from unittest.mock import patch
import pytest

FIXTURE_LIST = [f"ten_{i}" for i in range(1, 7)]


@pytest.fixture(scope="module", params=FIXTURE_LIST)
def fixture_path(request, tmp_path_factory):
    num_lines = int(request.param.split("_")[1])
    base_temp_dir = tmp_path_factory.mktemp("fixture_data")
    file_path = base_temp_dir / f"{request.param}.txt"
    with open(file_path, "w") as f:
        for i in range(num_lines):
            f.write(f"{i}\n")
    yield str(file_path)
    os.remove(file_path)


class TailPipe:
    def __init__(self, file_path):
        self.file_path = file_path
        self.has_run = False

    def start(self):
        self.stop_event = threading.Event()
        self.infile = open(self.file_path, "rb")
        self.thread = threading.Thread(target=self._tail)
        self.thread.start()

    def _tail(self):
        while not self.stop_event.is_set() or not self.has_run:
            data = self.infile.read()
            if data:
                print(data.decode("utf-8"), end="")
            self.has_run = True
            # Do we really need this? TODO should be configurable
            time.sleep(0.01)
        data = self.infile.read()
        if data:
            print(data.decode("utf-8"), end="")

    def close(self):
        self.stop_event.set()
        self.thread.join()
        self.infile.close()


@pytest.mark.parametrize("fixture_path", FIXTURE_LIST, indirect=True)
@patch("sys.stdout", new_callable=StringIO)
def test_POC(mock_stdout, fixture_path):
    outfile = "TEST"
    with open(outfile, "wb") as stdout:
        process = subprocess.Popen(
            ["cat", fixture_path],
            stdout=stdout,
        )
        tail_stream = TailPipe(outfile)
        tail_stream.start()
        process.wait()
        tail_stream.close()

    assert process.returncode == 0
    with open(fixture_path) as fixture:
        expected = fixture.read()
    assert mock_stdout.getvalue() == expected


if __name__ == "__main__":
    test_POC()

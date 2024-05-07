import os
import subprocess
import threading
from unittest.mock import call, patch
import pytest
from duct import TeeStream


@pytest.mark.parametrize(
    "file_path",
    [
        # "test/e2e/ten_1",
        # "test/e2e/ten_2",
        "test/e2e/ten_3",
        # "test/e2e/ten_4",
        # "test/e2e/ten_5",
        # "test/e2e/ten_6",
    ],
)
@patch("sys.stdout.buffer.write")
def test_cat(mock_write, file_path):
    stop_event = threading.Event()
    tee = TeeStream("tmp-tee-out", stop_event)
    tee.start()
    try:
        process = subprocess.Popen(
            ["cat", file_path],
            stdout=tee,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        process.wait()
    finally:
        tee.close()
        os.remove("tmp-tee-out")

    assert process.returncode == 0
    with open(file_path, "r", newline="") as file:
        data = file.read()
    byte_data = data.replace("\n", "\r\n").encode("utf-8")
    expected_calls = [
        call(byte_data[i : i + TeeStream.CHUNK_SIZE]) for i in range(0, len(data), 1024)
    ]
    # expected_calls = [call(byte_data)]
    mock_write.assert_has_calls(expected_calls, any_order=False)


@pytest.mark.parametrize(
    "file_path",
    [
        "test/e2e/ten_1",
        "test/e2e/ten_2",
        "test/e2e/ten_3",
        "test/e2e/ten_4",
    ],
)
def test_sanity(file_path):
    with open(f"{file_path}-copy", "wb") as file:
        process = subprocess.Popen(
            ["cat", file_path],
            stdout=file,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        process.wait()

    assert process.returncode == 0
    with open(file_path, "r", newline="") as file:
        expected_data = file.read()
    byte_expected_data = expected_data.replace("\n", "\r\n").encode("utf-8")

    with open(f"{file_path}-copy", "r", newline="") as file:
        actual_data = file.read()
    byte_actual_data = actual_data.replace("\n", "\r\n").encode("utf-8")
    assert byte_actual_data == byte_expected_data


@patch("sys.stdout.buffer.write")
def test_cat_empty(mock_write):
    stop_event = threading.Event()
    tee = TeeStream("tmp-tee-out", stop_event)
    tee.start()
    try:
        process = subprocess.Popen(
            ["cat", "test/e2e/empty-file"],
            stdout=tee,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        process.wait()
    finally:
        tee.close()
        os.remove("tmp-tee-out")

    assert process.returncode == 0
    assert not mock_write.called

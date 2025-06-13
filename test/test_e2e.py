from __future__ import annotations
import json
from pathlib import Path
import subprocess
import time
import pytest

TEST_SCRIPT_DIR = Path(__file__).with_name("data")


def test_sanity(temp_output_dir: str) -> None:
    command = f"duct -p {temp_output_dir}log_ sleep 0.1"
    subprocess.check_output(command, shell=True)


@pytest.mark.parametrize("mode", ["plain", "subshell", "nohup", "setsid"])
@pytest.mark.parametrize("num_children", [1, 2, 10])
def test_spawn_children(temp_output_dir: str, mode: str, num_children: int) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
    dur = "0.4"
    command = f"duct -q --s-i 0.001 --r-i 0.01 -p {duct_prefix} {script_path} {mode} {num_children} {dur}"

    expected_count = 1 if mode == "setsid" else num_children + 1

    # Retry mechanism for flaky timing issues
    for attempt in range(3):
        # Clean up previous attempt's files
        try:
            Path(f"{duct_prefix}usage.json").unlink(missing_ok=True)
        except OSError:
            pass

        subprocess.check_output(command, shell=True)

        with open(f"{duct_prefix}usage.json") as usage_file:
            all_samples = [json.loads(line) for line in usage_file]

        # Only count the child sleep processes
        all_child_pids = set(
            pid
            for sample in all_samples
            for pid, proc in sample["processes"].items()
            if "sleep" in proc["cmd"]
        )

        # Check if we got the expected count
        if len(all_child_pids) == expected_count:
            break

        # If not the last attempt, wait before retrying
        if attempt < 2:
            time.sleep(0.1)

    # Add one pid for the hold-the-door process, see spawn_children.sh line 7
    if mode == "setsid":
        assert len(all_child_pids) == 1
    else:
        assert len(all_child_pids) == num_children + 1

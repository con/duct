from __future__ import annotations
import json
from pathlib import Path
import subprocess
import pytest

TEST_SCRIPT_DIR = Path(__file__).with_name("data")


def test_sanity(temp_output_dir: str) -> None:
    command = f"duct -p {temp_output_dir}log_ sleep 0.1"
    subprocess.check_output(command, shell=True)


@pytest.mark.parametrize("mode", ["plain", "subshell", "nohup", "setsid"])
@pytest.mark.parametrize(
    "num_children", [1, 2, 1, 2, 1, 2, 1, 2, 10, 1, 2, 1, 2, 10, 1, 2, 1, 2, 10, 1]
)
def test_spawn_children(temp_output_dir: str, mode: str, num_children: int) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
    dur = "0.2"
    command = f"duct -q --s-i 0.001 --r-i 0.01 -p {duct_prefix} {script_path} {mode} {num_children} {dur}"

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

    expected_count = 1 if mode == "setsid" else num_children + 1

    # Debug capture if we get unexpected count
    if len(all_child_pids) != expected_count:
        # Collect all sleep processes with full details
        sleep_processes = []
        for sample in all_samples:
            for pid, proc in sample["processes"].items():
                if "sleep" in proc["cmd"]:
                    sleep_processes.append(
                        {
                            "pid": pid,
                            "cmd": proc["cmd"],
                            "sample_timestamp": sample.get("timestamp", "unknown"),
                            "full_proc": proc,
                        }
                    )

        # Print comprehensive debug info
        print(f"\\n*** BUG FOUND: {mode}[{num_children}] ***")
        print(
            f"Expected {expected_count} PIDs, got {len(all_child_pids)}: {all_child_pids}"
        )
        print("Sleep processes found:")
        for sp in sleep_processes:
            print(f"  PID {sp['pid']}: {sp['cmd']}")
        print("Full usage.json content:")
        print(json.dumps(all_samples, indent=2))

    # Add one pid for the hold-the-door process, see spawn_children.sh line 7
    if mode == "setsid":
        assert (
            len(all_child_pids) == 1
        ), f"setsid mode expected 1 PID, got {len(all_child_pids)}: {all_child_pids}"
    else:
        assert (
            len(all_child_pids) == num_children + 1
        ), f"{mode} mode expected {num_children + 1} PIDs, got {len(all_child_pids)}: {all_child_pids}"

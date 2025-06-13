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
@pytest.mark.parametrize(
    "num_children", [1, 2, 1, 2, 1, 2, 1, 2, 10, 1, 2, 1, 2, 10, 1, 2, 1, 2, 10, 1]
)
def test_spawn_children(temp_output_dir: str, mode: str, num_children: int) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
    dur = "0.4"
    command = f"duct -q --s-i 0.001 --r-i 0.01 -p {duct_prefix} {script_path} {mode} {num_children} {dur}"

    expected_count = 1 if mode == "setsid" else num_children + 1

    # Retry mechanism for flaky timing issues
    for attempt in range(1):  # Remove retry - single attempt
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


# def test_debug_setsid_bug(temp_output_dir: str) -> None:
# """Debug version to catch the 2 PIDs setsid bug with comprehensive logging"""
# duct_prefix = f"{temp_output_dir}log_"
# script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
# dur = "0.4"  # Keep longer duration
# command = f"duct -q --clobber --s-i 0.001 --r-i 0.01 -p {duct_prefix} {script_path} setsid 1 {dur}"
#
# expected_count = 1
#
# # Run many iterations to catch the bug
# failures = []
# for iteration in range(200):  # Many iterations to increase chance of hitting bug
#     # Clean up previous files
#     try:
#         Path(f"{duct_prefix}usage.json").unlink(missing_ok=True)
#     except OSError:
#         pass
#
#     subprocess.check_output(command, shell=True)
#
#     with open(f"{duct_prefix}usage.json") as usage_file:
#         all_samples = [json.loads(line) for line in usage_file]
#
#     # Only count the child sleep processes
#     all_child_pids = set(
#         pid
#         for sample in all_samples
#         for pid, proc in sample["processes"].items()
#         if "sleep" in proc["cmd"]
#     )
#
#     # Check if we got unexpected count - capture full debug info
#     if len(all_child_pids) != expected_count:
#         # Collect all sleep processes with full details
#         sleep_processes = []
#         for sample in all_samples:
#             for pid, proc in sample["processes"].items():
#                 if "sleep" in proc["cmd"]:
#                     sleep_processes.append(
#                         {
#                             "pid": pid,
#                             "cmd": proc["cmd"],
#                             "sample_timestamp": sample.get("timestamp", "unknown"),
#                             "full_proc": proc,
#                         }
#                     )
#
#         failure_info = {
#             "iteration": iteration,
#             "expected": expected_count,
#             "actual": len(all_child_pids),
#             "pids": all_child_pids,
#             "sleep_processes": sleep_processes,
#             "full_samples": all_samples,
#             "usage_file": f"{duct_prefix}usage.json",
#         }
#         failures.append(failure_info)
#
#         # Print immediate debug info
#         print(f"\n*** BUG FOUND in iteration {iteration}! ***")
#         print(
#             f"Expected {expected_count} PIDs, got {len(all_child_pids)}: {all_child_pids}"
#         )
#         print("Sleep processes found:")
#         for sp in sleep_processes:
#             print(f"  PID {sp['pid']}: {sp['cmd']}")
#         print("Full usage.json content:")
#         print(json.dumps(all_samples, indent=2))
#         break  # Stop on first failure to avoid spam
#
# # Summary
# if failures:
#     print(f"\n*** SUMMARY: Found bug in iteration {failures[0]['iteration']} ***")
#     first_failure = failures[0]
#     msg = (
#         f"Bug reproduced! Expected {first_failure['expected']} PIDs, "
#         f"got {first_failure['actual']}: {first_failure['pids']}"
#     )
#     raise AssertionError(msg)
#
# print("All 200 iterations passed - no bug reproduced")

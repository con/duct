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


@pytest.mark.flaky(reruns=3)
@pytest.mark.parametrize("mode", ["plain", "subshell", "nohup", "setsid"])
@pytest.mark.parametrize("num_children", [1, 2, 10])
def test_spawn_children(temp_output_dir: str, mode: str, num_children: int) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
    dur = "0.3"
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
    # Add one pid for the hold-the-door process, see spawn_children.sh line 7
    if mode == "setsid":
        assert len(all_child_pids) == 1
    else:
        assert len(all_child_pids) == num_children + 1


@pytest.mark.parametrize("session_mode", ["new-session", "current-session"])
def test_session_modes(temp_output_dir: str, session_mode: str) -> None:
    """Test that both session modes work correctly and collect appropriate data."""
    duct_prefix = f"{temp_output_dir}log_"
    command = f"duct -q --s-i 0.01 --r-i 0.05 --mode {session_mode} -p {duct_prefix} sleep 0.3"
    subprocess.check_output(command, shell=True)

    # Check that log files were created
    usage_file = Path(f"{duct_prefix}usage.json")
    info_file = Path(f"{duct_prefix}info.json")

    assert usage_file.exists(), f"Usage file not created for {session_mode} mode"
    assert info_file.exists(), f"Info file not created for {session_mode} mode"

    # Read and validate usage data
    with open(usage_file) as f:
        samples = [json.loads(line) for line in f]

    # Both modes should collect some data, but the behavior may differ
    assert len(samples) > 0, f"No samples collected for {session_mode} mode"

    # Validate sample structure
    for sample in samples:
        assert "timestamp" in sample
        assert "processes" in sample
        assert "totals" in sample

    # Read and validate info data
    with open(info_file) as f:
        info_data = json.loads(f.read())

    assert "execution_summary" in info_data
    assert info_data["execution_summary"]["exit_code"] == 0
    assert "sleep" in info_data["command"]


def test_session_mode_behavior_difference(temp_output_dir: str) -> None:
    """Test that new-session and current-session modes behave differently."""

    # Start a unique background process in the current session
    background_process = subprocess.Popen(
        ["python", "-c", "print('DUCT_TEST_MARKER'); import time; time.sleep(10)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Give background process time to start
        time.sleep(0.1)

        new_session_prefix = f"{temp_output_dir}new_"
        current_session_prefix = f"{temp_output_dir}current_"

        # Run duct with new-session mode - should NOT see background process
        subprocess.check_output(
            f"duct -q --s-i 0.01 --r-i 0.05 --mode new-session -p {new_session_prefix} sleep 2",
            shell=True,
        )

        # Run duct with current-session mode - should see background process
        subprocess.check_output(
            f"duct -q --s-i 0.01 --r-i 0.05 --mode current-session -p {current_session_prefix} sleep 2",
            shell=True,
        )

        # Read usage data from both
        with open(f"{new_session_prefix}usage.json") as f:
            new_session_samples = [json.loads(line) for line in f]

        with open(f"{current_session_prefix}usage.json") as f:
            current_session_samples = [json.loads(line) for line in f]

        # Check for our unique background process
        new_session_has_marker = any(
            any(
                "DUCT_TEST_MARKER" in str(proc.get("cmd", ""))
                for proc in sample["processes"].values()
            )
            for sample in new_session_samples
        )

        current_session_has_marker = any(
            any(
                "DUCT_TEST_MARKER" in str(proc.get("cmd", ""))
                for proc in sample["processes"].values()
            )
            for sample in current_session_samples
        )

        # new-session should NOT see the background process
        assert (
            not new_session_has_marker
        ), "new-session mode should not track background process"

        # current-session should see the background process
        assert (
            current_session_has_marker
        ), "current-session mode should track background process"

    finally:
        # Explicit cleanup of background process
        if background_process.poll() is None:
            background_process.terminate()
            try:
                background_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                background_process.kill()
                background_process.wait()

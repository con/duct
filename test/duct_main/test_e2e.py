from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time
import pytest
from utils import assert_files, rest_of_stderr, start_duct
from con_duct._constants import SUFFIXES

SYSTEM = platform.system()
TEST_SCRIPT_DIR = Path(__file__).parent.parent / "data"
LOG_FILES = [SUFFIXES[k] for k in ("stdout", "stderr", "info", "usage")]
# Allow overriding the duct executable for testing external builds (e.g., PyInstaller)
_DUCT_EXECUTABLES = [
    exe.strip()
    for exe in os.environ.get("DUCT_TEST_EXECUTABLES", "duct,con-duct run").split(",")
]


@pytest.fixture(params=_DUCT_EXECUTABLES)
def duct_cmd(request: pytest.FixtureRequest) -> str:
    """Fixture that parametrizes tests to run with different duct entry points."""
    return str(request.param)


def test_sanity(temp_output_dir: str, duct_cmd: str) -> None:
    command = f"{duct_cmd} -p {temp_output_dir}log_ sleep 0.1"
    subprocess.check_output(command, shell=True)


@pytest.mark.flaky(reruns=3)
@pytest.mark.parametrize("mode", ["plain", "subshell", "nohup", "setsid"])
@pytest.mark.parametrize("num_children", [1, 2, 10])
def test_spawn_children(
    temp_output_dir: str, duct_cmd: str, mode: str, num_children: int
) -> None:
    duct_prefix = f"{temp_output_dir}log_"
    script_path = TEST_SCRIPT_DIR / "spawn_children.sh"
    dur = "0.3"
    command = (
        f"{duct_cmd} -q --s-i 0.001 --r-i 0.01 "
        f"-p {duct_prefix} {script_path} {mode} {num_children} {dur}"
    )
    subprocess.check_output(command, shell=True)

    with open(f"{duct_prefix}{SUFFIXES['usage']}") as usage_file:
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
def test_session_modes(temp_output_dir: str, duct_cmd: str, session_mode: str) -> None:
    """Test that both session modes work correctly and collect appropriate data."""
    duct_prefix = f"{temp_output_dir}log_"
    command = f"{duct_cmd} -q --s-i 0.01 --r-i 0.05 --mode {session_mode} -p {duct_prefix} sleep 0.3"
    subprocess.check_output(command, shell=True)

    # Check that log files were created
    usage_file = Path(f"{duct_prefix}{SUFFIXES['usage']}")
    info_file = Path(f"{duct_prefix}{SUFFIXES['info']}")

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


def test_session_mode_behavior_difference(temp_output_dir: str, duct_cmd: str) -> None:
    """Test that new-session and current-session modes behave differently."""

    # Start a unique background process in the current session. It must outlive
    # both duct runs however slow they are (the finally block stops it).
    background_process = subprocess.Popen(
        ["python", "-c", "print('DUCT_TEST_MARKER'); import time; time.sleep(600)"],
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
            f"{duct_cmd} -q --s-i 0.01 --r-i 0.05 --mode new-session -p {new_session_prefix} sleep 2",
            shell=True,
        )

        # Run duct with current-session mode - should see background process
        subprocess.check_output(
            f"{duct_cmd} -q --s-i 0.01 --r-i 0.05 --mode current-session -p {current_session_prefix} sleep 2",
            shell=True,
        )

        # Read usage data from both
        with open(f"{new_session_prefix}{SUFFIXES['usage']}") as f:
            new_session_samples = [json.loads(line) for line in f]

        with open(f"{current_session_prefix}{SUFFIXES['usage']}") as f:
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


def test_logging_levels(temp_output_dir: str, duct_cmd: str) -> None:
    """Test that --quiet and --log-level NONE suppress logging output."""
    duct_prefix = f"{temp_output_dir}log_"

    # Test normal logging - should see "Summary" in stderr
    result = subprocess.run(
        f"{duct_cmd} -p {duct_prefix} sleep 0.1",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Summary" in result.stderr, "Normal run should log Summary"
    assert "Exit Code:" in result.stderr

    # Test --quiet flag - should suppress logging
    result_quiet = subprocess.run(
        f"{duct_cmd} --quiet --clobber -p {duct_prefix} sleep 0.1",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert result_quiet.returncode == 0
    assert "Summary" not in result_quiet.stderr, "--quiet should suppress logging"
    assert (
        result_quiet.stderr == ""
    ), f"Expected empty stderr, got: {result_quiet.stderr!r}"

    # Test --log-level NONE - should suppress logging
    result_none = subprocess.run(
        f"{duct_cmd} --log-level NONE --clobber -p {duct_prefix} sleep 0.1",
        shell=True,
        capture_output=True,
        text=True,
    )
    assert result_none.returncode == 0
    assert (
        "Summary" not in result_none.stderr
    ), "--log-level NONE should suppress logging"
    assert (
        result_none.stderr == ""
    ), f"Expected empty stderr, got: {result_none.stderr!r}"


# The --fail-time values whose effect does not depend on how long the run
# took: 0 always keeps a failed command's logs, a negative value never does
FAIL_TIMES = [0, -1]


# @pytest.mark.flaky(reruns=5)  # disabled: start_duct waits for duct instead of sleeping
@pytest.mark.parametrize("fail_time", FAIL_TIMES)
def test_signal_int(temp_output_dir: str, duct_cmd: str, fail_time: int) -> None:
    args = ["-p", temp_output_dir, f"--fail-time={fail_time}"]
    proc = start_duct(duct_cmd, [*args, "sleep", "60"])
    os.kill(proc.pid, signal.SIGINT)
    proc.communicate()

    # duct forwards SIGINT to the command and exits with the command's code
    assert proc.returncode == 128 + signal.SIGINT

    if fail_time < 0:
        assert_files(temp_output_dir, LOG_FILES, exists=False)
    else:
        with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
            info_data = json.loads(info.read())
        assert info_data["execution_summary"]["exit_code"] == 128 + signal.SIGINT


def _wait_for_lines(path: Path, n: int, proc: subprocess.Popen[str]) -> None:
    """Wait until *path* has *n* lines, failing if duct exits first."""
    while not path.exists() or len(path.read_text().splitlines()) < n:
        assert proc.poll() is None, (
            f"duct exited with {proc.returncode} before {path.name} had {n} lines; "
            f"its stderr:\n{rest_of_stderr(proc)}"
        )
        time.sleep(0.01)


# @pytest.mark.flaky(reruns=5)  # disabled: the test waits for each step instead of sleeping
@pytest.mark.parametrize("fail_time", FAIL_TIMES)
def test_signal_kill(
    temp_output_dir: str, tmp_path: Path, duct_cmd: str, fail_time: int
) -> None:
    progress = tmp_path / "signal_ignorer.progress"
    args = ["-p", temp_output_dir, f"--fail-time={fail_time}"]
    script = TEST_SCRIPT_DIR / "signal_ignorer.py"
    proc = start_duct(duct_cmd, [*args, str(script), str(progress)])

    _wait_for_lines(progress, 1, proc)  # "ready": the command ignores SIGINT now
    # duct forwards the first two; each must arrive before the next is sent,
    # since pending SIGINTs merge into one
    for received in (2, 3):
        os.kill(proc.pid, signal.SIGINT)
        _wait_for_lines(progress, received, proc)
    os.kill(proc.pid, signal.SIGINT)  # third: duct kills the command
    proc.communicate()

    assert proc.returncode == 128 + signal.SIGKILL

    if fail_time < 0:
        assert_files(temp_output_dir, LOG_FILES, exists=False)
    else:
        with open(os.path.join(temp_output_dir, SUFFIXES["info"])) as info:
            info_data = json.loads(info.read())
        assert info_data["execution_summary"]["exit_code"] == 128 + signal.SIGKILL

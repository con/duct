from __future__ import annotations
from collections.abc import Generator
import os
from pathlib import Path
import signal
from typing import Any
import pytest
from utils import run_duct_command
from con_duct import _signals
from con_duct._signals import SigIntHandler
from con_duct._tracker import Report


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record os.kill calls made by the handler instead of sending them."""
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "con_duct._signals.os.kill", lambda pid, sig: calls.append((pid, sig))
    )
    return calls


@pytest.fixture
def restore_sigint() -> Generator[None, None, None]:
    """execute() installs its own SIGINT handler; put pytest's back."""
    orig = signal.getsignal(signal.SIGINT)
    yield
    signal.signal(signal.SIGINT, orig)


@pytest.mark.parametrize(
    "presses,expected",
    [
        (1, [signal.SIGINT]),
        (2, [signal.SIGINT, signal.SIGINT]),
        (3, [signal.SIGINT, signal.SIGINT, signal.SIGKILL]),
    ],
)
def test_forwards_after_attach(
    sent: list[tuple[int, int]], presses: int, expected: list[int]
) -> None:
    handler = SigIntHandler()
    handler.attach(1234)
    for _ in range(presses):
        handler(signal.SIGINT, None)
    assert sent == [(1234, sig) for sig in expected]


def test_counts_but_does_not_forward_before_attach(
    sent: list[tuple[int, int]],
) -> None:
    handler = SigIntHandler()
    handler(signal.SIGINT, None)
    assert handler.sigcount == 1
    assert sent == []


@pytest.mark.parametrize(
    "presses,expected", [(1, signal.SIGINT), (2, signal.SIGINT), (3, signal.SIGKILL)]
)
def test_attach_acts_on_earlier_sigints(
    sent: list[tuple[int, int]], presses: int, expected: int
) -> None:
    handler = SigIntHandler()
    for _ in range(presses):
        handler(signal.SIGINT, None)
    handler.attach(1234)
    # Only the latest escalation level is applied, once
    assert sent == [(1234, expected)]


def test_forwards_even_if_logging_fails(
    sent: list[tuple[int, int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    def reentrant(*_args: Any) -> None:
        raise RuntimeError("reentrant call inside <_io.BufferedWriter name='<stderr>'>")

    monkeypatch.setattr(_signals.lgr, "log", reentrant)
    handler = SigIntHandler()
    handler.attach(1234)
    handler(signal.SIGINT, None)
    assert sent == [(1234, signal.SIGINT)]


def test_command_already_exited(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def no_such_process(_pid: int, _sig: int) -> None:
        raise ProcessLookupError(3, "No such process")

    monkeypatch.setattr("con_duct._signals.os.kill", no_such_process)
    handler = SigIntHandler()
    handler.attach(1234)
    handler(signal.SIGINT, None)  # must not raise
    assert [(r.levelname, r.message) for r in caplog.records] == [
        ("WARNING", "Received SIGINT, but the command has already exited")
    ]


@pytest.mark.usefixtures("restore_sigint")
def test_sigint_before_command_starts_does_not_start_it(
    temp_output_dir: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_report = Report

    def report_then_sigint(*args: Any, **kwargs: Any) -> Any:
        # Report is built after duct's handler is installed and before Popen
        report = real_report(*args, **kwargs)
        os.kill(os.getpid(), signal.SIGINT)
        return report

    monkeypatch.setattr("con_duct._duct_main.Report", report_then_sigint)
    marker = tmp_path / "command-ran"
    rc = run_duct_command(["touch", str(marker)], output_prefix=temp_output_dir)

    assert rc == 128 + signal.SIGINT
    assert not marker.exists()
    assert list(Path(temp_output_dir).iterdir()) == []

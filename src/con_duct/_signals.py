"""Signal handlers for con-duct."""

from __future__ import annotations
import logging
import os
import signal
import threading
from types import FrameType
from typing import Optional

lgr = logging.getLogger("con-duct")


def start_thread(thread: threading.Thread) -> None:
    """Start a thread that the kernel will never hand a SIGINT to.

    A signal sent to the process is delivered to any one thread that does
    not block it, but Python runs the handler only in the main thread. If
    another thread takes a SIGINT, the main thread stays asleep in its wait
    for the command and the Ctrl-C is not forwarded until the command exits.
    A new thread inherits its creator's signal mask, so block SIGINT just
    while starting it. Every thread duct starts must be started this way.

    Parameters
    ----------
    thread : threading.Thread
        The thread to start
    """
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    try:
        thread.start()
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)


class SigIntHandler:
    """
    Handler of SIGINT signals received by the process running duct.
    """

    def __init__(self) -> None:
        # Installed before the command starts; SIGINTs are only counted
        # until attach() says which process to forward them to.
        self.pid: Optional[int] = None
        self.sigcount: int = 0

    def attach(self, pid: int) -> None:
        """Start forwarding SIGINTs to the command.

        Parameters
        ----------
        pid : int
            The PID of the process monitored by duct. A SIGINT that arrived
            while it was being started is acted on now.
        """
        self.pid = pid
        if self.sigcount:
            self._act()

    def __call__(self, _sig: int, _frame: Optional[FrameType]) -> None:
        self.sigcount += 1
        if self.pid is not None:
            self._act()

    def _act(self) -> None:
        try:
            self._forward()
        except ProcessLookupError:
            # The command has already exited. Python runs this handler in
            # the main thread at its next bytecode, which can be only after
            # the wait for the command returns.
            _log(
                logging.WARNING,
                "Received SIGINT, but the command has already exited",
            )

    def _forward(self) -> None:
        assert self.pid is not None
        # Act before logging: the handler can interrupt duct mid-write to
        # stderr, and a failed log write must not stop the signal.
        if self.sigcount == 1:
            os.kill(self.pid, signal.SIGINT)
            _log(logging.INFO, "Received SIGINT, passing to command")
        elif self.sigcount == 2:
            os.kill(self.pid, signal.SIGINT)
            _log(logging.INFO, "Received second SIGINT, again passing to command")
        elif self.sigcount == 3:
            os.kill(self.pid, signal.SIGKILL)
            _log(
                logging.WARNING,
                "Received third SIGINT, forcefully killing command process",
            )
        elif self.sigcount >= 4:
            _log(logging.CRITICAL, "Exiting duct, skipping cleanup")
            os._exit(1)


def _log(level: int, msg: str) -> None:
    """Log from a signal handler without ever raising.

    If the signal arrived while duct was writing to stderr, logging raises
    ``RuntimeError: reentrant call`` (even its error report does): the
    buffered writer is held by the write the handler interrupted, which
    cannot finish until the handler returns. Write the message straight to
    file descriptor 2 instead, if the log level lets the message through.
    It does not go through the log format, and it may land in the middle of
    the log line that was being written, so it starts on a new line and says
    why it looks different.
    """
    try:
        lgr.log(level, msg)
    except RuntimeError:
        if not lgr.isEnabledFor(level):
            return
        try:
            line = (
                f"\ncon-duct [{logging.getLevelName(level)}] (written directly: "
                f"the signal interrupted a log write): {msg}\n"
            )
            os.write(2, line.encode())
        except OSError:
            pass

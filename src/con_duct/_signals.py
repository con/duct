"""Signal handlers for con-duct."""

from __future__ import annotations
import logging
import os
import signal
from types import FrameType
from typing import Optional

lgr = logging.getLogger("con-duct")


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
    ``RuntimeError: reentrant call`` (even its error report does); drop the
    message rather than let the error escape the handler.
    """
    try:
        lgr.log(level, msg)
    except RuntimeError:
        pass

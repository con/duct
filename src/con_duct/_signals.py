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

    def __init__(self, pid: int) -> None:
        """
        Parameters
        ----------
        pid : int
            The PID of the process monitored by duct
        """
        self.pid: int = pid
        self.sigcount: int = 0

    def __call__(self, _sig: int, _frame: Optional[FrameType]) -> None:
        self.sigcount += 1
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

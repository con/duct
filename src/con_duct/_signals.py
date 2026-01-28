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
        if self.sigcount == 1:
            lgr.info("Received SIGINT, passing to command")
            os.kill(self.pid, signal.SIGINT)
        elif self.sigcount == 2:
            lgr.info("Received second SIGINT, again passing to command")
            os.kill(self.pid, signal.SIGINT)
        elif self.sigcount == 3:
            lgr.warning("Received third SIGINT, forcefully killing command process")
            os.kill(self.pid, signal.SIGKILL)
        elif self.sigcount >= 4:
            lgr.critical("Exiting duct, skipping cleanup")
            os._exit(1)

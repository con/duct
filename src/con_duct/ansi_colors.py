"""
Definitions for ansi colors etc

Originally copied from the `datalad` (MIT Licence) project on September 20, 2024
https://github.com/datalad/datalad/blob/b55d8b7292fcb37b3ba6faad7fd7107fcc1caa50/datalad/support/ansi_colors.py#L4
"""

from __future__ import annotations

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"


def color_word(s: str, color: int, enable_colors: bool = False) -> str:
    """Color `s` with `color`.

    Parameters
    ----------
    s : string
    color : int
        Code for color. If the value evaluates to false, the string will not be
        colored.
    enable_colors: boolean, optional

    Returns
    -------
    str
    """
    if color and enable_colors:
        return "%s%s%s" % (COLOR_SEQ % color, s, RESET_SEQ)
    return s

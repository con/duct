"""Summary formatter with custom conversions for con-duct output."""

from __future__ import annotations
from datetime import datetime
import logging
import string
from typing import Any

lgr = logging.getLogger("con-duct")


class SummaryFormatter(string.Formatter):
    OK = "OK"
    NOK = "X"
    NONE = "-"
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(30, 38)
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[1;%dm"
    FILESIZE_SUFFIXES = (" kB", " MB", " GB", " TB", " PB", " EB", " ZB", " YB")

    def __init__(self, enable_colors: bool = False) -> None:
        self.enable_colors = enable_colors

    def naturalsize(
        self,
        value: float | str,
        format: str = "%.1f",  # noqa: A002
    ) -> str:
        """Format a number of bytes like a human readable decimal filesize (e.g. 10 kB).

        Examples:
            ```pycon
            >>> formatter = SummaryFormatter()
            >>> formatter.naturalsize(3000000)
            '3.0 MB'
            >>> formatter.naturalsize(3000, "%.3f")
            '2.930 kB'
            >>> formatter.naturalsize(10**28)
            '10000.0 YB'
            ```

        Args:
            value (int, float, str): Integer to convert.
            format (str): Custom formatter.

        Returns:
            str: Human readable representation of a filesize.
        """
        base = 1000
        bytes_ = float(value)
        abs_bytes = abs(bytes_)

        if abs_bytes == 1:
            return "%d Byte" % bytes_

        if abs_bytes < base:
            return "%d Bytes" % bytes_

        for i, _s in enumerate(self.FILESIZE_SUFFIXES):
            unit = base ** (i + 2)

            if abs_bytes < unit:
                break

        ret: str = format % (base * bytes_ / unit) + _s
        return ret

    def color_word(self, s: str, color: int) -> str:
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
        if color and self.enable_colors:
            return "%s%s%s" % (self.COLOR_SEQ % color, s, self.RESET_SEQ)
        return s

    def _format_duration(self, value: float) -> str:
        """Format a duration in seconds to human-readable format."""
        if value >= 3600:  # >= 1 hour
            hours = int(value // 3600)
            minutes = int((value % 3600) // 60)
            seconds = value % 60
            return f"{hours}h {minutes}m {seconds:.1f}s"
        elif value >= 60:  # >= 1 minute
            minutes = int(value // 60)
            seconds = value % 60
            return f"{minutes}m {seconds:.1f}s"
        else:
            return f"{value:.2f}s"

    def convert_field(self, value: str | None, conversion: str | None) -> Any:
        if conversion == "S":  # Human size
            if value is not None:
                return self.color_word(self.naturalsize(value), self.GREEN)
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "E":  # colored non-zero is bad
            return self.color_word(
                value if value is not None else self.NONE,
                self.RED if value or value is None else self.GREEN,
            )
        elif conversion == "X":  # colored truthy
            col = self.GREEN if value else self.RED
            return self.color_word(value if value is not None else self.NONE, col)
        elif conversion == "N":  # colored Red - if None
            if value is None:
                return self.color_word(self.NONE, self.RED)
            else:
                return self.color_word(value, self.GREEN)
        elif conversion == "P":  # Percentage
            if value is not None:
                return f"{float(value):.2f}%"
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "T":  # Time duration
            if value is not None:
                return self._format_duration(float(value))
            else:
                return self.color_word(self.NONE, self.RED)
        elif conversion == "D":  # DateTime from timestamp
            if value is not None:
                try:
                    dt = datetime.fromtimestamp(float(value))
                    return dt.strftime("%b %d, %Y %I:%M %p")
                except (ValueError, OSError):
                    return str(value)
            else:
                return self.color_word(self.NONE, self.RED)

        return super().convert_field(value, conversion)

    def format_field(self, value: Any, format_spec: str) -> Any:
        # TODO: move all the "coloring" into formatting, so we could correctly indent
        # given the format and only then color it up
        # print "> %r, %r" % (value, format_spec)
        if value is None:
            # TODO: could still use our formatter and make it red or smth like that
            return self.NONE
        # if it is a composite :format!conversion, we need to split it
        if "!" in format_spec and format_spec.index("!") > 1:
            format_spec, conversion = format_spec.split("!", 1)
        else:
            conversion = None
        try:
            value_ = super().format_field(value, format_spec)
        except ValueError as exc:
            lgr.warning(
                "Falling back to `str` formatting for %r due to exception: %s",
                value,
                exc,
            )
            return str(value)
        if conversion:
            return self.convert_field(value_, conversion)
        return value_

"""Interface for styling tabular terminal output.

This module defines the Tabular entry point.
"""

from contextlib import contextmanager
from logging import getLogger
import os

# Eventually we may want to retire blessings:
# https://github.com/pyout/pyout/issues/136
try:
    from blessed import Terminal
except ImportError:
    from blessings import Terminal

from pyout import interface
from pyout.field import TermProcessors

lgr = getLogger(__name__)


class TerminalStream(interface.Stream):
    """Stream interface implementation using blessed/blessings.Terminal.
    """

    def __init__(self, stream=None, interactive=None):
        super(TerminalStream, self).__init__(
            stream=stream, interactive=interactive)
        self.term = Terminal(stream=self.stream,
                             # interactive=False maps to force_styling=None.
                             force_styling=self.interactive or None)

    @property
    def width(self):
        """Maximum terminal width.
        """
        if self.interactive:
            return self.term.width

    @property
    def height(self):
        """Terminal height.
        """
        if self.interactive:
            return self.term.height

    def write(self, text):
        """Write `text` to terminal.
        """
        self.term.stream.write(text)

    def clear_last_lines(self, n):
        """Clear last N lines of terminal output.
        """
        self.term.stream.write(
            self.term.move_up * n + self.term.clear_eos)
        self.term.stream.flush()

    @contextmanager
    def _moveback(self, n):
        self.term.stream.write(self.term.move_up * n + self.term.clear_eol)
        try:
            yield
        finally:
            self.term.stream.write(self.term.move_down * (n - 1))
            self.term.stream.flush()

    def overwrite_line(self, n, text):
        """Move back N lines and overwrite line with `text`.
        """
        with self._moveback(n):
            self.term.stream.write(text)

    def move_to(self, n):
        """Move back N lines in terminal.
        """
        self.term.stream.write(self.term.move_up * n)


class Tabular(interface.Writer):
    """Interface for writing and updating styled terminal output.

    Parameters
    ----------
    columns : list of str or OrderedDict, optional
        Column names.  An OrderedDict can be used instead of a sequence to
        provide a map of short names to the displayed column names.

        If not given, the keys will be extracted from the first row of data
        that the object is called with, which is particularly useful if the row
        is an OrderedDict.  This argument must be given if this instance will
        not be called with a mapping.
    style : dict, optional
        Each top-level key should be a column name and the value should be a
        style dict that overrides the `default_style` class attribute.  See the
        "Examples" section below.
    stream : stream object, optional
        Write output to this stream (sys.stdout by default).
    interactive : boolean, optional
        Whether stream is considered interactive.  By default, this is
        determined by calling `stream.isatty()`.  If non-interactive, the bold,
        color, and underline keys will be ignored, and the mode will default to
        "final".
    mode : {update, incremental, final}, optional
        Mode of display.
        * update (default): Go back and update the fields.  This includes
          resizing the automated widths.
        * incremental: Don't go back to update anything.
        * final: finalized representation appropriate for redirecting to file

        Defaults to "update" if the stream supports updates and "incremental"
        otherwise.  If the stream is non-interactive, defaults to "final".
    continue_on_failure : bool, optional
        If an asynchronous worker fails, the default behavior is to continue
        and report the failures at the end.  Set this flag to false in order
        to abort writing the table and raise if any exception is received.
    wait_for_top : int, optional
        Wait for the asynchronous workers of this many top-most rows to finish
        before proceeding with a row before adding a row that would take the
        top row off screen.
    max_workers : int, optional
        Use at most this number of concurrent workers when retrieving values
        asynchronously (i.e., when producers are specified as row values).  The
        default matches the default of `concurrent.futures.ThreadPoolExecutor`
        as of Python 3.8: `min(32, os.cpu_count() + 4)`.

    Examples
    --------

    Create a `Tabular` instance for two output fields, "name" and
    "status".

    >>> out = Tabular(["name", "status"], style={"status": {"width": 5}})

    The first field, "name", is taken as the unique ID.  The `style` argument
    is used to override the default width for the "status" field that is
    defined by the class attribute `default_style`.

    Write a row to stdout:

    >>> out({"name": "foo", "status": "OK"})

    Write another row, overriding the style:

    >>> out({"name": "bar", "status": "BAD"},
    ...     style={"status": {"color": "red", "bold": True}})
    """

    def __init__(self, columns=None, style=None, stream=None,
                 interactive=None, mode=None, continue_on_failure=True,
                 wait_for_top=3, max_workers=None):
        in_jupyter = "JPY_PARENT_PID" in os.environ
        if in_jupyter:
            # TODO: More work is needed to render nicely in Jupyter.  For now,
            # just trigger the final, non-interactive rendering.
            mode = mode or "final"
            interactive = False if interactive is None else interactive

        super(Tabular, self).__init__(
            columns, style, stream=stream,
            interactive=interactive, mode=mode,
            continue_on_failure=continue_on_failure,
            wait_for_top=wait_for_top, max_workers=max_workers)
        streamer = TerminalStream(stream=stream, interactive=interactive)
        if streamer.interactive:
            processors = TermProcessors(streamer.term)
        else:
            processors = None
        super(Tabular, self)._init(style, streamer, processors)

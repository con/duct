"""Core pyout interface definitions.
"""

import abc
from collections import defaultdict
from collections import OrderedDict
from collections.abc import Mapping
import concurrent.futures as cfut
from concurrent.futures import ThreadPoolExecutor as Pool
from contextlib import contextmanager
from functools import wraps
import inspect
from itertools import chain
from logging import getLogger
import os
import sys
import threading
import time

from pyout.common import ContentWithSummary
from pyout.common import RowNormalizer
from pyout.common import StyleFields
from pyout.common import UnknownColumns
from pyout.field import PlainProcessors

lgr = getLogger(__name__)


class Stream(object, metaclass=abc.ABCMeta):
    """Output stream interface used by Writer.

    Parameters
    ----------
    stream : stream, optional
        Stream to write output to.  Defaults to sys.stdout.
    interactive : boolean, optional
        Whether this stream is interactive.  If not specified, it will be set
        to the return value of `stream.isatty()`.

    Attributes
    ----------
    interactive : bool
    supports_updates : boolean
        If true, the writer supports updating previous lines.
    """

    supports_updates = True

    def __init__(self, stream=None, interactive=None):
        self.stream = stream or sys.stdout
        if interactive is None:
            self.interactive = self.stream.isatty()
        else:
            self.interactive = interactive
        self.supports_updates = self.interactive

    @abc.abstractproperty
    def width(self):
        """Maximum line width.
        """

    @abc.abstractproperty
    def height(self):
        """Maximum number of rows that are visible."""

    @abc.abstractmethod
    def write(self, text):
        """Write `text`.
        """

    @abc.abstractmethod
    def clear_last_lines(self, n):
        """Clear previous N lines.
        """

    @abc.abstractmethod
    def overwrite_line(self, n, text):
        """Go to the Nth previous line and overwrite it with `text`
        """

    @abc.abstractmethod
    def move_to(self, n):
        """Move the Nth previous line.
        """


def skip_if_aborted(method):
    """Decorate Writer `method` to prevent execution if write has been aborted.
    """

    @wraps(method)
    def wrapped(self, *args, **kwds):
        if self._aborted:
            lgr.debug("Write has been aborted; not calling %r", method)
        else:
            return method(self, *args, **kwds)
    return wrapped


class Writer(object):
    """Base class implementing the core handling logic of pyout output.

    To define a writer, a subclass should inherit Writer and define __init__ to
     call Writer.__init__ and then the _init method.
    """
    def __init__(self, columns=None, style=None, stream=None,
                 interactive=None, mode=None, continue_on_failure=True,
                 wait_for_top=3, max_workers=None):
        if columns and not isinstance(columns, (list, OrderedDict)):
            self._columns = list(columns)
        else:
            self._columns = columns or None

        self._ids = None

        self._last_content_len = 0
        self._last_summary = None
        self._normalizer = None

        self._pool = None
        if max_workers is None and sys.version_info < (3, 8):
            # ThreadPoolExecutor's max_workers didn't get a default until
            # Python 3.5, and that default was changed in 3.8.  Use Python
            # 3.8's default for consistent behavior.
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        self._max_workers = max_workers
        self._lock = None
        self._aborted = False
        self._futures = defaultdict(list)
        self._continue_on_failure = continue_on_failure

        self._wait_for_top = wait_for_top
        self._mode = mode
        self._write_fn = None

        self._stream = None
        self._width_from_stream = False
        self._content = None

    def _init(self, style, streamer, processors=None):
        """Do writer-specific setup.

        Parameters
        ----------
        style : dict
            Style, as passed to __init__.
        streamer : interface.Stream
            A stream interface that takes __init__'s `stream` and `interactive`
            arguments into account.
        processors : field.StyleProcessors, optional
            A writer-specific processors instance.  Defaults to
            field.PlainProcessors().
        """
        self._stream = streamer
        self._init_mode(streamer)

        style = style or {}
        if style.get("width_") is None:
            lgr.debug("Setting width to stream width: %s",
                      self._stream.width)
            style["width_"] = self._stream.width
            self._width_from_stream = True
        self._content = ContentWithSummary(
            StyleFields(style, processors or PlainProcessors()))

    def _init_prewrite(self, table_width=None):
        self._content.init_columns(self._columns, self.ids,
                                   table_width=table_width)
        self._normalizer = RowNormalizer(self._columns,
                                         self._content.fields.style)

    def _init_mode(self, streamer):
        value = self._mode
        lgr.debug("Initializing mode with given value of %s", value)
        if value is None:
            if streamer.interactive:
                if streamer.supports_updates:
                    value = "update"
                else:
                    value = "incremental"
            else:
                value = "final"
        valid = {"update", "incremental", "final"}
        if value not in valid:
            raise ValueError("{!r} is not a valid mode: {!r}"
                             .format(value, valid))

        lgr.debug("Setting write mode to %r", value)
        self._mode = value
        if value == "incremental":
            self._write_fn = self._write_incremental
        elif value == "final":
            self._write_fn = self._write_final
        else:
            if self._stream.supports_updates and self._stream.interactive:
                self._write_fn = self._write_update
            else:
                raise ValueError("Stream {} does not support updates"
                                 .format(self._stream))

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, exc_value, _tb):
        failed = None
        if exc_value is not None:
            self._abort(msg="\n{!r} raised\n".format(exc_value))
        else:
            try:
                failed = self.wait()
            except KeyboardInterrupt:
                lgr.debug("Caught KeyboardInterrupt "
                          "while waiting for asynchronous workers")
                self._abort(msg="\nKeyboard interrupt registered\n")
                # Raise so that caller can decide how to handle.
                raise

        if self._mode == "final":
            self._stream.write(str(self._content))
        if self._mode != "update" and self._last_summary is not None:
            self._stream.write(str(self._last_summary))

        if failed:
            self._print_async_exceptions(failed)

    @property
    def ids(self):
        """A list of unique IDs used to identify a row.

        If not explicitly set, it defaults to the first column name.
        """
        if self._ids is None:
            if self._columns:
                if isinstance(self._columns, OrderedDict):
                    return [list(self._columns.keys())[0]]
                return [self._columns[0]]
        else:
            return self._ids

    @ids.setter
    def ids(self, columns):
        self._ids = columns

    def _process_futures(self):
        """Process each future as it completes.

        If _continue_on_failure is false, raise the exception of the first
        failed future encountered.  Otherwise return a list of futures that had
        an exception.
        """
        failed = []
        lgr.debug("Waiting for asynchronous calls")
        continue_on_failure = self._continue_on_failure
        for id_key, futures in self._futures.items():
            for future in cfut.as_completed(futures):
                lgr.debug("Processing future %s", future)
                if not future.cancelled() and future.exception():
                    if continue_on_failure:
                        failed.append((id_key, future))
                    else:
                        future.result()  # Raise exception.
        return failed

    def _print_async_exceptions(self, failed_futures):
        import traceback

        # Prevent any remaining callbacks from writing to stream.
        with self._write_lock():
            self._aborted = True

        n_failed = len(failed_futures)
        stream = self._stream
        with self._write_lock():
            stream.write("\n\n")
            stream.write("ERROR: {} asynchronous worker{} failed\n\n"
                         .format(n_failed, "" if n_failed == 1 else "s"))
            for id_key, future in failed_futures:
                try:
                    future.result()
                except Exception:
                    stream.write(
                        "Producing value for row {} failed:\n{}\n"
                        .format(id_key, traceback.format_exc()))

    @skip_if_aborted
    def _abort(self, cause=None, msg=None):
        if self._pool is None:
            # No asynchronous calls; there's nothing to abort.
            return

        with self._write_lock():
            self._aborted = cause or True
            stream = self._stream
            if msg:
                stream.write(msg)
            futures = list(chain(*self._futures.values()))
            for f in futures:
                lgr.debug("Calling .cancel() with for %s", f)
                f.cancel()
        n_running = len([f for f in futures if f.running()])
        stream.write("Canceled pending asynchronous workers. "
                     "{} worker{} already running\n"
                     .format(n_running, "" if n_running == 1 else "s"))
        # Note: We can't call shutdown() with wait=True here.  That will
        # trigger a RuntimeError in underlying <thread>.join() call.
        self._pool.shutdown(wait=False)

    def wait(self):
        """Wait for asynchronous calls to return.

        Returns
        -------
        A list of futures for asynchronous calls had an exception.
        """
        lgr.debug("Waiting for asynchronous calls")
        if self._pool is None:
            return
        aborted = self._aborted
        if aborted:
            if isinstance(aborted, cfut.Future):
                aborted.result()  # Raise exception.
        else:
            failed = self._process_futures()
            self._pool.shutdown(wait=True)
            lgr.debug("Pool shut down")
            return failed

    @contextmanager
    def _write_lock(self):
        """Acquire and release the lock around output calls.

        This should allow multiple threads or processes to write output
        reliably.  Code that modifies the `_content` attribute should also do
        so within this context.
        """
        if self._lock:
            lgr.debug("Acquiring write lock")
            self._lock.acquire()
        try:
            yield
        finally:
            if self._lock:
                lgr.debug("Releasing write lock")
                self._lock.release()

    def _write(self, row, style=None):
        with self._write_lock():
            if self._width_from_stream and self._mode != "final":
                width_current = self._content.fields.style["width_"]
                width_stream = self._stream.width
                if width_stream is not None and width_current != width_stream:
                    lgr.debug("Current stream width (%d) different "
                              "than last recorded (%d). Updating",
                              width_stream, width_current)
                    self._init_prewrite(table_width=width_stream)
            try:
                self._write_fn(row, style)
            except UnknownColumns as exc:
                self._columns.extend(exc.unknown_columns)
                self._init_prewrite()
                self._write_fn(row, style)

    def _get_last_summary_length(self):
        last_summary = self._last_summary
        return len(last_summary.splitlines()) if last_summary else 0

    def _write_update(self, row, style=None):
        last_summary_len = self._get_last_summary_length()

        content, status, summary = self._content.update(row, style)

        if last_summary_len > 0:
            # Clear the summary because 1) it has very likely changed, 2)
            # it makes the counting for row updates simpler, 3) and it is
            # possible for the summary lines to shrink.
            lgr.debug("Clearing summary of %d line(s)", last_summary_len)
            self._stream.clear_last_lines(last_summary_len)


        single_row_updated = False
        if isinstance(status, int):
            height = self._stream.height
            n_visible = min(
                height - last_summary_len - 1,  # -1 for current line.
                self._last_content_len)

            n_back = self._last_content_len - status
            if n_back > n_visible:
                lgr.debug("Cannot move back %d rows for update; "
                          "only %d visible rows",
                          n_back, n_visible)
                status = "repaint"
                content = str(self._content)
            else:
                lgr.debug("Moving up %d line(s) to overwrite line %d with %r",
                          n_back, status, row)
                self._stream.overwrite_line(n_back, content)
                single_row_updated = True

        if not single_row_updated:
            if status == "repaint":
                lgr.debug("Moving up %d line(s) to repaint the whole thing. "
                          "Blame row %r",
                          self._last_content_len, row)
                self._stream.move_to(self._last_content_len)
            self._stream.write(content)

        if summary is not None:
            self._stream.write(summary)
            lgr.debug("Wrote summary")
        self._last_content_len = len(self._content)
        self._last_summary = summary

    def _write_incremental(self, row, style=None):
        content, status, summary = self._content.update(row, style)
        if isinstance(status, int):
            lgr.debug("Duplicating line %d with %r", status, row)
        elif status == "repaint":
            lgr.debug("Duplicating the whole thing.  Blame row %r", row)
        self._stream.write(content)
        self._last_summary = summary

    def _write_final(self, row, style=None):
        _, _, summary = self._content.update(row, style)
        self._last_summary = summary

    @skip_if_aborted
    def _write_async_result(self, id_vals, cols, result):
        lgr.debug("Received result for %s: %s",
                  cols, result)
        if isinstance(result, Mapping):
            lgr.debug("Processing result as mapping")
        elif isinstance(result, tuple):
            lgr.debug("Processing result as tuple")
            result = dict(zip(cols, result))
        elif len(cols) == 1:
            lgr.debug("Processing result as atom")
            result = {cols[0]: result}
        else:
            raise ValueError(
                "Expected tuple or mapping for columns {!r}, got {!r}"
                .format(cols, result))
        result.update(id_vals)
        self._write(result)

    @skip_if_aborted
    def _start_callables(self, row, callables):
        """Start running `callables` asynchronously.
        """
        id_key = tuple(row[c] for c in self.ids)
        id_vals = {c: row[c] for c in self.ids}

        if self._pool is None:
            lgr.debug("Initializing pool with max workers=%s",
                      self._max_workers)
            self._pool = Pool(max_workers=self._max_workers)
        if self._lock is None:
            lgr.debug("Initializing lock")
            self._lock = threading.Lock()

        for cols, fn in callables:
            gen = None
            if inspect.isgeneratorfunction(fn):
                gen = fn()
            elif inspect.isgenerator(fn):
                gen = fn

            def check_result(future):
                if future.cancelled():
                    ok = False
                elif future.exception():
                    ok = False
                    if not self._continue_on_failure:
                        self._abort(cause=future)
                else:
                    ok = True
                return ok

            if gen:
                lgr.debug("Wrapping generator for cols %r of row %r",
                          cols, id_vals)

                def async_fn():
                    for i in gen:
                        self._write_async_result(id_vals, cols, i)

                callback = check_result
            else:
                async_fn = fn

                def callback(future):
                    if check_result(future):
                        self._write_async_result(
                            id_vals, cols, future.result())

            try:
                future = self._pool.submit(async_fn)
            except RuntimeError as exc:
                # We can get here if, between entering this method call and
                # calling .submit(), _aborted was set by a callback.
                if self._aborted:
                    lgr.debug(
                        "Submitting callable for %s failed "
                        "because pool is already shutdown: %s",
                        id_key, exc)
                else:
                    raise
            else:
                future.add_done_callback(callback)
                lgr.debug("Registering future %s for %s", future, id_key)
                self._futures[id_key].append(future)

    def top_nrows_done(self, n, height=None):
        """Check if the top N rows' asynchronous workers are done.

        Parameters
        ----------
        n : int
            Consider this many of the top rows (e.g., 1 would consider just the
            first row).
        height : int, optional
            Take this as the terminal height instead of querying the stream.

        Returns
        -------
        True if the asynchronous workers for the top N rows have finished, and
        False if they have not.  None is returned if Tabular is not operating
        in "update" mode.
        """
        if self._mode != "update" or not self._content:
            return None
        #          0|..                                  <|
        #          1|..                                   |
        #          2|..                                   |
        # top_idx  3|oo <|       <|          <|           |
        #          4|oo  |--- n=3 |           |           |
        #          5|oo <|        |           |           |--- content
        #          6|oo           |           |           |    length
        #          7|oo           |--- n_free |           | (including header)
        #          8|oo           |           |    stream |
        #          9|oo           |           |--- height |
        #         10|oo          <|           |          <|
        #           |oo <|                    |
        #           |oo  |--- summary         |
        #           |oo <|                    |
        #           |oo <------ cursor       <|
        last_summary_len = self._get_last_summary_length()
        n_free = (height or self._stream.height) - last_summary_len - 1
        top_idx = self._last_content_len - n_free

        if top_idx < 0:
            # The content lines haven't yet filled the screen.
            return True

        idxs = (top_idx + i for i in range(min(n, n_free)))
        id_keys = (self._content.get_idkey(i) for i in idxs
                   if i is not None)

        futures = self._futures
        top_futures = list(chain(*(futures[k] for k in id_keys)))
        if not top_futures:
            # These rows have no registered producers.
            return True
        return all(f.done() for f in top_futures)

    def _maybe_wait_on_top_rows(self):
        n = self._wait_for_top
        if n:
            waited = 0
            secs = 0.5
            height = self._stream.height
            while self.top_nrows_done(n, height) is False:
                time.sleep(secs)
                waited += 1
            if waited:
                lgr.debug("Waited for %s cycles of sleeping %s seconds",
                          waited, secs)
                # Wait a bit longer so that the caller has a chance to see the
                # last updated row if it about to go off screen.
                time.sleep(secs)

    @skip_if_aborted
    def __call__(self, row, style=None):
        """Write styled `row`.

        Parameters
        ----------
        row : mapping, sequence, or other
            If a mapping is given, the keys are the column names and values are
            the data to write.  After the initial set of columns is defined
            (via the constructor's `columns` argument or based on inferring the
            names from the first row passed), rows can still include new keys,
            in which case the list of known columns will be expanded.

            For a sequence, the items represent the values and are taken to be
            in the same order as the constructor's `columns` argument.  Any
            other object type should have an attribute for each column
            specified via `columns`.

            Instead of a plain value, a column's value can be a tuple of the
            form (initial_value, producer).  If a producer is is a generator
            function or a generator object, each item produced replaces
            `initial_value`.  Otherwise, a producer should be a function that
            will be called with no arguments and that returns the value with
            which to replace `initial_value`.  For both generators and normal
            functions, the execution will happen asynchronously.

            Directly supplying a producer as the value rather than
            (initial_value, producer) is shorthand for ("", producer).

            The producer can return an update for multiple columns.  To do so,
            the keys of `row` should include a tuple with the column names and
            the produced value should be a tuple with the same order as the key
            or a mapping from column name to the updated value.  A mapping's
            keys may include unknown columns; these will be added to the set of
            known columns.

            Using the (initial_value, producer) form requires some additional
            steps.  The `ids` property should be set unless the first column
            happens to be a suitable id.  Also, to instruct the program to wait
            for the updated values, the instance calls should be followed by a
            call to the `wait` method or the instance should be used as a
            context manager.
        style : dict, optional
            Each top-level key should be a column name and the value should be
            a style dict that overrides the class instance style.
        """
        self._maybe_wait_on_top_rows()
        if self._columns is None:
            self._columns = self._infer_columns(row)
            lgr.debug("Inferred columns: %r", self._columns)
        if self._normalizer is None:
            self._init_prewrite()

        callables, row = self._normalizer(row)
        self._write(row, style)
        if callables:
            lgr.debug("Starting callables for row %r", row)
            self._start_callables(row, callables)

    @staticmethod
    def _infer_columns(row):
        try:
            columns = list(row.keys())
        except AttributeError:
            raise ValueError("Can't infer columns from data")
        # Make sure we don't have any multi-column keys.
        flat = []
        for column in columns:
            if isinstance(column, tuple):
                flat.extend(column)
            else:
                flat.append(column)
        return flat

    def __getitem__(self, key):
        """Get the (normalized) row for `key`.

        This interface is focused on _writing_ output, and the caller usually
        knows the values.  However, this method can be useful for retrieving
        values that were produced asynchronously (see __call__).

        Parameters
        ----------
        key : tuple
            Unique ID for a row, as specified by the `ids` property.

        Returns
        -------
        A dictionary with the row's current value.
        """
        try:
            return self._content[key]
        except KeyError as exc:
            # Suppress context.
            raise KeyError(exc) from None

    @contextmanager
    def outside_write(self, clear=False):
        """Stop writing rows and yield control to the caller.

        This context manager allows callers to interrupt the table output while
        writing their own output.  On exit, the entire table is rewritten.

        Parameters
        ----------
        clear : bool
            Before yielding to the caller, clear the visible rows.  This only
            has an effect in "update" mode.
        """
        update = self._mode == "update"
        with self._write_lock():
            if update and clear:
                n_lines = min(
                    # -1 for the last empty line of screen.
                    self._stream.height - 1,
                    self._last_content_len + self._get_last_summary_length())
                self._stream.clear_last_lines(n_lines)
            yield
            if update:
                self._stream.write(str(self._content))
                last_summary = self._last_summary
                if last_summary:
                    self._stream.write(last_summary)

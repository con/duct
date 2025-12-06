"""Define a "field" based on a sequence of processor functions.
"""

from collections import defaultdict
from collections import OrderedDict
from itertools import chain
from logging import getLogger
import re
import sys

from pyout.elements import value_type

lgr = getLogger(__name__)


class Field(object):
    """Render values based on a list of processors.

    A Field instance is a template for a string that is defined by its width,
    text alignment, and its "processors".

    When a field is called with a value, the value is rendered in three steps.

                       pre -> format -> post

    During the first step, the value is fed through the list of pre-format
    processor functions.  The result of this value is then formatted as a
    string with the specified width and alignment.  Finally, this result is fed
    through the list of the post-format processors.  The rendered string is the
    result returned by the last processor

    Parameters
    ----------
    width : int, optional
    align : {'left', 'right', 'center'}, optional
    default_keys, other_keys : sequence, optional
        Together, these define the "registered" set of processor keys that can
        be used in the `pre` and `post` dicts.  Any key given to the `add`
        method or instance call must be contained in one of these collections.

        The processor lists for `default_keys` is used when the instance is
        called without a list of `keys`.  `other_keys` defines additional keys
        that can be passed as the `keys` argument to the instance call.

    Attributes
    ----------
    width : int
    registered_keys : set
        Set of available keys.
    default_keys : list
        Defines which processor lists are called by default and in what order.
        The values can be overridden by the `keys` argument when calling the
        instance.
    pre, post : dict of lists
        These map each registered key to a list of processors.  Conceptually,
        `pre` and `post` are a list of functions that form a pipeline, but they
        are structured as a dict of lists to allow different processors to be
        grouped by key.  By specifying keys, the caller can control which
        groups are "enabled".
    """

    _align_values = {"left": "<", "right": ">", "center": "^"}

    def __init__(self, width=10, align="left",
                 default_keys=None, other_keys=None):
        self._width = width
        self._align = align
        self._fmt = self._build_format()

        self.default_keys = default_keys or []
        self.registered_keys = set(chain(self.default_keys, other_keys or []))

        self.pre = defaultdict(list)
        self.post = defaultdict(list)

    def _check_if_registered(self, key):
        if key not in self.registered_keys:
            raise ValueError(
                "key '{}' was not specified at initialization".format(key))

    def add(self, kind, key, *values):
        """Add processor functions.

        Any previous list of processors for `kind` and `key` will be
        overwritten.

        Parameters
        ----------
        kind : {"pre", "post"}
        key : str
            A registered key.  Add the functions (in order) to this key's list
            of processors.
        *values : callables
            Processors to add.
        """
        if kind == "pre":
            procs = self.pre
        elif kind == "post":
            procs = self.post
        else:
            raise ValueError("kind is not 'pre' or 'post'")
        self._check_if_registered(key)
        procs[key] = values

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value
        self._fmt = self._build_format()

    def _build_format(self):
        align = self._align_values[self._align]
        return "".join(["{:", align, str(self.width), "}"])

    def _format(self, _, result):
        """Wrap format call as a two-argument processor function.
        """
        return self._fmt.format(str(result))

    def __call__(self, value, keys=None, exclude_post=False):
        """Render `value` by feeding it through the processors.

        Parameters
        ----------
        value : str
        keys : sequence, optional
            These lists define which processor lists are called and in what
            order.  If not specified, the `default_keys` attribute will be
            used.
        exclude_post : bool, optional
            Whether to return the value after the format step rather than
            feeding it through post-format processors.
        """
        lgr.debug("Rendering field with value %r and %s keys %r",
                  value,
                  "default" if keys is None else "non-default",
                  self.default_keys)
        if keys is None:
            keys = self.default_keys
        for key in keys:
            self._check_if_registered(key)

        pre_funcs = chain(*(self.pre[k] for k in keys))
        if exclude_post:
            post_funcs = []
        else:
            post_funcs = chain(*(self.post[k] for k in keys))

        funcs = chain(pre_funcs, [self._format], post_funcs)
        result = value
        for fn in funcs:
            result = fn(value, result)
        return result


class Nothing(object):
    """Internal class to represent missing values.

    This is used instead of a built-in like None, "", or 0 to allow us to
    unambiguously identify a missing value.  In terms of methods, it tries to
    mimic the string `text` (an empty string by default) because that behavior
    is the most useful internally for formatting the output.

    Parameters
    ----------
    text : str, optional
        Text to use for string representation of this object.
    """

    def __init__(self, text=""):
        self._text = text

    def __str__(self):
        return self._text

    def __add__(self, right):
        return str(self) + right

    def __radd__(self, left):
        return left + str(self)

    def __bool__(self):
        return False

    def __format__(self, format_spec):
        return self._text.__format__(format_spec)


def _pass_nothing_through(proc):
    """Make processor function `proc` skip Nothing objects.
    """
    def wrapped(value, result):
        return result if isinstance(value, Nothing) else proc(value, result)
    return wrapped


class StyleFunctionError(Exception):
    """Signal that a style function failed.
    """
    def __init__(self, function, exc_type, exc_value):
        msg = "{} raised {}\n  {}".format(function, exc_type.__name__,
                                          exc_value)
        super(StyleFunctionError, self).__init__(msg)


class StyleProcessors(object):
    """A base class for generating Field.processors for styled output.

    Attributes
    ----------
    style_keys : list of tuples
        Each pair consists of a style attribute (e.g., "bold") and the expected
        type.
    """

    # Ordering the dict isn't required, but we'll loop over this to generate
    # processors, and it'd be good to have a predictable order across calls.
    style_types = OrderedDict([("bold", bool),
                               ("underline", bool),
                               ("color", str)])

    def render(self, style_attr, value):
        """Render `value` according to a style key.

        Parameters
        ----------
        style_attr : str
            A style attribute (e.g., "bold" or "blue").
        value : str
            The value to render.

        Returns
        -------
        An output-specific styling of `value` (str).
        """
        raise NotImplementedError

    @staticmethod
    def transform(function):
        """Return a processor for a style's "transform" function.
        """
        def transform_fn(_, result):
            lgr.debug("Transforming %r with %r", result, function)
            try:
                return function(result)
            except:
                exctype, value, tb = sys.exc_info()
                try:
                    new_exc = StyleFunctionError(function, exctype, value)
                    # Remove the "During handling ..." since we're
                    # reraising with the traceback.
                    raise new_exc.with_traceback(tb) from None
                finally:
                    # Remove circular reference.
                    # https://docs.python.org/2/library/sys.html#sys.exc_info
                    del tb
        return transform_fn

    def by_key(self, style_key, style_value):
        """Return a processor for a "simple" style value.

        Parameters
        ----------
        style_key : str
            A style key.
        style_value : bool or str
            A "simple" style value that is either a style attribute (str) and a
            boolean flag indicating to use the style attribute named by
            `style_key`.

        Returns
        -------
        A function.
        """
        if self.style_types[style_key] is bool:
            style_attr = style_key
        else:
            style_attr = style_value

        def proc(_, result):
            return self.render(style_attr, result)
        return proc

    def by_lookup(self, style_key, style_value):
        """Return a processor that extracts the style from `mapping`.

        Parameters
        ----------
        style_key : str
            A style key.
        style_value : dict
            A dictionary with a "lookup" key whose value is a "mapping" style
            value that maps a field value to either a style attribute (str) and
            a boolean flag indicating to use the style attribute named by
            `style_key`.

        Returns
        -------
        A function.
        """
        style_attr = style_key if self.style_types[style_key] is bool else None
        mapping = style_value["lookup"]

        def proc(value, result):
            try:
                lookup_value = mapping[value]
            except KeyError:
                lgr.debug("by_lookup: Key %r not found in mapping %s",
                          value, mapping)
                lookup_value = None
            except TypeError:
                lgr.debug("by_lookup: Key %r not hashable", value)
                lookup_value = None

            if not lookup_value:
                return result
            return self.render(style_attr or lookup_value, result)
        return proc

    def by_re_lookup(self, style_key, style_value, re_flags=0):
        """Return a processor for a "re_lookup" style value.

        Parameters
        ----------
        style_key : str
            A style key.
        style_value : dict
            A dictionary with a "re_lookup" style value that consists of a
            sequence of items where each item should have the form `(regexp,
            x)`, where regexp is a regular expression to match against the
            field value and x is either a style attribute (str) and a boolean
            flag indicating to use the style attribute named by `style_key`.
        re_flags : int
            Passed through as flags argument to re.compile.

        Returns
        -------
        A function.
        """
        style_attr = style_key if self.style_types[style_key] is bool else None
        regexps = [(re.compile(r, flags=re_flags), v)
                   for r, v in style_value["re_lookup"]]

        def proc(value, result):
            if not isinstance(value, str):
                lgr.debug("by_re_lookup: Skipping non-string value %r",
                          value)
                return result
            for r, lookup_value in regexps:
                if r.search(value):
                    if not lookup_value:
                        return result
                    return self.render(style_attr or lookup_value, result)
            return result
        return proc

    def by_interval_lookup(self, style_key, style_value):
        """Return a processor for an "interval" style value.

        Parameters
        ----------
        style_key : str
            A style key.
        style_value : dict
            A dictionary with an "interval" key whose value consists of a
            sequence of tuples where each tuple should have the form `(start,
            end, x)`, where start is the start of the interval (inclusive), end
            is the end of the interval, and x is either a style attribute (str)
            and a boolean flag indicating to use the style attribute named by
            `style_key`.

        Returns
        -------
        A function.
        """
        style_attr = style_key if self.style_types[style_key] is bool else None
        intervals = style_value["interval"]

        def proc(value, result):
            try:
                value = float(value)
            except Exception as exc:
                lgr.debug("by_interval_lookup: Skipping %r: %s", value, exc)
                return result

            for start, end, lookup_value in intervals:
                if start is None:
                    start = float("-inf")
                if end is None:
                    end = float("inf")

                if start <= value < end:
                    if not lookup_value:
                        return result
                    return self.render(style_attr or lookup_value, result)
            return result
        return proc

    def pre_from_style(self, column_style):
        """Yield pre-format processors based on `column_style`.

        Parameters
        ----------
        column_style : dict
            A style where the top-level keys correspond to style attributes
            such as "bold" or "color".

        Returns
        -------
        A generator object.
        """
        if "transform" in column_style:
            yield _pass_nothing_through(
                self.transform(column_style["transform"]))

    def post_from_style(self, column_style):
        """Yield post-format processors based on `column_style`.

        Parameters
        ----------
        column_style : dict
            A style where the top-level keys correspond to style attributes
            such as "bold" or "color".

        Returns
        -------
        A generator object.
        """
        flanks = Flanks()
        yield flanks.split_flanks

        fns = {"simple": self.by_key,
               "lookup": self.by_lookup,
               "re_lookup": self.by_re_lookup,
               "interval": self.by_interval_lookup}

        for key in self.style_types:
            if key not in column_style:
                continue

            vtype = value_type(column_style[key])
            fn = fns[vtype]
            args = [key, column_style[key]]
            if vtype == "re_lookup":
                args.append(sum(getattr(re, f)
                                for f in column_style.get("re_flags", [])))
            yield _pass_nothing_through(fn(*args))

        yield flanks.join_flanks


class Flanks(object):
    """A pair of processors that split and rejoin flanking whitespace.
    """

    flank_re = re.compile(r"(\s*)(.*\S)(\s*)\Z", flags=re.DOTALL)

    def __init__(self):
        self.left, self.right = None, None

    def split_flanks(self, _, result):
        """Return `result` without flanking whitespace.
        """
        if not result.strip():
            self.left, self.right = "", ""
            return result

        match = self.flank_re.match(result)
        if not match:
            raise RuntimeError(
                "Flank regexp unexpectedly did not match result: "
                "{!r} (type: {})"
                .format(result, type(result)))
        self.left, self.right = match.group(1), match.group(3)
        return match.group(2)

    def join_flanks(self, _, result):
        """Add whitespace from last `split_flanks` call back to `result`.
        """
        return self.left + result + self.right


class PlainProcessors(StyleProcessors):
    """Ignore color, bold, or underline styling.
    """

    style_types = {}


class TermProcessors(StyleProcessors):
    """Generate Field.processors for styled Terminal output.

    Parameters
    ----------
    term : blessed.Terminal or blessings.Terminal

    Notes
    -----
    * Eventually we may want to retire blessings:
        https://github.com/pyout/pyout/issues/136
    """

    def __init__(self, term):
        self.term = term

    def render(self, style_attr, value):
        """Prepend terminal code for `key` to `value`.

        Parameters
        ----------
        style_attr : str
            A style attribute (e.g., "bold" or "blue").
        value : str
            The value to render.

        Returns
        -------
        The code for `key` (e.g., "\x1b[1m" for bold) plus the
        original value.
        """
        if not value.strip():
            # We've got an empty string.  Don't bother adding any
            # codes.
            return value
        return str(getattr(self.term, style_attr)) + value

    def _maybe_reset(self):
        def proc(_, result):
            if "\x1b" in result:
                return result + self.term.normal
            return result
        return proc

    def post_from_style(self, column_style):
        """A Terminal-specific reset to StyleProcessors.post_from_style.
        """
        for proc in super(TermProcessors, self).post_from_style(column_style):
            if proc.__name__ == "join_flanks":
                # Reset any codes before adding back whitespace.
                yield self._maybe_reset()
            yield proc

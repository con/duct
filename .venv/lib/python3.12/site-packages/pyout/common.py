"""Common components for styled output.

This modules contains things that would be shared across outputters if there
were any besides Tabular.  The Tabular class, though, still contains a good
amount of general logic that should be extracted if any other outputter is
actually added.
"""

from collections import defaultdict
from collections import namedtuple
from collections import OrderedDict
from collections.abc import Mapping
from collections.abc import Sequence
from functools import partial
import inspect
from logging import getLogger

from pyout import elements
from pyout.field import Field
from pyout.field import Nothing
from pyout.truncate import Truncater
from pyout.summary import Summary

lgr = getLogger(__name__)
NOTHING = Nothing()


class UnknownColumns(Exception):
    """The row has unknown columns.

    Parameters
    ----------
    unknown_columns : list
    """

    def __init__(self, unknown_columns):
        self.unknown_columns = unknown_columns
        super(UnknownColumns, self).__init__(
            "Unknown columns: {}".format(unknown_columns))


class RowNormalizer(object):
    """Transform various input data forms to a common form.

    An un-normalized row can be one of three kinds:

      * a mapping from column names to keys

      * a sequence of values in the same order as `columns`

      * any other value will be taken as an object where the column values can
        be accessed via an attribute with the same name

    To normalize a row, it is

      * converted to a dict that maps from column names to values

      * all callables are stripped out and replaced with their initial values

      * if the value for a column is missing, it is replaced with a Nothing
        instance whose value is specified by the column's style (an empty
        string by default)

    Parameters
    ----------
    columns : sequence of str
        Column names.
    style : dict, optional
        Column styles.

    Attributes
    ----------
    method : callable
        A function that takes a row and returns a normalized one.  This is
        chosen at time of the first call.  All subsequent calls should use the
        same kind of row.
    nothings : dict
        Maps column name to the placeholder value to use if that column is
        missing.
    """

    def __init__(self, columns, style):
        self._columns = columns
        self.method = None

        self.delayed = defaultdict(list)
        self.delayed_columns = set()
        self.nothings = {}  # column => missing value
        self._known_columns = set()

        for column in columns:
            cstyle = style[column]

            if "delayed" in cstyle:
                lgr.debug("Registered delay for column %r", column)
                value = cstyle["delayed"]
                group = column if value is True else value
                self.delayed[group].append(column)
                self.delayed_columns.add(column)

            if "missing" in cstyle:
                self.nothings[column] = Nothing(cstyle["missing"])
            else:
                self.nothings[column] = NOTHING

    def __call__(self, row):
        """Normalize `row`

        Parameters
        ----------
        row : mapping, sequence, or other
            Data to normalize.

        Returns
        -------
        A tuple (callables, row), where `callables` is a list (as returned by
        `strip_callables`) and `row` is the normalized row.
        """
        if self.method is None:
            self.method = self._choose_normalizer(row)
        return self.method(row)

    def _choose_normalizer(self, row):
        if isinstance(row, Mapping):
            getter = self.getter_dict
        elif isinstance(row, Sequence):
            getter = self.getter_seq
        else:
            getter = self.getter_attrs
        lgr.debug("Selecting %s as normalizer", getter.__name__)
        return partial(self._normalize, getter)

    def _normalize(self, getter, row):
        columns = self._columns
        if isinstance(row, Mapping):
            callables0 = self.strip_callables(row)
            # The row may have new columns.  All we're doing here is keeping
            # them around in the normalized row so that downstream code can
            # react to them.
            known = self._known_columns
            new_cols = [c for c in row.keys() if c not in known]
            if new_cols:
                if isinstance(self._columns, OrderedDict):
                    columns = list(self._columns)
                columns = columns + new_cols
        else:
            callables0 = []

        norm_row = self._maybe_delay(getter, row, columns)
        # We need a second pass with strip_callables because norm_row will
        # contain new callables for any delayed values.
        callables1 = self.strip_callables(norm_row)
        return callables0 + callables1, norm_row

    def _maybe_delay(self, getter, row, columns):
        row_norm = {}
        for column in columns:
            if column not in self.delayed_columns:
                row_norm[column] = getter(row, column)

        def delay(cols):
            return lambda: {c: getter(row, c) for c in cols}

        for cols in self.delayed.values():
            key = cols[0] if len(cols) == 1 else tuple(cols)
            lgr.debug("Delaying %r for row %r", cols, row)
            row_norm[key] = delay(cols)
        return row_norm

    def strip_callables(self, row):
        """Extract callable values from `row`.

        Replace the callable values with the initial value (if specified) or
        an empty string.

        Parameters
        ----------
        row : mapping
            A data row.  The keys are either a single column name or a tuple of
            column names.  The values take one of three forms: 1) a
            non-callable value, 2) a tuple (initial_value, callable), 3) or a
            single callable (in which case the initial value is set to an empty
            string).

        Returns
        -------
        list of (column, callable)
        """
        callables = []
        to_delete = []
        to_add = []
        for columns, value in row.items():
            if isinstance(value, tuple):
                initial, fn = value
            else:
                initial = NOTHING
                # Value could be a normal (non-callable) value or a
                # callable with no initial value.
                fn = value

            if callable(fn) or inspect.isgenerator(fn):
                lgr.debug("Using %r as the initial value "
                          "for columns %r in row %r",
                          initial, columns, row)
                if not isinstance(columns, tuple):
                    columns = columns,
                else:
                    to_delete.append(columns)
                for column in columns:
                    to_add.append((column, initial))
                callables.append((columns, fn))

        for column, value in to_add:
            row[column] = value
        for multi_columns in to_delete:
            del row[multi_columns]

        return callables

    # Input-specific getters.  These exist as their own methods so that they
    # can be wrapped in a callable and delayed.

    def getter_dict(self, row, column):
        # Note: We .get() from `nothings` because `row` is permitted to have an
        # unknown column.
        return row.get(column, self.nothings.get(column, NOTHING))

    def getter_seq(self, row, column):
        col_to_idx = {c: idx for idx, c in enumerate(self._columns)}
        return row[col_to_idx[column]]

    def getter_attrs(self, row, column):
        return getattr(row, column, self.nothings[column])


class StyleFields(object):
    """Generate Fields based on the specified style and processors.

    Parameters
    ----------
    style : dict
        A style that follows the schema defined in pyout.elements.
    procgen : StyleProcessors instance
        This instance is used to generate the fields from `style`.
    """

    def __init__(self, style, procgen):
        self.init_style = style
        self.procgen = procgen

        self.style = None
        self.columns = None
        self.autowidth_columns = {}
        self._known_columns = set()

        self.width_fixed = None
        self.width_separtor = None
        self.fields = None
        self._truncaters = {}

        self.hidden = {}  # column => {True, "if-empty", False}
        self._visible_columns = None  # cached list of visible columns

        self._table_width = None

    def build(self, columns, table_width=None):
        """Build the style and fields.

        Parameters
        ----------
        columns : list of str
            Column names.
        table_width : int, optional
            Table width to use instead of the previously specified width.
        """
        self.columns = columns
        self._known_columns = set(columns)
        default = dict(elements.default("default_"),
                       **self.init_style.get("default_", {}))
        self.style = elements.adopt({c: default for c in columns},
                                    self.init_style)

        # Store special keys in _style so that they can be validated.
        self.style["default_"] = default
        self.style["header_"] = self._compose("header_", {"align", "width"})
        self.style["aggregate_"] = self._compose("aggregate_",
                                                 {"align", "width"})
        self.style["separator_"] = self.init_style.get(
            "separator_", elements.default("separator_"))
        lgr.debug("Validating style %r", self.style)
        if table_width is not None:
            self._table_width = table_width
        elif self._table_width is None:
            self._table_width = self.init_style.get(
                "width_", elements.default("width_"))
        self.style["width_"] = self._table_width
        elements.validate(self.style)

        self._setup_fields()

        self.hidden = {c: self.style[c]["hide"] for c in columns}
        self._reset_width_info()

    def _compose(self, name, attributes):
        """Construct a style taking `attributes` from the column styles.

        Parameters
        ----------
        name : str
            Name of main style (e.g., "header_").
        attributes : set of str
            Adopt these elements from the column styles.

        Returns
        -------
        The composite style for `name`.
        """
        name_style = self.init_style.get(name, elements.default(name))
        if self.init_style is not None and name_style is not None:
            result = {}
            for col in self.columns:
                cstyle = {k: v for k, v in self.style[col].items()
                          if k in attributes}
                result[col] = dict(cstyle, **name_style)
            return result

    def _setup_fields(self):
        fields = {}
        style = self.style
        width_table = style["width_"]

        def frac_to_int(x):
            if x and 0 < x < 1:
                result = int(x * width_table)
                lgr.debug("Converted fraction %f to %d", x, result)
            else:
                result = x
            return result

        for column in self.columns:
            lgr.debug("Setting up field for column %r", column)
            cstyle = style[column]
            style_width = cstyle["width"]

            # Convert atomic values into the equivalent complex form.
            if style_width == "auto":
                style_width = {}
            elif not isinstance(style_width, Mapping):
                style_width = {"width": style_width}

            is_auto = "width" not in style_width
            if is_auto:
                lgr.debug("Automatically adjusting width for %s", column)
                width = frac_to_int(style_width.get("min", 0))
                wmax = frac_to_int(style_width.get("max"))
                autoval = {"max": wmax, "min": width,
                           "weight": style_width.get("weight", 1)}
                self.autowidth_columns[column] = autoval
                lgr.debug("Stored auto-width value for column %r: %s",
                          column, autoval)
            else:
                if "min" in style_width or "max" in style_width:
                    raise ValueError(
                        "'min' and 'max' are incompatible with 'width'")
                width = frac_to_int(style_width["width"])
                lgr.debug("Setting width of column %r to %d",
                          column, width)

            # We are creating a distinction between "width" processors, that we
            # always want to be active and "default" processors that we want to
            # be active unless there's an overriding style (i.e., a header is
            # being written or the `style` argument to __call__ is specified).
            field = Field(width=width, align=cstyle["align"],
                          default_keys=["width", "default"],
                          other_keys=["override"])
            field.add("pre", "default",
                      *(self.procgen.pre_from_style(cstyle)))
            truncater = Truncater(
                width,
                style_width.get("marker", True),
                style_width.get("truncate", "right"))
            field.add("post", "width", truncater.truncate)
            field.add("post", "default",
                      *(self.procgen.post_from_style(cstyle)))
            fields[column] = field
            self._truncaters[column] = truncater
        self.fields = fields

    @property
    def has_header(self):
        """Whether the style specifies a header.
        """
        return self.style["header_"] is not None

    @property
    def visible_columns(self):
        """List of columns that are not marked as hidden.

        This value is cached and becomes invalid if column visibility has
        changed since the last `render` call.
        """
        if self._visible_columns is None:
            hidden = self.hidden
            self._visible_columns = [c for c in self.columns if not hidden[c]]
        return self._visible_columns

    def _check_widths(self):
        visible = self.visible_columns
        autowidth_columns = self.autowidth_columns
        width_table = self.style["width_"]
        if width_table is None:
            # The table is unbounded (non-interactive).
            return

        if len(visible) > width_table:
            raise elements.StyleError(
                "Number of visible columns exceeds available table width")

        width_fixed = self.width_fixed
        width_auto = width_table - width_fixed

        if width_auto < len(set(autowidth_columns).intersection(visible)):
            raise elements.StyleError(
                "The number of visible auto-width columns ({}) "
                "exceeds the available width ({})"
                .format(len(autowidth_columns), width_auto))

    def _set_fixed_widths(self):
        """Set fixed-width attributes.

        Previously calculated values are invalid if the number of visible
        columns changes.  Call _reset_width_info() in that case.
        """
        visible = self.visible_columns
        ngaps = len(visible) - 1
        width_separtor = len(self.style["separator_"]) * ngaps
        lgr.debug("Calculated separator width as %d", width_separtor)

        autowidth_columns = self.autowidth_columns
        fields = self.fields
        width_fixed = sum([sum(fields[c].width for c in visible
                               if c not in autowidth_columns),
                           width_separtor])
        lgr.debug("Calculated fixed width as %d", width_fixed)

        self.width_separtor = width_separtor
        self.width_fixed = width_fixed

    def _reset_width_info(self):
        """Reset visibility-dependent information.
        """
        self._visible_columns = None
        self._set_fixed_widths()
        self._check_widths()

    def _set_widths(self, row, proc_group):
        """Update auto-width Fields based on `row`.

        Parameters
        ----------
        row : dict
        proc_group : {'default', 'override'}
            Whether to consider 'default' or 'override' key for pre- and
            post-format processors.

        Returns
        -------
        True if any widths required adjustment.
        """
        autowidth_columns = self.autowidth_columns
        fields = self.fields

        width_table = self.style["width_"]
        width_fixed = self.width_fixed
        if width_table is None:
            width_auto = float("inf")
        else:
            width_auto = width_table - width_fixed

        if not autowidth_columns:
            return False

        # Check what width each row wants.
        lgr.debug("Checking width for row %r", row)
        hidden = self.hidden
        for column in autowidth_columns:
            if hidden[column]:
                lgr.debug("%r is hidden; setting width to 0",
                          column)
                autowidth_columns[column]["wants"] = 0
                continue

            field = fields[column]
            lgr.debug("Checking width of column %r (current field width: %d)",
                      column, field.width)
            # If we've added any style transform functions as pre-format
            # processors, we want to measure the width of their result rather
            # than the raw value.
            if field.pre[proc_group]:
                value = field(row[column], keys=[proc_group],
                              exclude_post=True)
            else:
                value = row[column]
            value = str(value)
            value_width = len(value)
            wmax = autowidth_columns[column]["max"]
            wmin = autowidth_columns[column]["min"]
            max_seen = max(value_width, field.width)
            requested_floor = max(max_seen, wmin)
            wants = min(requested_floor, wmax or requested_floor)
            lgr.debug("value=%r, value width=%d, old field length=%d, "
                      "min width=%s, max width=%s => wants=%d",
                      value, value_width, field.width, wmin, wmax, wants)
            autowidth_columns[column]["wants"] = wants

        # Considering those wants and the available width, assign widths to
        # each column.
        assigned = self._assign_widths(autowidth_columns, width_auto)

        # Set the assigned widths.
        adjusted = False
        for column, width_assigned in assigned.items():
            field = fields[column]
            width_current = field.width
            if width_assigned != width_current:
                adjusted = True
                field.width = width_assigned
                lgr.debug("Adjusting width of %r column from %d to %d ",
                          column, width_current, field.width)
                self._truncaters[column].length = field.width
        return adjusted

    @staticmethod
    def _assign_widths(columns, available):
        """Assign widths to auto-width columns.

        Parameters
        ----------
        columns : dict
            A dictionary where each key is an auto-width column.  The value
            should be a dictionary with the following information:
              - wants: how much width the column wants
              - min: the minimum that the width should set to, provided there
                is enough room
             - weight: if present, a "weight" key indicates the number of
               available characters the column should claim at a time.  This is
               only in effect after each column has claimed one, and the
               specific column has claimed its minimum.
        available : int or float('inf')
            Width available to be assigned.

        Returns
        -------
        Dictionary mapping each auto-width column to the assigned width.
        """
        # NOTE: The method below is not very clever and does unnecessary
        # iteration.  It may end up being too slow, but at least it should
        # serve to establish the baseline (along with tests) that show the
        # desired behavior.

        assigned = {}

        # Make sure every column gets at least one.
        for column in columns:
            col_wants = columns[column]["wants"]
            if col_wants > 0:
                available -= 1
                assigned[column] = 1
        assert available >= 0, "bug: upstream checks should make impossible"

        weights = {c: columns[c].get("weight", 1) for c in columns}
        # ATTN: The sorting here needs to be stable across calls with the same
        # row so that the same assignments come out.
        colnames = sorted(assigned.keys(), reverse=True,
                          key=lambda c: (columns[c]["min"], weights[c], c))
        columns_in_need = set(assigned.keys())
        while available > 0 and columns_in_need:
            for column in colnames:
                if column not in columns_in_need:
                    continue

                col_wants = columns[column]["wants"] - assigned[column]
                if col_wants < 1:
                    columns_in_need.remove(column)
                    continue

                wmin = columns[column]["min"]
                has = assigned[column]
                claim = min(weights[column] if has >= wmin else wmin - has,
                            col_wants,
                            available)
                available -= claim
                assigned[column] += claim
                lgr.log(9, "Claiming %d characters (of %d available) for %s",
                        claim, available, column)
                if available == 0:
                    break
        lgr.debug("Available width after assigned: %s", available)
        lgr.debug("Assigned widths: %r", assigned)
        return assigned

    def _proc_group(self, style, adopt=True):
        """Return whether group is "default" or "override".

        In the case of "override", the self.fields pre-format and post-format
        processors will be set under the "override" key.

        Parameters
        ----------
        style : dict
            A style that follows the schema defined in pyout.elements.
        adopt : bool, optional
            Merge `self.style` and `style`, giving priority to the latter's
            keys when there are conflicts.  If False, treat `style` as a
            standalone style.
        """
        fields = self.fields
        if style is not None:
            if adopt:
                style = elements.adopt(self.style, style)
            elements.validate(style)

            for column in self.columns:
                fields[column].add(
                    "pre", "override",
                    *(self.procgen.pre_from_style(style[column])))
                fields[column].add(
                    "post", "override",
                    *(self.procgen.post_from_style(style[column])))
            return "override"
        else:
            return "default"

    def _check_for_unknown_columns(self, row):
        known = self._known_columns
        # The sorted() call here isn't necessary, but it makes testing the
        # expected output easier without relying on the order-preserving
        # implementation detail of the new dict implementation introduced in
        # Python 3.6.
        cols_new = sorted(c for c in row if c not in known)
        if cols_new:
            raise UnknownColumns(cols_new)

    def render(self, row, style=None, adopt=True, can_unhide=True):
        """Render fields with values from `row`.

        Parameters
        ----------
        row : dict
            A normalized row.
        style : dict, optional
            A style that follows the schema defined in pyout.elements.  If
            None, `self.style` is used.
        adopt : bool, optional
            Merge `self.style` and `style`, using the latter's keys
            when there are conflicts.  If False, treat `style` as a
            standalone style.
        can_unhide : bool, optional
            Whether a non-missing value within `row` is able to unhide a column
            that is marked with "if_missing".

        Returns
        -------
        A tuple with the rendered value (str) and a flag that indicates whether
        the field widths required adjustment (bool).
        """
        self._check_for_unknown_columns(row)

        hidden = self.hidden
        any_unhidden = False
        if can_unhide:
            for c in row:
                val = row[c]
                if hidden[c] == "if_missing" and not isinstance(val, Nothing):
                    lgr.debug("Unhiding column %r after encountering %r",
                              c, val)
                    hidden[c] = False
                    any_unhidden = True
        if any_unhidden:
            self._reset_width_info()

        group = self._proc_group(style, adopt=adopt)
        if group == "override":
            # Override the "default" processor key.
            proc_keys = ["width", "override"]
        else:
            # Use the set of processors defined by _setup_fields.
            proc_keys = None

        adjusted = self._set_widths(row, group)
        cols = self.visible_columns
        proc_fields = ((self.fields[c], row[c]) for c in cols)
        # Exclude fields that weren't able to claim any width to avoid
        # surrounding empty values with separators.
        proc_fields = filter(lambda x: x[0].width > 0, proc_fields)
        proc_fields = (fld(val, keys=proc_keys) for fld, val in proc_fields)
        return self.style["separator_"].join(proc_fields) + "\n", adjusted


class RedoContent(Exception):
    """The rendered content is stale and should be re-rendered.
    """
    pass


class ContentError(Exception):
    """An error occurred when generating the content representation.
    """
    pass


ContentRow = namedtuple("ContentRow", ["row", "kwds"])


class Content(object):
    """Concatenation of rendered fields.

    Parameters
    ----------
    fields : StyleField instance
    """

    def __init__(self, fields):
        self.fields = fields
        self.summary = None

        self.columns = None
        self.ids = None

        self._header = None
        self._rows = []
        self._idkey_to_idx = {}
        self._idx_to_idkey = {}

    def init_columns(self, columns, ids, table_width=None):
        """Set up the fields for `columns`.

        Parameters
        ----------
        columns : sequence or OrderedDict
            Names of the column.  In the case of an OrderedDict, a map between
            short and long names.
        ids : sequence
            A collection of column names that uniquely identify a column.
        table_width : int, optional
            Update the table width to this value.
        """
        self.fields.build(columns, table_width=table_width)
        self.columns = columns
        self.ids = ids

        if self._rows:
            # There are pre-existing rows, so this init_columns() call was due
            # to encountering unknown columns.  Fill in the previous rows.
            style = self.fields.style
            for row in self._rows:
                for col in columns:
                    if col not in row.row:
                        cstyle = style[col]
                        if "missing" in cstyle:
                            missing = Nothing(cstyle["missing"])
                        else:
                            missing = NOTHING
                        row.row[col] = missing
            if self.fields.has_header:
                self._add_header()

    def __len__(self):
        return len(list(self.rows))

    def __bool__(self):
        return bool(self._rows)

    def __getitem__(self, key):
        idx = self._idkey_to_idx[key]
        return self._rows[idx].row

    @property
    def rows(self):
        """Data and summary rows.
        """
        if self._header:
            yield self._header
        for i in self._rows:
            yield i

    def _render(self, rows):
        adjusted = []
        for row, kwds in rows:
            line, adj = self.fields.render(row, **kwds)
            yield line
            # Continue processing so that we get all the adjustments out of
            # the way.
            adjusted.append(adj)
        if any(adjusted):
            raise RedoContent

    def __str__(self):
        for redo in range(3):
            try:
                return "".join(self._render(self.rows))
            except RedoContent:
                # FIXME: Only one additional _render() call is supposed to
                # be necessary, but as f34696a7 (Detect changes in the
                # terminal width, 2020-08-17), it's not sufficient in some
                # cases (see gh-114).  Until that is figured out, allow one
                # more (i.e., three in total), which appears to get rid of
                # the issue.
                if redo:
                    if redo == 1:
                        lgr.debug("One redo was not enough. Trying again")
                    else:
                        raise

    def get_idkey(self, idx):
        """Return ID keys for a row.

        Parameters
        ----------
        idx : int
            Index of row (determined by order it came in to `update`).

        Returns
        -------
        ID key (tuple) matching row.  If there is a header, None is return as
        its ID key.

        Raises
        ------
        IndexError if `idx` does not match known row.
        """
        if self._header:
            idx -= 1
            if idx == -1:
                return None
        try:
            return self._idx_to_idkey[idx]
        except KeyError:
            msg = ("Index {!r} outside of current range: [0, {})"
                   .format(idx, len(self._idkey_to_idx)))
            raise IndexError(msg) from None

    def update(self, row, style):
        """Modify the content.

        Parameters
        ----------
        row : dict
            A normalized row.  If the names specified by `self.ids` have
            already been seen in a previous call, the entry for the previous
            row is updated.  Otherwise, a new entry is appended.

        style :
            Passed to `StyleFields.render`.

        Returns
        -------
        A tuple of (content, status), where status is 'append', an integer, or
        'repaint'.

          * append: the only change in the content is the addition of a line,
            and the returned content will consist of just this line.

          * an integer, N: the Nth line of the output needs to be updated, and
            the returned content will consist of just this line.

          * repaint: all lines need to be updated, and the returned content
            will consist of all the lines.
        """
        called_before = bool(self)
        idkey = tuple(row[idx] for idx in self.ids)

        if not called_before and self.fields.has_header:
            lgr.debug("Registering header")
            self._add_header()
            self._rows.append(ContentRow(row, kwds={"style": style}))
            self._idkey_to_idx[idkey] = 0
            self._idx_to_idkey[0] = idkey
            return str(self), "append"

        try:
            prev_idx = self._idkey_to_idx[idkey]
        except KeyError:
            prev_idx = None
        except TypeError:
            raise ContentError("ID columns must be hashable")

        if prev_idx is not None:
            lgr.debug("Updating content for row %r", idkey)
            row_update = {k: v for k, v in row.items()
                          if not isinstance(v, Nothing)}
            self._rows[prev_idx].row.update(row_update)
            self._rows[prev_idx].kwds.update({"style": style})
            # Replace the passed-in row since it may not have all the columns.
            row = self._rows[prev_idx][0]
        else:
            lgr.debug("Adding row %r to content for first time", idkey)
            nrows = len(self._rows)
            self._idkey_to_idx[idkey] = nrows
            self._idx_to_idkey[nrows] = idkey
            self._rows.append(ContentRow(row, kwds={"style": style}))

        line, adjusted = self.fields.render(row, style)
        lgr.log(9, "Rendered line as %r", line)
        if called_before and adjusted:
            return str(self), "repaint"
        if not adjusted and prev_idx is not None:
            return line, prev_idx + self.fields.has_header
        return line, "append"

    def _add_header(self):
        if isinstance(self.columns, OrderedDict):
            row = self.columns
        else:
            row = dict(zip(self.columns, self.columns))
        self._header = ContentRow(row,
                                  kwds={"style": self.fields.style["header_"],
                                        "can_unhide": False,
                                        "adopt": False})


class ContentWithSummary(Content):
    """Like Content, but append a summary to the return value of `update`.
    """

    def __init__(self, fields):
        super(ContentWithSummary, self).__init__(fields)
        self.summary = None

    def init_columns(self, columns, ids, table_width=None):
        super(ContentWithSummary, self).init_columns(
            columns, ids, table_width=table_width)
        self.summary = Summary(self.fields.style)

    def update(self, row, style):
        lgr.log(9, "Updating with .summary set to %s", self.summary)
        content, status = super(ContentWithSummary, self).update(row, style)
        if self.summary:
            summ_rows = self.summary.summarize(
                self.fields.visible_columns,
                [r.row for r in self._rows])

            def join():
                return "".join(self._render(summ_rows))

            try:
                summ_content = join()
            except RedoContent:
                # If rendering the summary lines triggered an adjustment, we
                # need to re-render the main content as well.
                return str(self), "repaint", join()
            return content, status, summ_content
        return content, status, None

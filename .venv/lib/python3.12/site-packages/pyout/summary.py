"""Summarize output.
"""

from collections.abc import Mapping
from logging import getLogger

from pyout.field import Nothing

lgr = getLogger(__name__)


class Summary(object):
    """Produce summary rows for a list of normalized rows.

    Parameters
    ----------
    style : dict
        A style that follows the schema defined in pyout.elements.
    """

    def __init__(self, style):
        self.style = style
        self._enabled = any("aggregate" in v for v in self.style.values()
                            if isinstance(v, Mapping))

    def __bool__(self):
        return self._enabled

    def summarize(self, columns, rows):
        """Return summary rows.

        Parameters
        ----------
        columns : list of str
            Summarize values within these columns.
        rows : list of dicts
            Normalized rows that contain keys for `columns`.

        Returns
        -------
        A list of summary rows.  Each row is a tuple where the first item is
        the data and the second is a dict of keyword arguments that can be
        passed to StyleFields.render.
        """
        agg_styles = {c: self.style[c]["aggregate"]
                      for c in columns if "aggregate" in self.style[c]}

        summaries = {}
        for col, agg_fn in agg_styles.items():
            lgr.debug("Summarizing column %r with %r", col, agg_fn)
            colvals = filter(lambda x: not isinstance(x, Nothing),
                             (row[col] for row in rows))
            summaries[col] = agg_fn(list(colvals))

        if not summaries:
            return []

        # The rest is just restructuring the summaries into rows that are
        # compatible with pyout.Content.  Most the complexity below comes from
        # the fact that a summary function is allowed to return either a single
        # item or a list of items.
        maxlen = max(len(v) if isinstance(v, list) else 1
                     for v in summaries.values())
        summary_rows = []
        for rowidx in range(maxlen):
            sumrow = {}
            for column, values in summaries.items():
                if isinstance(values, list):
                    if rowidx >= len(values):
                        continue
                    sumrow[column] = values[rowidx]
                elif rowidx == 0:
                    sumrow[column] = values

            for column in columns:
                if column not in sumrow:
                    sumrow[column] = ""

            summary_rows.append((sumrow,
                                 {"style": self.style.get("aggregate_"),
                                  "adopt": False,
                                  "can_unhide": False}))
        return summary_rows

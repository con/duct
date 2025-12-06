"""Terminal test utilities.
"""

from curses import tigetstr
from curses import tparm
from functools import partial
import re

# Eventually we may want to retire blessings:
# https://github.com/pyout/pyout/issues/136
try:
    import blessed as bls
except ImportError:
    import blessings as bls

from pyout.tests.utils import assert_contains


class Terminal(bls.Terminal):

    def __init__(self, *args, **kwargs):
        super(Terminal, self).__init__(
            *args, kind="xterm-256color", **kwargs)
        self._width = 100
        self._height = 20

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value


# unicode_cap, and unicode_parm are copied from blessings' tests.


def unicode_cap(cap):
    """Return the result of ``tigetstr`` except as Unicode."""
    return tigetstr(cap).decode('latin1')


def unicode_parm(cap, *params):
    """Return the result of ``tparm(tigetstr())`` except as Unicode."""
    return tparm(tigetstr(cap), *params).decode('latin1')


COLORNUMS = {"black": 0, "red": 1, "green": 2, "yellow": 3, "blue": 4,
             "magenta": 5, "cyan": 6, "white": 7}


def capres(name, value):
    """Format value with CAP key, followed by a reset.
    """
    if name in COLORNUMS:
        prefix = unicode_parm("setaf", COLORNUMS[name])
    else:
        prefix = unicode_cap(name)
    return prefix + value + unicode_cap("sgr0")


def eq_repr_noclear(actual, expected):
    """Like `eq_repr`, but strip clear-related codes from `actual`.
    """
    clear_codes = [re.escape(unicode_cap(x)) for x in ["el", "ed", "cuu1"]]
    match = re.match("(?:{}|{}|{})*(.*)".format(*clear_codes), actual)
    assert match, "This should always match"
    return repr(match.group(1)) == repr(expected)


assert_contains_nc = partial(assert_contains, cmp=eq_repr_noclear)

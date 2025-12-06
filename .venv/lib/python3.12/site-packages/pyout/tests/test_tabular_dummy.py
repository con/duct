# -*- coding: utf-8 -*-
from io import StringIO
import pytest

from pyout.tabular_dummy import NoUpdateTerminalStream
from pyout.tabular_dummy import Tabular


def test_stream_update_fail():
    stream = NoUpdateTerminalStream()
    with pytest.raises(NotImplementedError):
        stream.clear_last_lines(3)


def test_stream_update_hardcodes_height_width():
    stream = NoUpdateTerminalStream()
    assert stream.width == 80
    assert stream.height == 24


def test_tabular_basic():
    out = Tabular(["name", "status"],
                  stream=StringIO(),
                  interactive=True,
                  style={"name": {"color": "green",
                                  "width": {"marker": "…", "max": 4},
                                  "transform": lambda x: x.upper()}})
    with out:
        out({"name": "foo", "status": "fine"})
        out({"name": "barbecue", "status": "dandy"})

    # The default mode for tabular_dummy.Tabular is "incremental".
    assert out._stream.stream.getvalue() == ("FOO fine\n"
                                             "FOO  fine \n"
                                             "BAR… dandy\n")


def test_tabular_update_mode_disallowed():
    with pytest.raises(ValueError):
        Tabular(["name", "status"], mode="update")

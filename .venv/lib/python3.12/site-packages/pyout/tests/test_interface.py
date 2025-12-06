import pytest

# Eventually we may want to retire blessings:
# https://github.com/pyout/pyout/issues/136
try:
    pytest.importorskip("blessed")
except pytest.skip.Exception:
    pytest.importorskip("blessings")

import inspect

from pyout.interface import Stream
from pyout.interface import Writer
from pyout.tabular import Tabular
from pyout.tabular import TerminalStream
from pyout.tabular_dummy import NoUpdateTerminalStream
from pyout.tabular_dummy import Tabular as DummyTabular


@pytest.mark.parametrize("writer",
                         [Tabular, DummyTabular],
                         ids=["tabular", "dummy"])
def test_writer_children_match_signature(writer):
    assert inspect.signature(writer) == inspect.signature(Writer)


@pytest.mark.parametrize("stream",
                         [TerminalStream, NoUpdateTerminalStream],
                         ids=["terminal", "noupdate"])
def test_stream_children_match_signature(stream):
    assert inspect.signature(stream) == inspect.signature(Stream)

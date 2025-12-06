# -*- coding: utf-8 -*-

import pytest

from pyout.truncate import _splice as splice
from pyout.truncate import Truncater


def test_splice_non_positive():
    with pytest.raises(ValueError):
        assert splice("", 0)


def test_splice():
    assert splice("", 10) == ("", "")
    assert splice("abc", 10) == ("a", "bc")
    assert splice("abc", 3) == ("a", "bc")
    assert splice("abcefg", 3) == ("a", "fg")


def test_truncate_mark_true():
    fn = Truncater(7, marker=True).truncate

    assert fn(None, "abc") == "abc"
    assert fn(None, "abcdefg") == "abcdefg"
    assert fn(None, "abcdefgh") == "abcd..."


@pytest.mark.parametrize("where", ["left", "center", "right"])
def test_truncate_mark_string(where):
    fn = Truncater(7, marker="…", where=where).truncate

    assert fn(None, "abc") == "abc"
    assert fn(None, "abcdefg") == "abcdefg"

    expected = {"left": "…cdefgh",
                "center": "abc…fgh",
                "right": "abcdef…"}
    assert fn(None, "abcdefgh") == expected[where]


@pytest.mark.parametrize("where", ["left", "center", "right"])
def test_truncate_mark_even(where):
    # Test out a marker with an even number of characters, mostly to get the
    # "center" style on seven characters to be uneven.
    fn = Truncater(7, marker="..", where=where).truncate
    expected = {"left": "..defgh",
                "center": "ab..fgh",
                "right": "abcde.."}
    assert fn(None, "abcdefgh") == expected[where]


@pytest.mark.parametrize("where", ["left", "center", "right"])
def test_truncate_mark_short(where):
    fn = Truncater(2, marker=True, where=where).truncate
    assert fn(None, "abc") == ".."


@pytest.mark.parametrize("where", ["left", "center", "right"])
def test_truncate_nomark(where):
    fn = Truncater(7, marker=False, where=where).truncate

    assert fn(None, "abc") == "abc"
    assert fn(None, "abcdefg") == "abcdefg"

    expected = {"left": "bcdefgh",
                "center": "abcefgh",
                "right": "abcdefg"}
    assert fn(None, "abcdefgh") == expected[where]


def test_truncate_unknown_where():
    with pytest.raises(ValueError):
        Truncater(7, marker=False, where="dunno")

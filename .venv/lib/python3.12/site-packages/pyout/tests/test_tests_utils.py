import pytest
from pyout.tests.utils import assert_contains


def test_assert_contains_empty():
    with pytest.raises(AssertionError):
        assert_contains([], "aa")


def test_assert_contains_doesnt():
    with pytest.raises(AssertionError):
        assert_contains(["b"], "aa")


def test_assert_contains_count():
    with pytest.raises(AssertionError):
        assert_contains(["aa", "b"], "aa", count=2)
    assert_contains(["aa", "b", "aa"], "aa", count=2)
    assert_contains(["b"], "aa", count=0)


def test_assert_contains_cmp():
    with pytest.raises(AssertionError):
        assert_contains(["aa", "b"], "aa", cmp=lambda x, y: False)
    with pytest.raises(AssertionError):
        assert_contains(["a", "b"], "aa")
    assert_contains(["a", "b"], "aa", cmp=lambda x, y: x[0] == y[0])

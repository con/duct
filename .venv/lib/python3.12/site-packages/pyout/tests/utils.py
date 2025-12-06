from operator import eq


def assert_contains(collection, *items, **kwargs):
    """Check that each item in `items` is in `collection`.

    Parameters
    ----------
    collection : list
    *items : list
        Query items.
    count : int, optional
        The number of times each item should occur in `collection`.
    cmp : callable, optional
        Function to compare equality with.  It will be called with the element
        from `items` as the first argument and the element from `collection` as
        the second.

    Raises
    ------
    AssertionError if any item does not occur `count` times in `collection`.
    """
    count = kwargs.pop("count", 1)
    cmp = kwargs.pop("cmp", eq)
    for item in items:
        if not len([x for x in collection if cmp(x, item)]) == count:
            raise AssertionError("{!r} (x{}) not in {!r}".format(
                item, count, collection))


def assert_eq_repr(a, b):
    """Compare the repr's of `a` and `b` to escape escape codes.
    """
    assert repr(a) == repr(b)

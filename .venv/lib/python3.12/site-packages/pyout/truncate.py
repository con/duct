"""Processor for field value truncation.
"""


def _truncate_right(value, length, marker):
    if len(value) <= length:
        short = value
    elif marker:
        nchars_free = length - len(marker)
        if nchars_free > 0:
            short = value[:nchars_free] + marker
        else:
            short = marker[:length]
    else:
        short = value[:length]
    return short


def _truncate_left(value, length, marker):
    res = _truncate_right(value[::-1], length,
                          marker[::-1] if marker else None)
    return res[::-1]


def _splice(value, n):
    """Splice `value` at its center, retaining a total of `n` characters.

    Parameters
    ----------
    value : str
    n : int
        The total length of the returned ends will not be greater than this
        value.  Characters will be dropped from the center to reach this limit.

    Returns
    -------
    A tuple of str: (head, tail).
    """
    if n <= 0:
        raise ValueError("n must be positive")

    value_len = len(value)
    center = value_len // 2
    left, right = value[:center], value[center:]

    if n >= value_len:
        return left, right

    n_todrop = value_len - n
    right_idx = n_todrop // 2
    left_idx = right_idx + n_todrop % 2
    return left[:-left_idx], right[right_idx:]


def _truncate_center(value, length, marker):
    value_len = len(value)
    if value_len <= length:
        return value

    if marker:
        marker_len = len(marker)
        if marker_len < length:
            left, right = _splice(value, length - marker_len)
            parts = left, marker, right
        else:
            parts = _splice(marker, length)
    else:
        parts = _splice(value, length)
    return "".join(parts)


class Truncater(object):
    """A processor that truncates the result to a given length.

    Note: You probably want to place the `truncate` method at the beginning of
    the processor list so that the truncation is based on the length of the
    original value.

    Parameters
    ----------
    length : int
        Truncate the string to this length.
    marker : str or bool, optional
        Indicate truncation with this string.  If True, indicate truncation by
        replacing the last three characters of a truncated string with '...'.
        If False, no truncation marker is added to a truncated string.
    where : {'left', 'center', 'right'}, optional
        Where to truncate the result.
    """

    def __init__(self, length, marker=True, where="right"):
        self.length = length
        self.marker = "..." if marker is True else marker

        truncate_fns = {"left": _truncate_left,
                        "center": _truncate_center,
                        "right": _truncate_right}
        try:
            self._truncate_fn = truncate_fns[where]
        except KeyError:
            raise ValueError("Unrecognized `where` value: {}".format(where))

    def truncate(self, _, result):
        return self._truncate_fn(result, self.length, self.marker)

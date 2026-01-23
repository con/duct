"""Utility functions for con-duct."""

from typing import Any


def assert_num(*values: Any) -> None:
    for value in values:
        assert isinstance(value, (float, int))

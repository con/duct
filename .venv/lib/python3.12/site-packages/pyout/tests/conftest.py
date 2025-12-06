import pytest
pytest.register_assert_rewrite("pyout.tests.utils")

from pyout.elements import validate


@pytest.fixture(autouse=True)
def cache_clear():
    yield
    validate.cache_clear()

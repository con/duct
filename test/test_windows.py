from __future__ import annotations
import importlib
import sys
from typing import Generator
from unittest import mock
import pytest


@pytest.fixture
def _reload_sampling() -> Generator:
    """Ensure _sampling module is restored after tests that reload it."""
    import con_duct._sampling as mod

    yield
    if hasattr(sys, "tracebacklimit"):
        del sys.tracebacklimit
    importlib.reload(mod)


@mock.patch("platform.system", return_value="Windows")
@pytest.mark.usefixtures("_reload_sampling")
def test_unsupported_system_raises(_mock_system: mock.MagicMock) -> None:
    import con_duct._sampling as mod

    with pytest.raises(
        NotImplementedError, match="does not currently support.*Windows"
    ):
        importlib.reload(mod)

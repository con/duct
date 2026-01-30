from importlib.metadata import version
from .duct_main import execute

__version__ = version("con-duct")


__all__ = [
    "execute",
    "__version__",
]

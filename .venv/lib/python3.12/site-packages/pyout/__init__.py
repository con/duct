"""Terminal styling for tabular data.

Exposes a single entry point, the Tabular class.
"""

import sys

from pyout.elements import schema

if sys.platform == "win32":
    from pyout.tabular_dummy import Tabular
else:
    from pyout.tabular import Tabular

del sys

from . import _version
__version__ = _version.get_versions()['version']

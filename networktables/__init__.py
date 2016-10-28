
# This is imported first to avoid circular dependency problems
try:
    from .version import __version__
except ImportError:
    __version__ = 'master'

from .networktables import NetworkTables

# Deprecated, will be removed in 2018
from .networktable import NetworkTable



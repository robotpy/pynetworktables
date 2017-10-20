
# This is imported first to avoid circular dependency problems
from .version import __version__

from .networktables import NetworkTables

# Deprecated, will be removed in 2018
from .networktable import NetworkTable



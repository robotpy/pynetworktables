
# This is imported first to avoid circular dependency problems
from .version import __version__

#: Alias of NetworkTablesInstance.getDefault()
from .networktables import NetworkTables

from .instance import NetworkTablesInstance

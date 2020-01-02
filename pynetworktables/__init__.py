from ._impl import __version__

from .instance import NetworkTablesInstance

#: Alias of NetworkTablesInstance.getDefault(), the "default" instance
NetworkTables = NetworkTablesInstance.getDefault()

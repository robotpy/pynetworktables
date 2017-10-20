
__all__ = ["NetworkTables"]

from .instance import NetworkTablesInstance

#: This is the default instance of NetworkTables
NetworkTables = NetworkTablesInstance.getDefault()

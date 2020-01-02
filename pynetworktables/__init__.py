from ._impl import __version__

from .entry import NetworkTableEntry
from .instance import NetworkTablesInstance
from .table import NetworkTable

#: Alias of NetworkTablesInstance.getDefault(), the "default" instance
NetworkTables = NetworkTablesInstance.getDefault()

__all__ = (
    "NetworkTablesInstance",
    "NetworkTables",
    "NetworkTable",
    "NetworkTableEntry",
)

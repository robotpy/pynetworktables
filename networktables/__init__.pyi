from _pynetworktables import (
    NetworkTablesInstance as NetworkTablesInstance,
    NetworkTables as NetworkTables,
    NetworkTable as NetworkTable,
    NetworkTableEntry as NetworkTableEntry,
    Value as Value,
    __version__ as __version__,
)

nt_backend: str = ...

__all__ = (
    "NetworkTablesInstance",
    "NetworkTables",
    "NetworkTable",
    "NetworkTableEntry",
    "Value",
)

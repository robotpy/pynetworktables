# prefer pyntcore if installed
try:
    from _pyntcore import (
        NetworkTablesInstance,
        NetworkTables,
        NetworkTable,
        NetworkTableEntry,
        Value,
    )

    nt_backend = "pyntcore"
except ImportError as e:
    from _pynetworktables import (
        NetworkTablesInstance,
        NetworkTables,
        NetworkTable,
        NetworkTableEntry,
        Value,
    )

    nt_backend = "pynetworktables"


__all__ = (
    "NetworkTablesInstance",
    "NetworkTables",
    "NetworkTable",
    "NetworkTableEntry",
    "Value",
)

__all__ = ("NetworkTables", "NetworkTablesInstance")

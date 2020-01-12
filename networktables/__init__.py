# prefer pyntcore if installed
try:
    from _pyntcore import (
        NetworkTablesInstance,
        NetworkTables,
        NetworkTable,
        NetworkTableEntry,
        Value,
        __version__,
    )

    nt_backend = "pyntcore"
except ImportError as e:
    from _pynetworktables import (
        NetworkTablesInstance,
        NetworkTables,
        NetworkTable,
        NetworkTableEntry,
        Value,
        __version__,
    )

    nt_backend = "pynetworktables"


__all__ = (
    "NetworkTablesInstance",
    "NetworkTables",
    "NetworkTable",
    "NetworkTableEntry",
    "Value",
)

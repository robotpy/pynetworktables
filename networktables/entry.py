import warnings

from . import NetworkTableEntry  # noqa

warnings.warn(
    "networktables.entry is deprecated, import networktables.NetworkTableEntry directly",
    DeprecationWarning,
    stacklevel=2,
)

import warnings

from . import NetworkTable  # noqa

warnings.warn(
    "networktables.networktable is deprecated, import networktables.NetworkTable directly",
    DeprecationWarning,
    stacklevel=2,
)


from networktables2 import BooleanArray, NumberArray, StringArray
from .networktable import NetworkTable

try:
    from .version import __version__
except ImportError:
    __version__ = 'master'

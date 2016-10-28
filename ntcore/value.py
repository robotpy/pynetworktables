# validated: 2016-10-21 DS a73166a src/Value.cpp
'''
    Internal storage for ntcore values
    
    Uses namedtuple for efficiency, and because Value objects are supposed
    to be immutable. Will have to measure that and see if there's a performance
    penalty for this in python.
    
    Original ntcore stores the last change time, but it doesn't seem to
    be used anywhere, so we don't store that to make equality comparison
    more efficient.
'''

from collections import namedtuple
from .constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
    NT_RPC,
)

from .support.compat import stringtype

ValueType = namedtuple('Value', ['type', 'value'])


# optimization
_TRUE_VALUE = ValueType(NT_BOOLEAN, True)
_FALSE_VALUE = ValueType(NT_BOOLEAN, False)


class Value(object):
    
    @staticmethod
    def makeBoolean(value):
        if value:
            return _TRUE_VALUE
        else:
            return _FALSE_VALUE
        
    @staticmethod
    def makeDouble(value):
        return ValueType(NT_DOUBLE, float(value))

    @staticmethod
    def makeString(value):
        return ValueType(NT_STRING, str(value))
    
    @staticmethod
    def makeRaw(value):
        return ValueType(NT_RAW, bytes(value))
    
    # TODO: array stuff a good idea?
    
    @staticmethod
    def makeBooleanArray(value):
        return ValueType(NT_BOOLEAN_ARRAY, tuple(bool(v) for v in value))
    
    @staticmethod
    def makeDoubleArray(value):
        return ValueType(NT_DOUBLE_ARRAY, tuple(float(v) for v in value))
    
    @staticmethod
    def makeStringArray(value):
        return ValueType(NT_STRING_ARRAY, tuple(str(v) for v in value))

    @staticmethod
    def makeRpc(value):
        return ValueType(NT_RPC, str(value))

    @staticmethod
    def makeUnknown(value):
        if isinstance(value, bool):
            return Value.makeBoolean(value)
        elif isinstance(value, (int, float)):
            return Value.makeDouble(value)
        elif isinstance(value, stringtype):
            return Value.makeString(value)
        elif isinstance(value, bytes):
            return ValueType(NT_RAW, value)
        
        # TODO: decide how to deal with arrays
        
        elif value is None:
            raise ValueError("Cannot put None into NetworkTable")
        else:
            raise ValueError("Can only put bool/int/str/bytes")


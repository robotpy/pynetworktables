# validated: 2017-09-28 DS 5ab20bb27c97 cpp/Value.cpp include/networktables/NetworkTableValue.h
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

from .support.compat import basestring, unicode

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
        return ValueType(NT_STRING, unicode(value))
    
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
        return ValueType(NT_STRING_ARRAY, tuple(unicode(v) for v in value))

    @staticmethod
    def makeRpc(value):
        return ValueType(NT_RPC, str(value))
    
    @staticmethod
    def getFactory(value):
        if isinstance(value, bool):
            return Value.makeBoolean
        elif isinstance(value, (int, float)):
            return Value.makeDouble
        elif isinstance(value, basestring):
            return Value.makeString
        elif isinstance(value, (bytes, bytearray)):
            return Value.makeRaw
        
        # Do best effort for arrays, but can't catch all cases
        # .. if you run into an error here, use a less generic type
        elif isinstance(value, (list, tuple)):
            if not value:
                raise TypeError("If you use a list here, cannot be empty")
            
            first = value[0]
            if isinstance(first, bool):
                return Value.makeBooleanArray
            elif isinstance(first, (int, float)):
                return Value.makeDoubleArray
            elif isinstance(first, basestring):
                return Value.makeStringArray
            else:
                raise ValueError("Can only use lists of bool/int/float/strings")
        
        elif value is None:
            raise ValueError("Cannot put None into NetworkTable")
        else:
            raise ValueError("Can only put bool/int/float/str/bytes or lists/tuples of them")
        
    @classmethod
    def getFactoryByType(cls, type_id):
        return _make_map[type_id]

_make_map = {
    NT_BOOLEAN: Value.makeBoolean,
    NT_DOUBLE: Value.makeDouble,
    NT_STRING: Value.makeString,
    NT_RAW: Value.makeRaw,
    NT_BOOLEAN_ARRAY: Value.makeBooleanArray,
    NT_DOUBLE_ARRAY: Value.makeDoubleArray,
    NT_STRING_ARRAY: Value.makeStringArray,
    NT_RPC: Value.makeRpc
}

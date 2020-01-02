# validated: 2018-11-27 DS 175c6c1f0130 cpp/Value.cpp include/networktables/NetworkTableValue.h
"""
    Internal storage for ntcore values

    Uses namedtuple for efficiency, and because Value objects are supposed
    to be immutable. Will have to measure that and see if there's a performance
    penalty for this in python.

    Original ntcore stores the last change time, but it doesn't seem to
    be used anywhere, so we don't store that to make equality comparison
    more efficient.
"""

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


class Value(namedtuple("Value", ["type", "value"])):
    __slots__ = ()

    @classmethod
    def makeBoolean(cls, value):
        if value:
            return cls._TRUE_VALUE
        else:
            return cls._FALSE_VALUE

    @classmethod
    def makeDouble(cls, value):
        return cls(NT_DOUBLE, float(value))

    @classmethod
    def makeString(cls, value):
        return cls(NT_STRING, str(value))

    @classmethod
    def makeRaw(cls, value):
        return cls(NT_RAW, bytes(value))

    # TODO: array stuff a good idea?

    @classmethod
    def makeBooleanArray(cls, value):
        return cls(NT_BOOLEAN_ARRAY, tuple(bool(v) for v in value))

    @classmethod
    def makeDoubleArray(cls, value):
        return cls(NT_DOUBLE_ARRAY, tuple(float(v) for v in value))

    @classmethod
    def makeStringArray(cls, value):
        return cls(NT_STRING_ARRAY, tuple(str(v) for v in value))

    @classmethod
    def makeRpc(cls, value):
        return cls(NT_RPC, str(value))

    @classmethod
    def getFactory(cls, value):
        if isinstance(value, bool):
            return cls.makeBoolean
        elif isinstance(value, (int, float)):
            return cls.makeDouble
        elif isinstance(value, str):
            return cls.makeString
        elif isinstance(value, (bytes, bytearray)):
            return cls.makeRaw

        # Do best effort for arrays, but can't catch all cases
        # .. if you run into an error here, use a less generic type
        elif isinstance(value, (list, tuple)):
            if not value:
                raise TypeError("If you use a list here, cannot be empty")

            first = value[0]
            if isinstance(first, bool):
                return cls.makeBooleanArray
            elif isinstance(first, (int, float)):
                return cls.makeDoubleArray
            elif isinstance(first, str):
                return cls.makeStringArray
            else:
                raise ValueError("Can only use lists of bool/int/float/strings")

        elif value is None:
            raise ValueError("Cannot put None into NetworkTable")
        else:
            raise ValueError(
                "Can only put bool/int/float/str/bytes or lists/tuples of them"
            )

    @classmethod
    def getFactoryByType(cls, type_id):
        return cls._make_map[type_id]


# optimization
Value._TRUE_VALUE = Value(NT_BOOLEAN, True)
Value._FALSE_VALUE = Value(NT_BOOLEAN, False)

Value._make_map = {
    NT_BOOLEAN: Value.makeBoolean,
    NT_DOUBLE: Value.makeDouble,
    NT_STRING: Value.makeString,
    NT_RAW: Value.makeRaw,
    NT_BOOLEAN_ARRAY: Value.makeBooleanArray,
    NT_DOUBLE_ARRAY: Value.makeDoubleArray,
    NT_STRING_ARRAY: Value.makeStringArray,
    NT_RPC: Value.makeRpc,
}

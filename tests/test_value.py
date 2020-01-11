# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

#
# These tests are adapted from ntcore's test suite
#

from _pynetworktables._impl.constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
)
from _pynetworktables._impl.value import Value


def test_Boolean():
    v = Value.makeBoolean(False)
    assert NT_BOOLEAN == v.type
    assert not v.value

    v = Value.makeBoolean(True)
    assert NT_BOOLEAN == v.type
    assert v.value


def test_Double():
    v = Value.makeDouble(0.5)
    assert NT_DOUBLE == v.type
    assert 0.5 == v.value

    v = Value.makeDouble(0.25)
    assert NT_DOUBLE == v.type
    assert 0.25 == v.value


def test_String():
    v = Value.makeString("hello")
    assert NT_STRING == v.type
    assert "hello" == v.value

    v = Value.makeString("goodbye")
    assert NT_STRING == v.type
    assert "goodbye" == v.value


def test_Raw():
    v = Value.makeRaw(b"hello")
    assert NT_RAW == v.type
    assert b"hello" == v.value

    v = Value.makeRaw(b"goodbye")
    assert NT_RAW == v.type
    assert b"goodbye" == v.value


def test_BooleanArray():
    v = Value.makeBooleanArray([True, False, True])
    assert NT_BOOLEAN_ARRAY == v.type
    assert (True, False, True) == v.value


def test_DoubleArray():
    v = Value.makeDoubleArray([0.5, 0.25, 0.5])
    assert NT_DOUBLE_ARRAY == v.type
    assert (0.5, 0.25, 0.5) == v.value


def test_StringArray():
    v = Value.makeStringArray(["hello", "goodbye", "string"])
    assert NT_STRING_ARRAY == v.type
    assert ("hello", "goodbye", "string") == v.value


def test_MixedComparison():

    v2 = Value.makeBoolean(True)
    v3 = Value.makeDouble(0.5)
    assert v2 != v3  # boolean vs double


def test_BooleanComparison():
    v1 = Value.makeBoolean(True)
    v2 = Value.makeBoolean(True)
    assert v1 == v2
    v2 = Value.makeBoolean(False)
    assert v1 != v2


def test_DoubleComparison():
    v1 = Value.makeDouble(0.25)
    v2 = Value.makeDouble(0.25)
    assert v1 == v2
    v2 = Value.makeDouble(0.5)
    assert v1 != v2


def test_StringComparison():
    v1 = Value.makeString("hello")
    v2 = Value.makeString("hello")
    assert v1 == v2
    v2 = Value.makeString("world")
    # different contents
    assert v1 != v2
    v2 = Value.makeString("goodbye")
    # different size
    assert v1 != v2


def test_BooleanArrayComparison():
    v1 = Value.makeBooleanArray([1, 0, 1])
    v2 = Value.makeBooleanArray((1, 0, 1))
    assert v1 == v2

    # different contents
    v2 = Value.makeBooleanArray([1, 1, 1])
    assert v1 != v2

    # different size
    v2 = Value.makeBooleanArray([True, False])
    assert v1 != v2


def test_DoubleArrayComparison():
    v1 = Value.makeDoubleArray([0.5, 0.25, 0.5])
    v2 = Value.makeDoubleArray((0.5, 0.25, 0.5))
    assert v1 == v2

    # different contents
    v2 = Value.makeDoubleArray([0.5, 0.5, 0.5])
    assert v1 != v2

    # different size
    v2 = Value.makeDoubleArray([0.5, 0.25])
    assert v1 != v2


def test_StringArrayComparison():
    v1 = Value.makeStringArray(["hello", "goodbye", "string"])
    v2 = Value.makeStringArray(("hello", "goodbye", "string"))
    assert v1 == v2

    # different contents
    v2 = Value.makeStringArray(["hello", "goodby2", "string"])
    assert v1 != v2

    # different sized contents
    v2 = Value.makeStringArray(["hello", "goodbye2", "string"])
    assert v1 != v2

    # different size
    v2 = Value.makeStringArray(["hello", "goodbye"])
    assert v1 != v2


#
# Additional Python tests
#


def test_unicode():
    # copyright symbol
    v1 = Value.makeString(u"\xA9")
    assert v1.value == u"\xA9"


def test_bytearray():
    v1 = Value.makeRaw(bytearray(b"\x01\x02\x00"))
    assert v1.type == NT_RAW
    assert v1.value == bytearray(b"\x01\x02\x00")
    assert v1.value == b"\x01\x02\x00"

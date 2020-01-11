from __future__ import print_function
from io import BytesIO

import pytest

from _pynetworktables._impl.support.leb128 import (
    size_uleb128,
    encode_uleb128,
    read_uleb128,
)


def test_size():

    # Testing Plan:
    # (1) 128 ^ n ............ need (n+1) bytes
    # (2) 128 ^ n * 64 ....... need (n+1) bytes
    # (3) 128 ^ (n+1) - 1 .... need (n+1) bytes

    assert 1 == size_uleb128(0)  # special case

    assert 1 == size_uleb128(0x1)
    assert 1 == size_uleb128(0x40)
    assert 1 == size_uleb128(0x7F)

    assert 2 == size_uleb128(0x80)
    assert 2 == size_uleb128(0x2000)
    assert 2 == size_uleb128(0x3FFF)

    assert 3 == size_uleb128(0x4000)
    assert 3 == size_uleb128(0x100000)
    assert 3 == size_uleb128(0x1FFFFF)

    assert 4 == size_uleb128(0x200000)
    assert 4 == size_uleb128(0x8000000)
    assert 4 == size_uleb128(0xFFFFFFF)

    assert 5 == size_uleb128(0x10000000)
    assert 5 == size_uleb128(0x40000000)
    assert 5 == size_uleb128(0x7FFFFFFF)


def test_wikipedia_example():

    i = 624485
    result_bytes = bytes(bytearray([0xE5, 0x8E, 0x26]))

    bio = BytesIO(encode_uleb128(i))
    print(result_bytes)
    assert bio.read() == result_bytes
    bio.seek(0)

    result_i = read_uleb128(bio)

    assert result_i == i


@pytest.mark.parametrize(
    "i", [0, 1, 16, 42, 65, 0xFF, 0xFFF, 0xFFFFFFFF, 0x123456789, 100000000000000000000]
)
def test_roundtrip(i):

    bio = BytesIO(encode_uleb128(i))
    print(bio.read())
    bio.seek(0)

    r = read_uleb128(bio)

    print(r)

    assert r == i


from __future__ import print_function
from io import BytesIO

import pytest
from networktables2.leb128 import encode_uleb128, read_uleb128


def test_wikipedia_example():
    
    i = 624485
    result_bytes = bytes(bytearray([0xE5, 0x8E, 0x26]))
    
    bio = BytesIO(encode_uleb128(i))
    print(result_bytes)
    assert bio.read() == result_bytes
    bio.seek(0)
    
    result_i = read_uleb128(bio)
    
    assert result_i == i


@pytest.mark.parametrize('i', [ 
    0, 1, 16, 42, 65,
    0xff, 0xfff,
    0xffffffff,
    0x123456789, 
    100000000000000000000
])
def test_roundtrip(i):
    
    bio = BytesIO(encode_uleb128(i))
    print(bio.read())
    bio.seek(0)
    
    r = read_uleb128(bio)
    
    print(r)
    
    assert r == i
    
    
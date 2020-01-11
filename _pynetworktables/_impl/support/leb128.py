# novalidate
"""
    Operations related to LEB128 encoding/decoding

    The algorithm is taken from Appendix C of the DWARF 3 spec. For information
    on the encodings refer to section "7.6 - Variable Length Data"

"""

import sys


def size_uleb128(value):
    count = 0
    while True:
        value >>= 7
        count += 1
        if value == 0:
            break
    return count


def encode_uleb128(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte = byte | 0x80
        out.append(byte)
        if value == 0:
            break
    return out


def read_uleb128(rstream):
    result = 0
    shift = 0
    while True:
        b = rstream.read(1)[0]
        result |= (b & 0x7F) << shift
        shift += 7
        if (b & 0x80) == 0:
            break
    return result

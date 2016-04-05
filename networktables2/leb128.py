
import sys

def encode_uleb128(value):
    out = []
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte = byte | 0x80
        out.append(byte)
        if value == 0:
            break
    return bytes(bytearray(out))

# You can do bitwise operations on bytes, not so with strings (py2)
if sys.version_info[0] == 2:
    
    def read_uleb128(rstream):
        result = 0
        shift = 0
        while True:
            x = rstream.read(1)
            b = ord(x)
            result |= (b & 0x7f) << shift
            shift += 7
            if (b & 0x80) == 0:
                break
        return result
    
else:
    
    def read_uleb128(rstream):
        result = 0
        shift = 0
        while True:
            b = rstream.read(1)[0]
            result |= (b & 0x7f) << shift
            shift += 7
            if (b & 0x80) == 0:
                break
        return result


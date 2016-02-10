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
    return bytes(out)

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


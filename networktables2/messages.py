
import struct

__all__ = ["BadMessageError", "PROTOCOL_REVISION",
           "KEEP_ALIVE", "CLIENT_HELLO", "PROTOCOL_UNSUPPORTED",
           "SERVER_HELLO_COMPLETE", "ENTRY_ASSIGNMENT", "FIELD_UPDATE"]

# The definitions of all of the protocol message types

class BadMessageError(IOError):
    pass

PROTOCOL_REVISION = 0x0200

class Message:
    def __init__(self, HEADER, STRUCT=None):
        self.HEADER = HEADER
        if STRUCT is None:
            self.STRUCT = None
        else:
            self.STRUCT = struct.Struct(STRUCT)

    def getBytes(self, *args):
        b = bytearray(self.HEADER)
        if self.STRUCT is not None:
            b.extend(self.STRUCT.pack(*args))
        return b
    
    def read(self, rstream):
        return rstream.readStruct(self.STRUCT)

class NamedMessage(Message):
    NAME_LEN_STRUCT = struct.Struct('>H')

    def __init__(self, HEADER, STRUCT=None):
        Message.__init__(self, HEADER, STRUCT)
        
    def getBytes(self, name, *args):
        b = bytearray(self.HEADER)
        name = name.encode('utf-8')
        b.extend(self.NAME_LEN_STRUCT.pack(len(name)))
        b.extend(name)
        if self.STRUCT is not None:
            b.extend(self.STRUCT.pack(*args))
        return b

    def read(self, rstream):
        nameLen = rstream.readStruct(self.NAME_LEN_STRUCT)[0]
        try:
            name = rstream.read(nameLen).decode('utf-8')
        except UnicodeDecodeError as e:
            raise BadMessageError(e)
        return name, rstream.readStruct(self.STRUCT)

# A keep alive message that the client sends
KEEP_ALIVE = Message(b'\x00')
# A client hello message that a client sends
CLIENT_HELLO = Message(b'\x01', '>H')
# A protocol version unsupported message that the server sends to a client
PROTOCOL_UNSUPPORTED = Message(b'\x02', '>H')
# A server hello complete message that a server sends
SERVER_HELLO_COMPLETE = Message(b'\x03')
# An entry assignment message
ENTRY_ASSIGNMENT = NamedMessage(b'\x10', '>bHH')
# A field update message
FIELD_UPDATE = Message(b'\x11', '>HH')


import struct
from . import leb128

__all__ = ["BadMessageError", "PROTOCOL_REVISION",
           "KEEP_ALIVE", "CLIENT_HELLO", "PROTOCOL_UNSUPPORTED",
           "SERVER_HELLO_COMPLETE", "ENTRY_ASSIGNMENT", "FIELD_UPDATE",
           "SERVER_HELLO", "CLIENT_HELLO_COMPLETE", "FLAGS_UPDATE",
           "ENTRY_DELETE", "CLEAR_ENTRIES", "EXECUTE_RPC", "RPC_RESPONSE"]

# The definitions of all of the protocol message types

class BadMessageError(IOError):
    pass

PROTOCOL_REVISION = 0x0300

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
    def __init__(self, HEADER, STRUCT=None):
        Message.__init__(self, HEADER, STRUCT)
        
    def getBytes(self, name, *args):
        b = bytearray(self.HEADER)
        name = name.encode('utf-8')
        b.extend(leb128.encode_uleb128(len(name)))
        b.extend(name)
        if self.STRUCT is not None:
            b.extend(self.STRUCT.pack(*args))
        return b

    def read(self, rstream):
        nameLen = leb128.read_uleb128(rstream)
        try:
            name = rstream.read(nameLen).decode('utf-8')
        except UnicodeDecodeError as e:
            raise BadMessageError(e)
        return name, rstream.readStruct(self.STRUCT)

class NamedMessageEnd(Message):
    def __init__(self, HEADER, STRUCT=None):
        Message.__init__(self, HEADER, STRUCT)
        
    def getBytes(self, name, *args):
        b = bytearray(self.HEADER)
        if self.STRUCT is not None:
            b.extend(self.STRUCT.pack(*args))
        name = name.encode('utf-8')
        b.extend(leb128.encode_uleb128(len(name)))
        b.extend(name)
        return b

    def read(self, rstream):
        s = rstream.readStruct(self.STRUCT)
        nameLen = leb128.read_uleb128(rstream)
        try:
            name = rstream.read(nameLen).decode('utf-8')
        except UnicodeDecodeError as e:
            raise BadMessageError(e)
        return name, s

# A keep alive message that the client sends
KEEP_ALIVE = Message(b'\x00')
# A client hello message that a client sends
CLIENT_HELLO = NamedMessageEnd(b'\x01', '>H')
# A protocol version unsupported message that the server sends to a client
PROTOCOL_UNSUPPORTED = Message(b'\x02', '>H')
# A server hello complete message that a server sends
SERVER_HELLO_COMPLETE = Message(b'\x03')
SERVER_HELLO = NamedMessageEnd(b'\x04', 'b')
CLIENT_HELLO_COMPLETE = Message(b'\x05')
# An entry assignment message
ENTRY_ASSIGNMENT = NamedMessage(b'\x10', '>bHHb')
# A field update message
FIELD_UPDATE = Message(b'\x11', '>HHb')
FLAGS_UPDATE = Message(b'\x12', '>Hb')
ENTRY_DELETE = Message(b'\x13', '>H')
CLEAR_ENTRIES = Message(b'\x14', '>I')
EXECUTE_RPC = NamedMessageEnd(b'\x20', '>HH')
RPC_RESPONSE = NamedMessageEnd(b'\x21', '>HH')

# validated: 2016-10-27 DS c2ae897 src/WireDecoder.cpp src/WireDecoder.h src/WireEncoder.cpp src/WireEncoder.h
'''
    This encompasses the WireEncoder and WireDecoder stuff in ntcore
    
    Reading:
    
    Writing:
    
        Each message type will have a write function, which takes
        a single list argument. Bytes will be added to that list.
    
        The write routines assume that the messages are a tuple
        that have the following format:
        
            # This doesn't make sense
            type, str, value, id, flags, seqnum
    
'''

import struct
from .support.compat import range

from .constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
    NT_RPC
)

from .support import leb128
from .value import Value


_clientHello = struct.Struct('>H')
_protoUnsup = struct.Struct('>H')
_entryAssignV2 = struct.Struct('>HH')
_entryUpdate = struct.Struct('>HH')

_serverHello = struct.Struct('b')
_entryAssignV3 = struct.Struct('>HHb')
_flagsUpdate = struct.Struct('>Hb')
_entryDelete = struct.Struct('>H')
_clearEntries = struct.Struct('>I')
_executeRpc = struct.Struct('>HH')
_rpcResponse = struct.Struct('>HH')


class WireCodec(object):
    
    _bool_fmt = struct.Struct('?')
    _double_fmt = struct.Struct('>d')
    _string_fmt = struct.Struct('>H')
    _array_fmt = struct.Struct('b')
    _short_fmt = struct.Struct('>H')
        
    clientHello = _clientHello
    protoUnsup = _protoUnsup
    entryUpdate = _entryUpdate
        
    def __init__(self, proto_rev):
        self.set_proto_rev(proto_rev)
        
    def set_proto_rev(self, proto_rev):
        self.proto_rev = proto_rev
        if proto_rev == 0x0200:
            self.read_arraylen = self.read_arraylen_v2
            self.read_string = self.read_string_v2
            self.write_arraylen = self.write_arraylen_v2
            self.write_string = self.write_string_v2
            
            self.entryAssign = _entryAssignV2
            
            self._del('serverHello')
            self._del('flagsUpdate')
            self._del('entryDelete')
            self._del('clearEntries')
            self._del('executeRpc')
            self._del('rpcResponse')
            
        elif proto_rev == 0x0300:
            self.read_arraylen = self.read_arraylen_v3
            self.read_string = self.read_string_v3
            self.write_arraylen = self.write_arraylen_v3
            self.write_string = self.write_string_v3
            
            self.entryAssign = _entryAssignV3
            
            self.serverHello = _serverHello
            self.flagsUpdate = _flagsUpdate
            self.entryDelete = _entryDelete
            self.clearEntries = _clearEntries
            self.executeRpc = _executeRpc
            self.rpcResponse = _rpcResponse
        
        else:
            raise ValueError("Unsupported protocol")
    
    def _del(self, attr):
        if hasattr(self, attr):
            delattr(self, attr)
    
    def read_value(self, vtype, rstream):
        if vtype == NT_BOOLEAN:
            return Value.makeBoolean(rstream.readStruct(self._bool_fmt)[0])
        
        elif vtype == NT_DOUBLE:
            return Value.makeDouble(rstream.readStruct(self._double_fmt)[0])
        
        elif vtype == NT_STRING:
            return Value.makeString(self.read_string(rstream))
        
        elif vtype == NT_BOOLEAN_ARRAY:
            alen = self.read_arraylen(rstream)
            return Value.makeBooleanArray([rstream.readStruct(self._bool_fmt)[0] for _ in range(alen)])
        
        elif vtype == NT_DOUBLE_ARRAY:
            alen = self.read_arraylen(rstream)
            return Value.makeDoubleArray([rstream.readStruct(self._double_fmt)[0] for _ in range(alen)])
        
        elif vtype == NT_STRING_ARRAY:
            alen = self.read_arraylen(rstream)
            return Value.makeStringArray([self.read_string(rstream) for _ in range(alen)])
        
        elif self.proto_rev >= 0x0300:
            if vtype == NT_RAW:
                slen = leb128.read_uleb128(rstream) 
                return Value.makeRaw(rstream.read(slen))
            
            elif vtype == NT_RPC:
                return Value.makeRpc(self.read_string(rstream))
        
        raise ValueError("Cannot decode value type %s" % vtype)
    
    def write_value(self, v, out):
        vtype = v.type
    
        if vtype == NT_BOOLEAN:
            out.append(self._bool_fmt.pack(v.value))
            return
            
        elif vtype == NT_DOUBLE:
            out.append(self._double_fmt.pack(v.value))
            return
            
        elif vtype == NT_STRING:
            self.write_string(v.value, out)
            return
            
        elif vtype == NT_BOOLEAN_ARRAY:
            alen = self.write_arraylen(v.value, out)
            out += (self._bool_fmt.pack(v) for v in v.value[:alen])
            return
            
        elif vtype == NT_DOUBLE_ARRAY:
            alen = self.write_arraylen(v.value, out)
            out += (self._double_fmt.pack(v) for v in v.value[:alen])
            return
            
        elif vtype == NT_STRING_ARRAY:
            alen = self.write_arraylen(v.value, out)
            for s in v.value[:alen]:
                self.write_string(s, out)
            return
                
        elif self.proto_rev >= 0x0300:
            if vtype == NT_RPC:
                self.write_string(v.value, out)
                return
            
            elif vtype == NT_RAW:
                s = v.value
                out += (leb128.encode_uleb128(len(s)), s)
                return
        
        raise ValueError("Cannot encode invalid value type %s" % vtype)
    
    
    #
    # v2/v3 routines
    #
    
    def read_arraylen_v2(self, rstream):
        return rstream.readStruct(self._array_fmt)[0]
    
    def read_arraylen_v3(self, rstream):
        return leb128.read_uleb128(rstream) 
    
    def read_string_v2(self, rstream):
        slen = rstream.readStruct(self._string_fmt)[0]
        return rstream.read(slen).decode('utf-8', 'replace')
    
    def read_string_v3(self, rstream):
        slen = leb128.read_uleb128(rstream)
        return rstream.read(slen).decode('utf-8', 'replace')
    
    
    def write_arraylen_v2(self, a, out):
        alen = min(len(a), 0xff)
        out.append(self._array_fmt.pack(alen))
        return alen
    
    def write_arraylen_v3(self, a, out):
        alen = len(a)
        out.append(leb128.encode_uleb128(alen))
        return alen
    
    def write_string_v2(self, s, out):
        s = s.encode('utf-8')
        out += (self._string_fmt.pack(min(len(s), 0xffff)), s[:0xffff])
    
    def write_string_v3(self, s, out):
        s = s.encode('utf-8')
        out += (leb128.encode_uleb128(len(s)), s)



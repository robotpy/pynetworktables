# validated: 2017-01-07 DS b9a08e826046 src/Message.cpp src/Message.h

from collections import namedtuple

from .constants import (
    kKeepAlive,
    kClientHello,
    kProtoUnsup,
    kServerHello,
    kServerHelloDone,
    kClientHelloDone,
    kEntryAssign,
    kEntryUpdate,
    kFlagsUpdate,
    kEntryDelete,
    kClearEntries,
    kExecuteRpc,
    kRpcResponse,
    
    kClearAllMagic,
    
    NT_VTYPE2RAW,
    NT_RAW2VTYPE,
)

_empty_msgtypes = [kKeepAlive, kServerHelloDone, kClientHelloDone]


MessageType = namedtuple('MessageType', ['type', 'str', 'value',
                                         'id', 'flags', 'seq_num_uid'])

class Message(object):
    
    @staticmethod
    def keepAlive():
        return MessageType(kKeepAlive, None, None, None, None, None)
    
    @staticmethod
    def clientHello(proto_rev, identity):
        return MessageType(kClientHello, identity, None, proto_rev, None, None)
    
    @staticmethod
    def protoUnsup(proto_rev):
        return MessageType(kProtoUnsup, None, None, proto_rev, None, None)
    
    @staticmethod
    def serverHelloDone():
        return MessageType(kServerHelloDone, None, None, None, None, None)
    
    @staticmethod
    def serverHello(flags, identity):
        return MessageType(kServerHello, identity, None, None, flags, None)
    
    @staticmethod
    def clientHelloDone():
        return MessageType(kClientHelloDone, None, None, None, None, None)
    
    @staticmethod
    def entryAssign(name, msg_id, seq_num_uid, value, flags):
        return MessageType(kEntryAssign, name, value, msg_id, flags, seq_num_uid)
    
    @staticmethod
    def entryUpdate(entry_id, seq_num_uid, value):
        return MessageType(kEntryUpdate, None, value, entry_id, None, seq_num_uid)
    
    @staticmethod
    def flagsUpdate(msg_id, flags):
        return MessageType(kFlagsUpdate, None, None, msg_id, flags, None)
    
    @staticmethod
    def entryDelete(entry_id):
        return MessageType(kEntryDelete, None, None, entry_id, None, None)
    
    @staticmethod
    def clearEntries():
        return MessageType(kClearEntries, None, None, kClearAllMagic, None, None)
    
    @staticmethod
    def executeRpc(rpc_id, call_uid, params):
        return MessageType(kExecuteRpc, params, None, rpc_id, None, call_uid)

    @staticmethod
    def rpcResponse(rpc_id, call_uid, result):
        return MessageType(kRpcResponse, result, None, rpc_id, None, call_uid)

    

    @staticmethod
    def read(rstream, codec, get_entry_type):
        msgtype = rstream.read(1)
        
        msg_str = None
        value = None
        msg_id = None
        flags = None
        seq_num_uid = None
        
        # switch type
        if msgtype in _empty_msgtypes:
            pass
        
        elif msgtype == kClientHello:
            msg_id, = rstream.readStruct(codec.clientHello)
            if msg_id >= 0x0300:
                msg_str = codec.read_string_v3(rstream)
        
        elif msgtype == kProtoUnsup:
            msg_id, = rstream.readStruct(codec.protoUnsup)
        
        elif msgtype == kServerHello:
            flags, = rstream.readStruct(codec.serverHello)
            msg_str = codec.read_string(rstream)
           
        elif msgtype == kEntryAssign:
            msg_str = codec.read_string(rstream)
            value_type = NT_RAW2VTYPE.get(rstream.read(1))
            if codec.proto_rev >= 0x0300:
                msg_id, seq_num_uid, flags = rstream.readStruct(codec.entryAssign)
            else:
                msg_id, seq_num_uid = rstream.readStruct(codec.entryAssign)
                flags = 0
                
            value = codec.read_value(value_type, rstream)
        
        elif msgtype == kEntryUpdate:
            if codec.proto_rev >= 0x0300:
                msg_id, seq_num_uid = rstream.readStruct(codec.entryUpdate)
                value_type = NT_RAW2VTYPE.get(rstream.read(1))
            else:
                msg_id, seq_num_uid = rstream.readStruct(codec.entryUpdate)
                value_type = get_entry_type(msg_id)
            
            value = codec.read_value(value_type, rstream)
            
        elif msgtype == kFlagsUpdate:
            msg_id, flags = rstream.readStruct(codec.flagsUpdate)
        
        elif msgtype == kEntryDelete:
            msg_id, = rstream.readStruct(codec.entryDelete)
        
        elif msgtype == kClearEntries:
            msg_id, = rstream.readStruct(codec.clearEntries)
            if msg_id != kClearAllMagic:
                raise ValueError("Bad magic")
        
        elif msgtype == kExecuteRpc:
            msg_id, seq_num_uid = rstream.readStruct(codec.executeRpc)
            msg_str = codec.read_string(rstream)
        
        elif msgtype == kRpcResponse:
            msg_id, seq_num_uid = rstream.readStruct(codec.rpcResponse)
            msg_str = codec.read_string(rstream)
            
        else:
            raise ValueError("Unrecognized message type %s" % msgtype)
        
        return MessageType(msgtype, msg_str, value, msg_id, flags, seq_num_uid)
    
    @staticmethod
    def write(msg, out, codec):
        msgtype = msg.type
        
        # switch type
        if msgtype in _empty_msgtypes:
            out.append(msgtype)
        
        elif msgtype == kClientHello:
            proto_rev = msg.id
            out += (msgtype,
                    codec.clientHello.pack(proto_rev))
            
            if proto_rev >= 0x0300:
                codec.write_string_v3(msg.str, out)
                    
        elif msgtype == kProtoUnsup:
            out += (msgtype,
                    codec.protoUnsup.pack(msg.id))
            
        elif msgtype == kServerHello:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.serverHello.pack(msg.flags))
                codec.write_string(msg.str, out)
            
        elif msgtype == kEntryAssign:
            out.append(msgtype)
            codec.write_string(msg.str, out)
            
            value = msg.value
            if codec.proto_rev >= 0x0300:
                sb = codec.entryAssign.pack(msg.id, msg.seq_num_uid, msg.flags)
            else:
                sb = codec.entryAssign.pack(msg.id, msg.seq_num_uid)
            out += (NT_VTYPE2RAW[value.type], sb)
            
            codec.write_value(value, out)
        
        elif msgtype == kEntryUpdate:
            value = msg.value
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.entryUpdate.pack(msg.id, msg.seq_num_uid),
                        NT_VTYPE2RAW[value.type])
            else:
                out += (msgtype,
                        codec.entryUpdate.pack(msg.id, msg.seq_num_uid))
                
            codec.write_value(value, out)
        
        elif msgtype == kFlagsUpdate:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.flagsUpdate.pack(msg.id, msg.flags))
        
        elif msgtype == kEntryDelete:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.entryDelete.pack(msg.id))
            
        elif msgtype == kClearEntries:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.clearEntries.pack(msg.id))
        
        elif msgtype == kExecuteRpc:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.executeRpc.pack(msg.id, msg.seq_num_uid))
                codec.write_string(msg.str, out)
        
        elif msgtype == kRpcResponse:
            if codec.proto_rev >= 0x0300:
                out += (msgtype,
                        codec.rpcResponse.pack(msg.id, msg.seq_num_uid))
                codec.write_string(msg.str, out)
        
        else:
            raise ValueError("Internal error: bad value type %s" % msg.type)
        
        
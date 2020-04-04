# validated: 2018-01-06 DV 2287281066f6 cpp/Message.cpp cpp/Message.h

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


class Message(
    namedtuple("Message", ["type", "str", "value", "id", "flags", "seq_num_uid"])
):
    __slots__ = ()

    _empty_msgtypes = (kKeepAlive, kServerHelloDone, kClientHelloDone)

    @classmethod
    def keepAlive(cls):
        return cls(kKeepAlive, None, None, None, None, None)

    @classmethod
    def clientHello(cls, proto_rev, identity):
        return cls(kClientHello, identity, None, proto_rev, None, None)

    @classmethod
    def protoUnsup(cls, proto_rev):
        return cls(kProtoUnsup, None, None, proto_rev, None, None)

    @classmethod
    def serverHelloDone(cls):
        return cls(kServerHelloDone, None, None, None, None, None)

    @classmethod
    def serverHello(cls, flags, identity):
        return cls(kServerHello, identity, None, None, flags, None)

    @classmethod
    def clientHelloDone(cls):
        return cls(kClientHelloDone, None, None, None, None, None)

    @classmethod
    def entryAssign(cls, name, msg_id, seq_num_uid, value, flags):
        return cls(kEntryAssign, name, value, msg_id, flags, seq_num_uid)

    @classmethod
    def entryUpdate(cls, entry_id, seq_num_uid, value):
        return cls(kEntryUpdate, None, value, entry_id, None, seq_num_uid)

    @classmethod
    def flagsUpdate(cls, msg_id, flags):
        return cls(kFlagsUpdate, None, None, msg_id, flags, None)

    @classmethod
    def entryDelete(cls, entry_id):
        return cls(kEntryDelete, None, None, entry_id, None, None)

    @classmethod
    def clearEntries(cls):
        return cls(kClearEntries, None, None, kClearAllMagic, None, None)

    @classmethod
    def executeRpc(cls, rpc_id, call_uid, params):
        return cls(kExecuteRpc, params, None, rpc_id, None, call_uid)

    @classmethod
    def rpcResponse(cls, rpc_id, call_uid, result):
        return cls(kRpcResponse, result, None, rpc_id, None, call_uid)

    @classmethod
    def read(cls, rstream, codec, get_entry_type) -> "Message":
        msgtype = rstream.read(1)

        msg_str = None
        value = None
        msg_id = None
        flags = None
        seq_num_uid = None

        # switch type
        if msgtype in cls._empty_msgtypes:
            pass

        # python optimization: entry updates tend to occur more than
        # anything else, so check this first
        elif msgtype == kEntryUpdate:
            if codec.proto_rev >= 0x0300:
                msg_id, seq_num_uid = rstream.readStruct(codec.entryUpdate)
                value_type = NT_RAW2VTYPE.get(rstream.read(1))
            else:
                msg_id, seq_num_uid = rstream.readStruct(codec.entryUpdate)
                value_type = get_entry_type(msg_id)

            value = codec.read_value(value_type, rstream)

        elif msgtype == kClientHello:
            (msg_id,) = rstream.readStruct(codec.clientHello)
            if msg_id >= 0x0300:
                msg_str = codec.read_string_v3(rstream)

        elif msgtype == kProtoUnsup:
            (msg_id,) = rstream.readStruct(codec.protoUnsup)

        elif msgtype == kServerHello:
            (flags,) = rstream.readStruct(codec.serverHello)
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

        elif msgtype == kFlagsUpdate:
            msg_id, flags = rstream.readStruct(codec.flagsUpdate)

        elif msgtype == kEntryDelete:
            (msg_id,) = rstream.readStruct(codec.entryDelete)

        elif msgtype == kClearEntries:
            (msg_id,) = rstream.readStruct(codec.clearEntries)
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

        return cls(msgtype, msg_str, value, msg_id, flags, seq_num_uid)

    def write(self, out, codec):
        msgtype = self.type

        # switch type
        if msgtype in self._empty_msgtypes:
            out.append(msgtype)

        elif msgtype == kClientHello:
            proto_rev = self.id
            out += (msgtype, codec.clientHello.pack(proto_rev))

            if proto_rev >= 0x0300:
                codec.write_string_v3(self.str, out)

        elif msgtype == kProtoUnsup:
            out += (msgtype, codec.protoUnsup.pack(self.id))

        elif msgtype == kServerHello:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.serverHello.pack(self.flags))
                codec.write_string(self.str, out)

        elif msgtype == kEntryAssign:
            out.append(msgtype)
            codec.write_string(self.str, out)

            value = self.value
            if codec.proto_rev >= 0x0300:
                sb = codec.entryAssign.pack(self.id, self.seq_num_uid, self.flags)
            else:
                sb = codec.entryAssign.pack(self.id, self.seq_num_uid)
            out += (NT_VTYPE2RAW[value.type], sb)

            codec.write_value(value, out)

        elif msgtype == kEntryUpdate:
            value = self.value
            if codec.proto_rev >= 0x0300:
                out += (
                    msgtype,
                    codec.entryUpdate.pack(self.id, self.seq_num_uid),
                    NT_VTYPE2RAW[value.type],
                )
            else:
                out += (msgtype, codec.entryUpdate.pack(self.id, self.seq_num_uid))

            codec.write_value(value, out)

        elif msgtype == kFlagsUpdate:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.flagsUpdate.pack(self.id, self.flags))

        elif msgtype == kEntryDelete:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.entryDelete.pack(self.id))

        elif msgtype == kClearEntries:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.clearEntries.pack(self.id))

        elif msgtype == kExecuteRpc:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.executeRpc.pack(self.id, self.seq_num_uid))
                codec.write_string(self.str, out)

        elif msgtype == kRpcResponse:
            if codec.proto_rev >= 0x0300:
                out += (msgtype, codec.rpcResponse.pack(self.id, self.seq_num_uid))
                codec.write_string(self.str, out)

        else:
            raise ValueError("Internal error: bad value type %s" % self.type)

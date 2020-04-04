#
# These tests are adapted from ntcore's test suite
#

from __future__ import print_function

from io import BytesIO

import pytest

from _pynetworktables._impl.message import Message
from _pynetworktables._impl.value import Value
from _pynetworktables._impl.tcpsockets.tcp_stream import TCPStream, StreamEOF
from _pynetworktables._impl.wire import WireCodec


class ReadStream(TCPStream):
    def __init__(self, fp):
        self.m_rdsock = fp


@pytest.fixture(params=[0x0200, 0x0300])
def proto_rev(request):
    return request.param


@pytest.fixture
def v_round_trip(proto_rev):

    codec = WireCodec(proto_rev)

    def _fn(v, minver=0x0200):
        if codec.proto_rev < minver:
            return

        out = []
        fp = BytesIO()
        rstream = ReadStream(fp)

        codec.write_value(v, out)
        fp.write(b"".join(out))
        fp.seek(0)

        vv = codec.read_value(v.type, rstream)

        with pytest.raises(StreamEOF):
            rstream.read(1)

        assert v == vv

    return _fn


# for each value type, test roundtrip


def test_wire_boolean(v_round_trip):
    v_round_trip(Value.makeBoolean(True))


def test_wire_double(v_round_trip):
    v_round_trip(Value.makeDouble(0.5))


def test_wire_string1(v_round_trip):
    v_round_trip(Value.makeString(""))


def test_wire_string2(v_round_trip):
    v_round_trip(Value.makeString("Hi there"))


def test_wire_raw1(v_round_trip):
    v_round_trip(Value.makeRaw(b""), minver=0x0300)


def test_wire_raw2(v_round_trip):
    v_round_trip(Value.makeRaw(b"\x00\xff\x78"), minver=0x0300)


def test_wire_boolArray1(v_round_trip):
    v_round_trip(Value.makeBooleanArray([]))


def test_wire_boolArray2(v_round_trip):
    v_round_trip(Value.makeBooleanArray([True, False]))


def test_wire_boolArray3(v_round_trip):
    v_round_trip(Value.makeBooleanArray([True] * 255))


def test_wire_doubleArray1(v_round_trip):
    v_round_trip(Value.makeDoubleArray([]))


def test_wire_doubleArray2(v_round_trip):
    v_round_trip(Value.makeDoubleArray([0, 1]))


def test_wire_doubleArray3(v_round_trip):
    v_round_trip(Value.makeDoubleArray([0] * 255))


def test_wire_stringArray1(v_round_trip):
    v_round_trip(Value.makeStringArray([]))


def test_wire_stringArray2(v_round_trip):
    v_round_trip(Value.makeStringArray(["hi", "there"]))


def test_wire_stringArray3(v_round_trip):
    v_round_trip(Value.makeStringArray(["hi"] * 255))


def test_wire_rpc1(v_round_trip):
    v_round_trip(Value.makeRpc(""), minver=0x0300)


def test_wire_rpc2(v_round_trip):
    v_round_trip(Value.makeRpc("Hi there"), minver=0x0300)


# Try out the various message types
@pytest.fixture
def msg_round_trip(proto_rev):

    codec = WireCodec(proto_rev)

    def _fn(msg: Message, minver=0x0200, exclude=None):

        out = []
        fp = BytesIO()
        rstream = ReadStream(fp)

        if codec.proto_rev < minver:
            # The codec won't have the correct struct set if
            # the version isn't supported
            msg.write(out, codec)
            assert not out
            return

        msg.write(out, codec)
        fp.write(b"".join(out))
        fp.seek(0)

        mm = Message.read(rstream, codec, lambda x: msg.value.type)

        with pytest.raises(StreamEOF):
            rstream.read(1)

        # In v2, some fields aren't copied over, so we exclude them
        # by overwriting those indices and recreating the read message
        if exclude:
            args = list(mm)
            for e in exclude:
                args[e] = msg[e]
            mm = Message(*args)

        assert msg == mm

    return _fn


def test_wire_keepAlive(msg_round_trip):
    msg_round_trip(Message.keepAlive())


def test_wire_clientHello(msg_round_trip):
    msg_round_trip(Message.clientHello(0x0200, "Hi"), exclude=[1])


def test_wire_clientHelloV3(msg_round_trip):
    msg_round_trip(Message.clientHello(0x0300, "Hi"))


def test_wire_protoUnsup(msg_round_trip):
    msg_round_trip(Message.protoUnsup(0x0300))


def test_wire_serverHelloDone(msg_round_trip):
    msg_round_trip(Message.serverHelloDone())


def test_wire_serverHello(msg_round_trip):
    msg_round_trip(Message.serverHello(0x01, "Hi"), minver=0x0300)


def test_wire_clientHelloDone(msg_round_trip):
    msg_round_trip(Message.clientHelloDone())


def test_wire_entryAssign1(msg_round_trip, proto_rev):
    exclude = [] if proto_rev >= 0x0300 else [4]
    value = Value.makeBoolean(True)
    msg_round_trip(
        Message.entryAssign("Hi", 0x1234, 0x4321, value, 0x00), exclude=exclude
    )


def test_wire_entryAssign2(msg_round_trip, proto_rev):
    exclude = [] if proto_rev >= 0x0300 else [4]
    value = Value.makeString("Oh noes")
    msg_round_trip(
        Message.entryAssign("Hi", 0x1234, 0x4321, value, 0x00), exclude=exclude
    )


def test_wire_entryUpdate1(msg_round_trip, proto_rev):
    exclude = [] if proto_rev >= 0x0300 else [4]
    value = Value.makeBoolean(True)
    msg_round_trip(Message.entryUpdate(0x1234, 0x4321, value), exclude=exclude)


def test_wire_entryUpdate2(msg_round_trip, proto_rev):
    exclude = [] if proto_rev >= 0x0300 else [4]
    value = Value.makeString("Oh noes")
    msg_round_trip(Message.entryUpdate(0x1234, 0x4321, value), exclude=exclude)


def test_wire_flagsUpdate(msg_round_trip):
    msg_round_trip(Message.flagsUpdate(0x1234, 0x42), minver=0x0300)


def test_wire_entryDelete(msg_round_trip):
    msg_round_trip(Message.entryDelete(0x1234), minver=0x0300)


def test_wire_clearEntries(msg_round_trip):
    msg_round_trip(Message.clearEntries(), minver=0x0300)


def test_wire_executeRpc(msg_round_trip):
    msg_round_trip(Message.executeRpc(0x1234, 0x4321, "parameter"), minver=0x0300)


def test_wire_rpcResponse(msg_round_trip):
    msg_round_trip(Message.rpcResponse(0x1234, 0x4321, "parameter"), minver=0x0300)


# Various invalid unicode
def test_decode_invalid_string(proto_rev):
    codec = WireCodec(proto_rev)

    if proto_rev == 0x0200:
        prefix = b"\x00\x1a"
    else:
        prefix = b"\x1a"

    fp = BytesIO(prefix + b"\x00\xa7>\x03eWithJoystickCommandV2")
    rstream = ReadStream(fp)

    s = "INVALID UTF-8: b'\\x00\\xa7>\\x03eWithJoystickCommandV2'"

    assert codec.read_string(rstream) == s

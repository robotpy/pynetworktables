# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

#
# These tests are adapted from ntcore's test suite
#

from io import StringIO
from unittest.mock import call, Mock, ANY

import pytest

from _pynetworktables._impl.constants import (
    kEntryAssign,
    kEntryUpdate,
    kFlagsUpdate,
    kEntryDelete,
    kClearEntries,
    NT_PERSISTENT,
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_NOTIFY_IMMEDIATE,
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_NEW,
    NT_NOTIFY_DELETE,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS,
)

from _pynetworktables._impl.dispatcher import Dispatcher
from _pynetworktables._impl.entry_notifier import EntryNotifier
from _pynetworktables._impl.message import Message
from _pynetworktables._impl.network_connection import NetworkConnection
from _pynetworktables._impl.rpc_server import RpcServer
from _pynetworktables._impl.storage import Storage
from _pynetworktables._impl.value import Value


@pytest.fixture
def dispatcher():
    return Mock(spec=Dispatcher)


@pytest.fixture
def entry_notifier():
    return Mock(spec=EntryNotifier)


@pytest.fixture(params=[True, False])
def is_server(request):
    return request.param


@pytest.fixture
def conn():
    conn = Mock(spec=NetworkConnection)
    conn.get_proto_rev.return_value = 0x0300
    return conn


class FakeUserEntry:
    def __init__(self, *args):
        pass


@pytest.fixture
def storage_empty(dispatcher, entry_notifier, is_server):
    rpc_server = Mock(spec=RpcServer)

    storage = Storage(entry_notifier, rpc_server, FakeUserEntry)
    storage.setDispatcher(dispatcher, is_server)

    entry_notifier.m_local_notifiers = True

    yield storage

    rpc_server.stop()
    storage.stop()


@pytest.fixture
def storage_populate_one(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    entry_notifier.m_local_notifiers = False

    storage.setEntryTypeValue("foo", Value.makeBoolean(True))

    dispatcher.reset_mock()
    entry_notifier.reset_mock()
    entry_notifier.m_local_notifiers = True

    return storage


@pytest.fixture
def storage_populated(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    entry_notifier.m_local_notifiers = False

    entry_notifier.m_local_notifiers = False
    storage.setEntryTypeValue("foo", Value.makeBoolean(True))
    storage.setEntryTypeValue("foo2", Value.makeDouble(0.0))
    storage.setEntryTypeValue("bar", Value.makeDouble(1.0))
    storage.setEntryTypeValue("bar2", Value.makeBoolean(False))

    dispatcher.reset_mock()
    entry_notifier.reset_mock()
    entry_notifier.m_local_notifiers = True

    return storage


@pytest.fixture
def storage_persistent(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    entry_notifier.m_local_notifiers = False

    storage.setEntryTypeValue("boolean/true", Value.makeBoolean(True))
    storage.setEntryTypeValue("boolean/false", Value.makeBoolean(False))
    storage.setEntryTypeValue("double/neg", Value.makeDouble(-1.5))
    storage.setEntryTypeValue("double/zero", Value.makeDouble(0.0))
    storage.setEntryTypeValue("double/big", Value.makeDouble(1.3e8))
    storage.setEntryTypeValue("string/empty", Value.makeString(""))
    storage.setEntryTypeValue("string/normal", Value.makeString("hello"))
    storage.setEntryTypeValue("string/special", Value.makeString("\0\3\5\n"))
    storage.setEntryTypeValue("string/quoted", Value.makeString('"a"'))
    storage.setEntryTypeValue("raw/empty", Value.makeRaw(b""))
    storage.setEntryTypeValue("raw/normal", Value.makeRaw(b"hello"))
    storage.setEntryTypeValue("raw/special", Value.makeRaw(b"\0\3\5\n"))
    storage.setEntryTypeValue("booleanarr/empty", Value.makeBooleanArray([]))
    storage.setEntryTypeValue("booleanarr/one", Value.makeBooleanArray([True]))
    storage.setEntryTypeValue("booleanarr/two", Value.makeBooleanArray([True, False]))
    storage.setEntryTypeValue("doublearr/empty", Value.makeDoubleArray([]))
    storage.setEntryTypeValue("doublearr/one", Value.makeDoubleArray([0.5]))
    storage.setEntryTypeValue("doublearr/two", Value.makeDoubleArray([0.5, -0.25]))
    storage.setEntryTypeValue("stringarr/empty", Value.makeStringArray([]))
    storage.setEntryTypeValue("stringarr/one", Value.makeStringArray(["hello"]))
    storage.setEntryTypeValue(
        "stringarr/two", Value.makeStringArray(["hello", "world\n"])
    )
    storage.setEntryTypeValue("\0\3\5\n", Value.makeBoolean(True))
    storage.setEntryTypeValue("CaseSensitive/KeyName", Value.makeBoolean(True))
    storage.setEntryTypeValue("=", Value.makeBoolean(True))

    dispatcher.reset_mock()
    entry_notifier.reset_mock()
    entry_notifier.m_local_notifiers = True

    return storage


def test_Construct(storage_empty):
    storage = storage_empty

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0


def test_StorageEntryInit(storage_empty):
    storage = storage_empty

    assert storage.m_entries.get("foo") is None


def test_GetEntryValueNotExist(storage_empty, dispatcher):
    storage = storage_empty

    assert storage.getEntryValue("foo") is None
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert dispatcher._queueOutgoing.call_count == 0


def test_GetEntryValueExist(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    assert dispatcher._queueOutgoing.call_count == 1
    assert entry_notifier.notifyEntry.call_count == 1

    assert value == storage.getEntryValue("foo")


def test_SetEntryTypeValueAssignNew(
    storage_empty, dispatcher, entry_notifier, is_server
):
    storage = storage_empty

    # brand new entry
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    dispatcher._queueOutgoing.assert_has_calls(
        [
            call(
                Message.entryAssign("foo", 0 if is_server else 0xFFFF, 1, value, 0),
                None,
                None,
            )
        ]
    )
    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)]
    )

    if is_server:
        assert 1 == len(storage.m_idmap)
        assert value == storage.m_idmap[0].value
    else:
        assert len(storage.m_idmap) == 0


def test_SetEntryTypeValueAssignTypeChange(
    storage_populate_one, dispatcher, entry_notifier, is_server
):
    storage = storage_populate_one

    # update with different type results in assignment message
    value = Value.makeDouble(0.0)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    dispatcher._queueOutgoing.assert_has_calls(
        [
            call(
                Message.entryAssign("foo", 0 if is_server else 0xFFFF, 2, value, 0),
                None,
                None,
            )
        ]
    )
    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)]
    )


def test_SetEntryTypeValueEqualValue(storage_populate_one, dispatcher, entry_notifier):
    storage = storage_populate_one

    # update with same type and same value: change value contents but no update
    # message is issued (minimizing bandwidth usage)
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryTypeValueDifferentValue(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    # update with same type and different value results in value update message
    value = Value.makeDouble(1.0)
    storage.setEntryTypeValue("foo2", value)
    assert value == storage.m_entries.get("foo2").value

    if is_server:
        # id assigned if server; seq_num incremented
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryUpdate(1, 2, value), None, None)]
        )

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)]
    )

    if not is_server:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert dispatcher._queueOutgoing.call_count == 0
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_SetEntryTypeValueEmptyName(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("", value)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryTypeValueEmptyValue(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    storage.setEntryTypeValue("foo", None)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryValueAssignNew(storage_empty, dispatcher, entry_notifier, is_server):
    storage = storage_empty

    # brand entry
    value = Value.makeBoolean(True)
    assert storage.setEntryValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    dispatcher._queueOutgoing.assert_has_calls(
        [
            call(
                Message.entryAssign("foo", 0 if is_server else 0xFFFF, 1, value, 0),
                None,
                None,
            )
        ]
    )
    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)]
    )


def test_SetEntryValueAssignTypeChange(
    storage_populate_one, dispatcher, entry_notifier
):
    storage = storage_populate_one

    # update with different type results in error and no message
    value = Value.makeDouble(0.0)
    assert not storage.setEntryValue("foo", value)
    entry = storage.m_entries.get("foo")
    assert value != entry.value

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryValueEqualValue(storage_populate_one, dispatcher, entry_notifier):
    storage = storage_populate_one

    # update with same type and same value: change value contents but no update
    # message is issued (minimizing bandwidth usage)
    value = Value.makeBoolean(True)
    assert storage.setEntryValue("foo", value)
    entry = storage.m_entries.get("foo")
    assert value == entry.value

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryValueDifferentValue(
    storage_populated, is_server, dispatcher, entry_notifier
):
    storage = storage_populated

    # update with same type and different value results in value update message
    value = Value.makeDouble(1.0)
    assert storage.setEntryValue("foo2", value)
    entry = storage.m_entries.get("foo2")
    assert value == entry.value

    # client shouldn't send an update as id not assigned yet
    if is_server:
        # id assigned if server; seq_num incremented
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryUpdate(1, 2, value), None, None)]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)]
    )

    if not is_server:
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_SetEntryValueEmptyName(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    value = Value.makeBoolean(True)
    assert storage.setEntryValue("", value)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryValueEmptyValue(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    assert storage.setEntryValue("foo", None)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetDefaultEntryAssignNew(storage_empty, dispatcher, entry_notifier, is_server):
    storage = storage_empty

    # brand new entry
    value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert ret_val
    assert value == storage.m_entries.get("foo").value

    dispatcher._queueOutgoing.assert_has_calls(
        [
            call(
                Message.entryAssign("foo", 0 if is_server else 0xFFFF, 1, value, 0),
                None,
                None,
            )
        ]
    )
    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)]
    )


def test_SetDefaultEntryExistsSameType(
    storage_populate_one, dispatcher, entry_notifier
):
    storage = storage_populate_one

    # existing entry
    value = Value.makeBoolean(False)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert ret_val
    assert value != storage.m_entries.get("foo").value

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetDefaultEntryExistsDifferentType(
    storage_populate_one, dispatcher, entry_notifier
):
    storage = storage_populate_one

    # existing entry is boolean
    value = Value.makeDouble(2.0)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert not ret_val
    # should not have updated value in table if it already existed.
    assert value != storage.m_entries.get("foo").value

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_empty_SetDefaultEntryEmptyName(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", value)
    assert not ret_val
    assert "foo" not in storage.m_entries

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_empty_SetDefaultEntryEmptyValue(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    # value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", None)
    assert not ret_val
    assert "foo" not in storage.m_entries

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_populated_SetDefaultEntryEmptyName(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", value)
    assert not ret_val
    # assert that no entries get added
    assert 4 == len(storage.m_entries)
    if is_server:
        assert 4 == len(storage.m_idmap)

    else:
        assert 0 == len(storage.m_idmap)

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_populated_SetDefaultEntryEmptyValue(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    # value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", None)
    assert not ret_val
    # assert that no entries get added
    assert 4 == len(storage.m_entries)
    if is_server:
        assert 4 == len(storage.m_idmap)

    else:
        assert 0 == len(storage.m_idmap)

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryFlagsNew(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    # flags setting doesn't create an entry
    storage.setEntryFlags("foo", 0)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryFlagsEqualValue(storage_populate_one, dispatcher, entry_notifier):
    storage = storage_populate_one

    # update with same value: no update message is issued (minimizing bandwidth
    # usage)
    storage.setEntryFlags("foo", 0)
    entry = storage.m_entries.get("foo")
    assert 0 == entry.flags

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_SetEntryFlagsDifferentValue(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    # update with different value results in flags update message
    storage.setEntryFlags("foo2", 1)
    entry = storage.m_entries.get("foo2")
    assert 1 == entry.flags

    if is_server:
        # id assigned as this is the server
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.flagsUpdate(1, 1), None, None)]
        )
    else:
        # shouldn't send an update id not assigned yet
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", entry.value, NT_NOTIFY_FLAGS | NT_NOTIFY_LOCAL)]
    )


def test_SetEntryFlagsEmptyName(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    storage.setEntryFlags("", 0)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_GetEntryFlagsNotExist(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    assert 0 == storage.getEntryFlags("foo")
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_GetEntryFlagsExist(
    storage_populate_one, dispatcher, entry_notifier, is_server
):
    storage = storage_populate_one

    storage.setEntryFlags("foo", 1)
    assert 1 == storage.getEntryFlags("foo")

    assert dispatcher._queueOutgoing.call_count == (1 if is_server else 0)
    assert entry_notifier.notifyEntry.call_count == 1


def test_DeleteEntryNotExist(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    storage.deleteEntry("foo")

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_DeleteEntryExist(storage_populated, dispatcher, entry_notifier, is_server):
    storage = storage_populated

    storage.deleteEntry("foo2")

    entry = storage.m_entries.get("foo2")
    assert entry is not None
    assert entry.value is None
    assert entry.id == 0xFFFF
    assert entry.local_write == False

    # client shouldn't send an update as id not assigned yet
    if is_server:
        # id assigned as this is the server
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryDelete(1), None, None)]
        )
    else:
        # shouldn't send an update id not assigned yet
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", Value.makeDouble(0.0), NT_NOTIFY_DELETE | NT_NOTIFY_LOCAL)]
    )

    if is_server:
        assert len(storage.m_idmap) >= 2
        assert not storage.m_idmap[1]


def test_DeleteAllEntriesEmpty(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    storage.deleteAllEntries()
    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_deleteAllEntries(storage_populated, dispatcher, entry_notifier):
    storage = storage_populated

    storage.deleteAllEntries()
    assert len(storage.m_entries) == 4
    assert len(storage.getEntries("", 0)) == 0

    assert storage.m_entries["foo2"].value is None

    dispatcher._queueOutgoing.assert_has_calls(
        [call(Message.clearEntries(), None, None)]
    )

    entry_notifier.notifyEntry.assert_has_calls(
        [call(ANY, ANY, ANY, NT_NOTIFY_DELETE | NT_NOTIFY_LOCAL)] * 4
    )


def test_DeleteAllEntriesPersistent(storage_populated, dispatcher, entry_notifier):
    storage = storage_populated

    entry = storage.m_entries.get("foo2")
    entry.flags = NT_PERSISTENT
    entry.isPersistent = True
    storage.deleteAllEntries()
    assert len(storage.getEntries("", 0)) == 1
    assert "foo2" in storage.m_entries

    dispatcher._queueOutgoing.assert_has_calls(
        [call(Message.clearEntries(), None, None)]
    )

    entry_notifier.notifyEntry.assert_has_calls(
        [call(ANY, ANY, ANY, NT_NOTIFY_DELETE | NT_NOTIFY_LOCAL)] * 3
    )


def test_GetEntryInfoAll(storage_populated):
    storage = storage_populated

    info = storage.getEntryInfo("", 0)
    assert 4 == len(info)


def test_GetEntryInfoPrefix(storage_populated):
    storage = storage_populated

    info = storage.getEntryInfo("foo", 0)
    assert 2 == len(info)
    if info[0].name == "foo":
        assert "foo" == info[0].name
        assert NT_BOOLEAN == info[0].type
        assert "foo2" == info[1].name
        assert NT_DOUBLE == info[1].type

    else:
        assert "foo2" == info[0].name
        assert NT_DOUBLE == info[0].type
        assert "foo" == info[1].name
        assert NT_BOOLEAN == info[1].type


def test_GetEntryInfoTypes(storage_populated):
    storage = storage_populated

    info = storage.getEntryInfo("", NT_DOUBLE)
    assert 2 == len(info)
    assert NT_DOUBLE == info[0].type
    assert NT_DOUBLE == info[1].type
    if info[0].name == "foo2":
        assert "foo2" == info[0].name
        assert "bar" == info[1].name

    else:
        assert "bar" == info[0].name
        assert "foo2" == info[1].name


def test_GetEntryInfoPrefixTypes(storage_populated):
    storage = storage_populated

    info = storage.getEntryInfo("bar", NT_BOOLEAN)
    assert 1 == len(info)
    assert "bar2" == info[0].name
    assert NT_BOOLEAN == info[0].type


def test_SavePersistentEmpty(storage_persistent):
    storage = storage_persistent

    fp = StringIO()
    storage.savePersistent(fp=fp, periodic=False)

    fp.seek(0)
    assert "[NetworkTables Storage 3.0]\n\n" == fp.read()


def test_savePersistent(storage_persistent):
    storage = storage_persistent

    for e in storage.m_entries.values():
        e.flags = NT_PERSISTENT
        e.isPersistent = True

    fp = StringIO()
    storage.savePersistent(fp=fp, periodic=False)

    fp.seek(0)

    line = fp.readline()[:-1]
    assert "[NetworkTables Storage 3.0]" == line
    line = fp.readline()[:-1]
    assert 'boolean "\\x00\\x03\\x05\\n"=true' == line
    line = fp.readline()[:-1]
    assert 'boolean "="=true' == line
    line = fp.readline()[:-1]
    assert 'boolean "CaseSensitive/KeyName"=true' == line
    line = fp.readline()[:-1]
    assert 'boolean "boolean/false"=false' == line
    line = fp.readline()[:-1]
    assert 'boolean "boolean/true"=true' == line
    line = fp.readline()[:-1]
    assert 'array boolean "booleanarr/empty"=' == line
    line = fp.readline()[:-1]
    assert 'array boolean "booleanarr/one"=true' == line
    line = fp.readline()[:-1]
    assert 'array boolean "booleanarr/two"=true,false' == line
    line = fp.readline()[:-1]
    # this differs from ntcore
    assert 'double "double/big"=130000000.0' == line
    line = fp.readline()[:-1]
    assert 'double "double/neg"=-1.5' == line
    line = fp.readline()[:-1]
    assert 'double "double/zero"=0.0' == line
    line = fp.readline()[:-1]
    assert 'array double "doublearr/empty"=' == line
    line = fp.readline()[:-1]
    assert 'array double "doublearr/one"=0.5' == line
    line = fp.readline()[:-1]
    assert 'array double "doublearr/two"=0.5,-0.25' == line
    line = fp.readline()[:-1]
    assert 'raw "raw/empty"=' == line
    line = fp.readline()[:-1]
    assert 'raw "raw/normal"=aGVsbG8=' == line
    line = fp.readline()[:-1]
    assert 'raw "raw/special"=AAMFCg==' == line
    line = fp.readline()[:-1]
    assert 'string "string/empty"=""' == line
    line = fp.readline()[:-1]
    assert 'string "string/normal"="hello"' == line
    line = fp.readline()[:-1]
    assert 'string "string/quoted"="\\"a\\""' == line
    line = fp.readline()[:-1]
    assert 'string "string/special"="\\x00\\x03\\x05\\n"' == line
    line = fp.readline()[:-1]
    assert 'array string "stringarr/empty"=' == line
    line = fp.readline()[:-1]
    assert 'array string "stringarr/one"="hello"' == line
    line = fp.readline()[:-1]
    assert 'array string "stringarr/two"="hello","world\\n"' == line
    line = fp.readline()[:-1]
    assert "" == line


def test_LoadPersistentBadHeader(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    # EXPECT_CALL(warn, Warn(1, llvm.StringRef("header line mismatch, rest of file")))
    fp = StringIO(None)
    assert storage.loadPersistent(fp=fp) is not None

    fp = StringIO("[NetworkTables")
    # EXPECT_CALL(warn, Warn(1, llvm.StringRef("header line mismatch, rest of file")))
    assert storage.loadPersistent(fp=fp) is not None

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_LoadPersistentCommentHeader(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    fp = StringIO("\n; comment\n# comment\n[NetworkTables Storage 3.0]\n")
    assert storage.loadPersistent(fp=fp) is None

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_LoadPersistentEmptyName(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    fp = StringIO('[NetworkTables Storage 3.0]\nboolean ""=true\n')
    assert storage.loadPersistent(fp=fp) is None

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_LoadPersistentAssign(storage_empty, dispatcher, entry_notifier, is_server):
    storage = storage_empty

    fp = StringIO('[NetworkTables Storage 3.0]\nboolean "foo"=true\n')
    assert storage.loadPersistent(fp=fp) is None

    entry = storage.m_entries.get("foo")
    assert Value.makeBoolean(True) == entry.value
    assert NT_PERSISTENT == entry.flags
    assert entry.isPersistent

    dispatcher._queueOutgoing.assert_has_calls(
        [
            call(
                Message.entryAssign(
                    "foo", 0 if is_server else 0xFFFF, 1, entry.value, NT_PERSISTENT
                ),
                None,
                None,
            )
        ]
    )

    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", entry.value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)]
    )


def test_LoadPersistentUpdateFlags(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    fp = StringIO('[NetworkTables Storage 3.0]\ndouble "foo2"=0.0\n')
    assert storage.loadPersistent(fp=fp) is None

    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(0.0) == entry.value
    assert NT_PERSISTENT == entry.flags
    assert entry.isPersistent

    if is_server:
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.flagsUpdate(1, NT_PERSISTENT), None, None)]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", entry.value, NT_NOTIFY_FLAGS | NT_NOTIFY_LOCAL)]
    )


def test_LoadPersistentUpdateValue(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    entry = storage.m_entries.get("foo2")
    entry.flags = NT_PERSISTENT
    entry.isPersistent = True

    fp = StringIO('[NetworkTables Storage 3.0]\ndouble "foo2"=1.0\n')
    assert storage.loadPersistent(fp=fp) is None

    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(1.0) == entry.value
    assert NT_PERSISTENT == entry.flags
    assert entry.isPersistent

    # client shouldn't send an update as id not assigned yet
    if is_server:
        # id assigned as this is the server; seq_num incremented
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryUpdate(1, 2, entry.value), None, None)]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(1, "foo2", entry.value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)]
    )

    if not is_server:
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_LoadPersistentUpdateValueFlags(
    storage_populated, dispatcher, entry_notifier, is_server
):
    storage = storage_populated

    fp = StringIO('[NetworkTables Storage 3.0]\ndouble "foo2"=1.0\n')
    assert storage.loadPersistent(fp=fp) is None

    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(1.0) == entry.value
    assert NT_PERSISTENT == entry.flags
    assert entry.isPersistent

    # client shouldn't send an update as id not assigned yet
    if is_server:
        # id assigned as this is the server; seq_num incremented
        dispatcher._queueOutgoing.assert_has_calls(
            [
                call(Message.entryUpdate(1, 2, entry.value), None, None),
                call(Message.flagsUpdate(1, NT_PERSISTENT), None, None),
            ]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [
            call(
                1,
                "foo2",
                entry.value,
                NT_NOTIFY_FLAGS | NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL,
            )
        ]
    )

    if not is_server:
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_loadPersistent(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    inp = "[NetworkTables Storage 3.0]\n"
    inp += 'boolean "\\x00\\x03\\x05\\n"=true\n'
    inp += 'boolean "CaseSensitive/KeyName"=true\n'
    inp += 'boolean "boolean/false"=false\n'
    inp += 'boolean "boolean/true"=true\n'
    inp += 'array boolean "booleanarr/empty"=\n'
    inp += 'array boolean "booleanarr/one"=true\n'
    inp += 'array boolean "booleanarr/two"=true,false\n'
    inp += 'double "double/big"=1.3e+08\n'
    inp += 'double "double/neg"=-1.5\n'
    inp += 'double "double/zero"=0\n'
    inp += 'array double "doublearr/empty"=\n'
    inp += 'array double "doublearr/one"=0.5\n'
    inp += 'array double "doublearr/two"=0.5,-0.25\n'
    inp += 'raw "raw/empty"=\n'
    inp += 'raw "raw/normal"=aGVsbG8=\n'
    inp += 'raw "raw/special"=AAMFCg==\n'
    inp += 'string "string/empty"=""\n'
    inp += 'string "string/normal"="hello"\n'
    inp += 'string "string/special"="\\x00\\x03\\x05\\n"\n'
    inp += 'string "string/quoted"="\\"a\\""\n'
    inp += 'array string "stringarr/empty"=\n'
    inp += 'array string "stringarr/one"="hello"\n'
    inp += 'array string "stringarr/two"="hello","world\\n"\n'

    fp = StringIO(inp)
    assert storage.loadPersistent(fp=fp) is None

    dispatcher._queueOutgoing.assert_has_calls([call(ANY, None, None)] * 23)

    entry_notifier.notifyEntry.assert_has_calls(
        [call(ANY, ANY, ANY, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)] * 23
    )

    assert Value.makeBoolean(True) == storage.getEntryValue("boolean/true")
    assert Value.makeBoolean(False) == storage.getEntryValue("boolean/false")
    assert Value.makeDouble(-1.5) == storage.getEntryValue("double/neg")
    assert Value.makeDouble(0.0) == storage.getEntryValue("double/zero")
    assert Value.makeDouble(1.3e8) == storage.getEntryValue("double/big")
    assert Value.makeString("") == storage.getEntryValue("string/empty")
    assert Value.makeString("hello") == storage.getEntryValue("string/normal")
    assert Value.makeString("\0\3\5\n") == storage.getEntryValue("string/special")
    assert Value.makeString('"a"') == storage.getEntryValue("string/quoted")
    assert Value.makeRaw(b"") == storage.getEntryValue("raw/empty")
    assert Value.makeRaw(b"hello") == storage.getEntryValue("raw/normal")
    assert Value.makeRaw(b"\0\3\5\n") == storage.getEntryValue("raw/special")
    assert Value.makeBooleanArray([]) == storage.getEntryValue("booleanarr/empty")
    assert Value.makeBooleanArray([True]) == storage.getEntryValue("booleanarr/one")
    assert Value.makeBooleanArray([True, False]) == storage.getEntryValue(
        "booleanarr/two"
    )
    assert Value.makeDoubleArray([]) == storage.getEntryValue("doublearr/empty")
    assert Value.makeDoubleArray([0.5]) == storage.getEntryValue("doublearr/one")
    assert Value.makeDoubleArray([0.5, -0.25]) == storage.getEntryValue("doublearr/two")
    assert Value.makeStringArray([]) == storage.getEntryValue("stringarr/empty")
    assert Value.makeStringArray(["hello"]) == storage.getEntryValue("stringarr/one")
    assert Value.makeStringArray(["hello", "world\n"]) == storage.getEntryValue(
        "stringarr/two"
    )
    assert Value.makeBoolean(True) == storage.getEntryValue("\0\3\5\n")
    assert Value.makeBoolean(True) == storage.getEntryValue("CaseSensitive/KeyName")


def test_LoadPersistentWarn(storage_empty, dispatcher, entry_notifier):
    storage = storage_empty

    fp = StringIO('[NetworkTables Storage 3.0]\nboolean "foo"=foo\n')

    # EXPECT_CALL(warn,
    #            Warn(2, llvm.StringRef("unrecognized boolean value, not 'True' or 'False'")))
    assert storage.loadPersistent(fp=fp) is None

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_ProcessIncomingEntryAssign0(
    storage_empty, dispatcher, entry_notifier, is_server, conn
):
    storage = storage_empty
    value = Value.makeDouble(1.0)

    entry_id = 0xFFFF if is_server else 0

    storage.processIncoming(Message.entryAssign("foo", entry_id, 0, value, 0), conn)

    if is_server:
        # id assign message reply generated on the server sent to everyone
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryAssign("foo", 0, 0, value, 0), None, None)]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls([call(0, "foo", value, NT_NOTIFY_NEW)])


def test_ProcessIncomingEntryAssign1(
    storage_populate_one, dispatcher, entry_notifier, is_server, conn
):
    storage = storage_populate_one
    value = Value.makeDouble(1.0)

    storage.processIncoming(Message.entryAssign("foo", 0, 1, value, 0), conn)

    # EXPECT_CALL(*conn, proto_rev()).WillRepeatedly(Return(0x0300u))
    if is_server:
        # server broadcasts new value to all *other* connections
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryAssign("foo", 0, 1, value, 0), None, conn)]
        )
    else:
        assert dispatcher._queueOutgoing.call_count == 0

    entry_notifier.notifyEntry.assert_has_calls(
        [call(0, "foo", value, NT_NOTIFY_UPDATE)]
    )


def test_ProcessIncomingEntryAssignIgnore(
    storage_populate_one, dispatcher, entry_notifier, is_server, conn
):
    storage = storage_populate_one
    value = Value.makeDouble(1.0)

    storage.processIncoming(Message.entryAssign("foo", 0xFFFF, 1, value, 0), conn)

    assert dispatcher._queueOutgoing.call_count == 0
    assert entry_notifier.notifyEntry.call_count == 0


def test_ProcessIncomingEntryAssignWithFlags(
    storage_populate_one, dispatcher, entry_notifier, is_server, conn
):
    storage = storage_populate_one
    value = Value.makeDouble(1.0)

    storage.processIncoming(Message.entryAssign("foo", 0, 1, value, 0x2), conn)

    # EXPECT_CALL(*conn, proto_rev()).WillRepeatedly(Return(0x0300u))
    if is_server:
        # server broadcasts new value/flags to all *other* connections
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.entryAssign("foo", 0, 1, value, 0x2), None, conn)]
        )

        entry_notifier.notifyEntry.assert_has_calls(
            [call(0, "foo", value, NT_NOTIFY_UPDATE | NT_NOTIFY_FLAGS)]
        )

    else:
        # client forces flags back when an assign message is received for an
        # existing entry with different flags
        dispatcher._queueOutgoing.assert_has_calls(
            [call(Message.flagsUpdate(0, 0), None, None)]
        )

        entry_notifier.notifyEntry.assert_has_calls(
            [call(0, "foo", value, NT_NOTIFY_UPDATE)]
        )


def test_DeleteCheckHandle(storage_populate_one, dispatcher, entry_notifier, is_server):
    storage = storage_populate_one

    handle = storage.getEntryId("foo")
    storage.deleteEntry("foo")
    storage.setEntryTypeValue("foo", Value.makeBoolean(True))

    handle2 = storage.getEntryId("foo")
    assert handle == handle2


def test_DeletedEntryFlags(storage_populate_one, dispatcher, entry_notifier, is_server):
    storage = storage_populate_one

    handle = storage.getEntryId("foo")
    storage.setEntryFlags("foo", 2)
    storage.deleteEntry("foo")

    assert storage.getEntryFlags("foo") == 0
    assert storage.getEntryFlags(handle) == 0
    storage.setEntryFlags("foo", 4)
    storage.setEntryFlags(handle, 4)
    assert storage.getEntryFlags("foo") == 0
    assert storage.getEntryFlags(handle) == 0


def test_DeletedDeleteAllEntries(
    storage_populate_one, dispatcher, entry_notifier, is_server
):
    storage = storage_populate_one

    storage.deleteEntry("foo")
    assert dispatcher._queueOutgoing.call_count == (1 if is_server else 0)

    storage.deleteAllEntries()

    assert dispatcher._queueOutgoing.call_count == (1 if is_server else 0)


def test_DeletedGetEntries(storage_populate_one, dispatcher, entry_notifier, is_server):
    storage = storage_populate_one

    storage.deleteEntry("foo")
    assert storage.getEntries("", 0) == []

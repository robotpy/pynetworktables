'''----------------------------------------------------------------------------'''
''' Copyright (c) FIRST 2015. All Rights Reserved.                             '''
''' Open Source Software - may be modified and shared by FRC teams. The code   '''
''' must be accompanied by the FIRST BSD license file in the root directory of '''
''' the project.                                                               '''
'''----------------------------------------------------------------------------'''

#
# These tests are adapted from ntcore's test suite
#

from collections import namedtuple

try:
    from StringIO import cStringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

import pytest

from ntcore.constants import (
    kEntryAssign,
    kEntryUpdate,
    kFlagsUpdate,
    kEntryDelete,
    kClearEntries,
    
    NT_PERSISTENT,
    
    NT_BOOLEAN,
    NT_DOUBLE
)

from ntcore.support.compat import PY2
from ntcore.notifier import Notifier
from ntcore.rpc_server import RpcServer
from ntcore.storage import Storage
from ntcore.value import Value

OutgoingData = namedtuple('OutgoingData', [
    'msg',
    'only',
    'conn'
])


@pytest.fixture
def outgoing():
    return []

@pytest.fixture(params=[True, False])
def is_server(request):
    return request.param

@pytest.fixture
def queue_outgoing(outgoing):
    def _fn(msg, only, conn):
        outgoing.append(OutgoingData(msg, only, conn))
    return _fn

@pytest.fixture
def storage_empty(is_server, queue_outgoing):
    notifier = Notifier()
    rpc_server = RpcServer()
    
    storage = Storage(notifier, rpc_server)
    storage.setOutgoing(queue_outgoing, is_server)
    
    yield storage
    
    rpc_server.stop()
    notifier.stop()
    storage.stop()
    

@pytest.fixture
def storage_populate_one(storage_empty, outgoing):
    storage = storage_empty
    
    storage.setEntryTypeValue("foo", Value.makeBoolean(True))
    del outgoing[:]
    
    return storage

@pytest.fixture
def storage_populated(storage_empty, outgoing):
    storage = storage_empty
    
    storage.setEntryTypeValue("foo", Value.makeBoolean(True))
    storage.setEntryTypeValue("foo2", Value.makeDouble(0.0))
    storage.setEntryTypeValue("bar", Value.makeDouble(1.0))
    storage.setEntryTypeValue("bar2", Value.makeBoolean(False))
    del outgoing[:]

    return storage

@pytest.fixture
def storage_persistent(storage_empty, outgoing):
    storage = storage_empty
    
    storage.setEntryTypeValue("boolean/True", Value.makeBoolean(True))
    storage.setEntryTypeValue("boolean/False", Value.makeBoolean(False))
    storage.setEntryTypeValue("double/neg", Value.makeDouble(-1.5))
    storage.setEntryTypeValue("double/zero", Value.makeDouble(0.0))
    storage.setEntryTypeValue("double/big", Value.makeDouble(1.3e8))
    storage.setEntryTypeValue("string/empty", Value.makeString(""))
    storage.setEntryTypeValue("string/normal", Value.makeString("hello"))
    storage.setEntryTypeValue("string/special", Value.makeString("\0\3\5\n"))
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
    storage.setEntryTypeValue("stringarr/two", Value.makeStringArray(["hello", "world\n"]))
    storage.setEntryTypeValue("\0\3\5\n",Value.makeBoolean(True))
    del outgoing[:]
    
    return storage


def test_Construct(storage_empty):
    storage = storage_empty
    
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0


def test_StorageEntryInit(storage_empty):
    storage = storage_empty
    
    assert storage.m_entries.get("foo") is None


def test_GetEntryValueNotExist(storage_empty, outgoing):
    storage = storage_empty
    
    assert storage.getEntryValue("foo") is None
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_GetEntryValueExist(storage_empty, outgoing):
    storage = storage_empty
    
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    del outgoing[:]
    assert value == storage.getEntryValue("foo")


def test_SetEntryTypeValueAssignNew(storage_empty, outgoing, is_server):
    storage = storage_empty
    
    # brand entry
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value
    if is_server:
        assert 1 == len(storage.m_idmap)
        assert value == storage.m_idmap[0].value

    else:
        assert len(storage.m_idmap) == 0


    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kEntryAssign == msg.type
    assert "foo" == msg.str
    if is_server:
        assert 0 == msg.id    # assigned as server

    else:
        assert 0xffff == msg.id    # not assigned as client

    assert 1 == msg.seq_num_uid
    assert value == msg.value
    assert 0 == msg.flags


def test_SetEntryTypeValueAssignTypeChange(storage_populate_one, outgoing, is_server):
    storage = storage_populate_one
    
    # update with different type results in assignment message
    value = Value.makeDouble(0.0)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kEntryAssign == msg.type
    assert "foo" == msg.str
    if is_server:
        assert 0 == msg.id    # assigned as server

    else:
        assert 0xffff == msg.id    # not assigned as client

    assert 2 == msg.seq_num_uid  # incremented
    assert value == msg.value
    assert 0 == msg.flags


def test_SetEntryTypeValueEqualValue(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # update with same type and same value: change value contents but no update
    # message is issued (minimizing bandwidth usage)
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("foo", value)
    assert value == storage.m_entries.get("foo").value
    assert len(outgoing) == 0


def test_SetEntryTypeValueDifferentValue(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    # update with same type and different value results in value update message
    value = Value.makeDouble(1.0)
    storage.setEntryTypeValue("foo2", value)
    assert value == storage.m_entries.get("foo2").value

    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kEntryUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert 2 == msg.seq_num_uid  # incremented
        assert value == msg.value

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_SetEntryTypeValueEmptyName(storage_empty, outgoing):
    storage = storage_empty
    
    value = Value.makeBoolean(True)
    storage.setEntryTypeValue("", value)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_SetEntryTypeValueEmptyValue(storage_empty, outgoing):
    storage = storage_empty
    
    storage.setEntryTypeValue("foo", None)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_SetEntryValueAssignNew(storage_empty, outgoing, is_server):
    storage = storage_empty
    
    # brand entry
    value = Value.makeBoolean(True)
    assert storage.setEntryValue("foo", value)
    assert value == storage.m_entries.get("foo").value

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kEntryAssign == msg.type
    assert "foo" == msg.str
    if is_server:
        assert 0 == msg.id    # assigned as server

    else:
        assert 0xffff == msg.id    # not assigned as client

    assert 0 == msg.seq_num_uid
    assert value == msg.value
    assert 0 == msg.flags


def test_SetEntryValueAssignTypeChange(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # update with different type results in error and no message
    value = Value.makeDouble(0.0)
    assert not storage.setEntryValue("foo", value)
    entry = storage.m_entries.get("foo")
    assert value != entry.value
    assert len(outgoing) == 0


def test_SetEntryValueEqualValue(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # update with same type and same value: change value contents but no update
    # message is issued (minimizing bandwidth usage)
    value = Value.makeBoolean(True)
    assert storage.setEntryValue("foo", value)
    entry = storage.m_entries.get("foo")
    assert value == entry.value
    assert len(outgoing) == 0


def test_SetEntryValueDifferentValue(storage_populated, is_server, outgoing):
    storage = storage_populated
    
    # update with same type and different value results in value update message
    value = Value.makeDouble(1.0)
    assert storage.setEntryValue("foo2", value)
    entry = storage.m_entries.get("foo2")
    assert value == entry.value

    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kEntryUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert 2 == msg.seq_num_uid  # incremented
        assert value == msg.value

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented


def test_SetEntryValueEmptyName(storage_empty, outgoing):
    storage = storage_empty
    
    value = Value.makeBoolean(True)
    assert storage.setEntryValue("", value)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_SetEntryValueEmptyValue(storage_empty, outgoing):
    storage = storage_empty
    
    assert storage.setEntryValue("foo", None)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_SetDefaultEntryAssignNew(storage_empty, outgoing, is_server):
    storage = storage_empty
    
    # brand entry
    value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert ret_val
    assert value == storage.m_entries.get("foo").value

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kEntryAssign == msg.type
    assert "foo" == msg.str
    if is_server:
        assert 0 == msg.id    # assigned as server

    else:
        assert 0xffff == msg.id    # not assigned as client

    assert 0 == msg.seq_num_uid
    assert value == msg.value
    assert 0 == msg.flags


def test_SetDefaultEntryExistsSameType(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # existing entry
    value = Value.makeBoolean(False)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert ret_val
    assert value != storage.m_entries.get("foo").value

    assert len(outgoing) == 0


def test_SetDefaultEntryExistsDifferentType(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # existing entry is boolean
    value = Value.makeDouble(2.0)
    ret_val = storage.setDefaultEntryValue("foo", value)
    assert not ret_val
    # should not have updated value in table if it already existed.
    assert value != storage.m_entries.get("foo").value

    assert len(outgoing) == 0


def test_empty_SetDefaultEntryEmptyName(storage_empty, outgoing):
    storage = storage_empty
    
    value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", value)
    assert not ret_val
    assert "foo" not in storage.m_entries
    
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_empty_SetDefaultEntryEmptyValue(storage_empty, outgoing):
    storage = storage_empty
    
    #value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", None)
    assert not ret_val
    assert "foo" not in storage.m_entries
    
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_populated_SetDefaultEntryEmptyName(storage_populated, outgoing, is_server):
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

    assert len(outgoing) == 0


def test_populated_SetDefaultEntryEmptyValue(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    #value = Value.makeBoolean(True)
    ret_val = storage.setDefaultEntryValue("", None)
    assert not ret_val
    # assert that no entries get added
    assert 4 == len(storage.m_entries)
    if is_server:
        assert 4 == len(storage.m_idmap)

    else:
        assert 0 == len(storage.m_idmap)

    assert len(outgoing) == 0


def test_SetEntryFlagsNew(storage_empty, outgoing):
    storage = storage_empty
    
    # flags setting doesn't create an entry
    storage.setEntryFlags("foo", 0)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_SetEntryFlagsEqualValue(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    # update with same value: no update message is issued (minimizing bandwidth
    # usage)
    storage.setEntryFlags("foo", 0)
    entry = storage.m_entries.get("foo")
    assert 0 == entry.flags
    assert len(outgoing) == 0


def test_SetEntryFlagsDifferentValue(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    # update with different value results in flags update message
    storage.setEntryFlags("foo2", 1)
    assert 1 == storage.m_entries.get("foo2").flags

    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kFlagsUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert 1 == msg.flags

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0


def test_SetEntryFlagsEmptyName(storage_empty, outgoing):
    storage = storage_empty
    
    storage.setEntryFlags("", 0)
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_GetEntryFlagsNotExist(storage_empty, outgoing):
    storage = storage_empty
    
    assert 0 == storage.getEntryFlags("foo")
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_GetEntryFlagsExist(storage_populate_one, outgoing):
    storage = storage_populate_one
    
    storage.setEntryFlags("foo", 1)
    del outgoing[:]
    assert 1 == storage.getEntryFlags("foo")
    assert len(outgoing) == 0


def test_DeleteEntryNotExist(storage_empty, outgoing):
    storage = storage_empty
    
    storage.deleteEntry("foo")
    assert len(outgoing) == 0


def test_DeleteEntryExist(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    assert "foo2" in storage.m_entries
    storage.deleteEntry("foo2")
    assert "foo2" not in storage.m_entries
    if is_server:
        assert len(storage.m_idmap) >= 2
        assert not storage.m_idmap[1]


    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kEntryDelete == msg.type
        assert 1 == msg.id  # assigned as server

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0


def test_DeleteAllEntriesEmpty(storage_empty, outgoing):
    storage = storage_empty
    
    storage.deleteAllEntries()
    assert len(outgoing) == 0


def test_deleteAllEntries(storage_populated, outgoing):
    storage = storage_populated
    
    storage.deleteAllEntries()
    assert len(storage.m_entries) == 0

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kClearEntries == msg.type


def test_DeleteAllEntriesPersistent(storage_populated, outgoing):
    storage = storage_populated
    
    storage.m_entries.get("foo2").flags = NT_PERSISTENT
    storage.deleteAllEntries()
    assert 1 == len(storage.m_entries)
    assert "foo2" in storage.m_entries

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kClearEntries == msg.type


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

def py2(l):
    # Python 2's configparser can't write without spaces
    if PY2:
        l = l.replace(' = ', '=')
    return l
        

def test_savePersistent(storage_persistent):
    storage = storage_persistent
    
    for e in storage.m_entries.values():
        e.flags = NT_PERSISTENT
    
    fp = StringIO()
    storage.savePersistent(fp=fp, periodic=False)
    
    fp.seek(0)
    
    line = fp.readline()[:-1]
    assert "[NetworkTables Storage 3.0]" == py2(line)
    line = fp.readline()[:-1]
    assert "boolean \"\\x00\\x03\\x05\\n\"=true" == py2(line)
    line = fp.readline()[:-1]
    assert "boolean \"boolean/false\"=false" == py2(line)
    line = fp.readline()[:-1]
    assert "boolean \"boolean/true\"=true" == py2(line)
    line = fp.readline()[:-1]
    assert "array boolean \"booleanarr/empty\"=" == py2(line)
    line = fp.readline()[:-1]
    assert "array boolean \"booleanarr/one\"=true" == py2(line)
    line = fp.readline()[:-1]
    assert "array boolean \"booleanarr/two\"=true,false" == py2(line)
    line = fp.readline()[:-1]
    # this differs from ntcore 
    assert "double \"double/big\"=130000000.0" == py2(line)
    line = fp.readline()[:-1]
    assert "double \"double/neg\"=-1.5" == py2(line)
    line = fp.readline()[:-1]
    assert "double \"double/zero\"=0.0" == py2(line)
    line = fp.readline()[:-1]
    assert "array double \"doublearr/empty\"=" == py2(line)
    line = fp.readline()[:-1]
    assert "array double \"doublearr/one\"=0.5" == py2(line)
    line = fp.readline()[:-1]
    assert "array double \"doublearr/two\"=0.5,-0.25" == py2(line)
    line = fp.readline()[:-1]
    assert "raw \"raw/empty\"=" == py2(line)
    line = fp.readline()[:-1]
    assert "raw \"raw/normal\"=aGVsbG8=" == py2(line)
    line = fp.readline()[:-1]
    assert "raw \"raw/special\"=AAMFCg==" == py2(line)
    line = fp.readline()[:-1]
    assert "string \"string/empty\"=\"\"" == py2(line)
    line = fp.readline()[:-1]
    assert "string \"string/normal\"=\"hello\"" == py2(line)
    line = fp.readline()[:-1]
    assert "string \"string/special\"=\"\\x00\\x03\\x05\\n\"" == py2(line)
    line = fp.readline()[:-1]
    assert "array string \"stringarr/empty\"=" == py2(line)
    line = fp.readline()[:-1]
    assert "array string \"stringarr/one\"=\"hello\"" == py2(line)
    line = fp.readline()[:-1]
    assert "array string \"stringarr/two\"=\"hello\",\"world\\n\"" == py2(line)
    line = fp.readline()[:-1]
    assert "" == line


def test_LoadPersistentBadHeader(storage_empty, outgoing):
    storage = storage_empty
    
    #EXPECT_CALL(warn, Warn(1, llvm.StringRef("header line mismatch, rest of file")))
    fp = StringIO(None)
    assert storage.loadPersistent(fp=fp) is not None

    fp = StringIO("[NetworkTables")
    #EXPECT_CALL(warn, Warn(1, llvm.StringRef("header line mismatch, rest of file")))
    assert storage.loadPersistent(fp=fp) is not None
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_LoadPersistentCommentHeader(storage_empty, outgoing):
    storage = storage_empty
    
    fp = StringIO("\n; comment\n# comment\n[NetworkTables Storage 3.0]\n")
    assert storage.loadPersistent(fp=fp) is None
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_LoadPersistentEmptyName(storage_empty, outgoing):
    storage = storage_empty
    
    fp = StringIO("[NetworkTables Storage 3.0]\nboolean \"\"=true\n")
    assert storage.loadPersistent(fp=fp) is None
    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0


def test_LoadPersistentAssign(storage_empty, outgoing, is_server):
    storage = storage_empty

    fp = StringIO("[NetworkTables Storage 3.0]\nboolean \"foo\"=true\n")
    assert storage.loadPersistent(fp=fp) is None
    
    entry = storage.m_entries.get("foo")
    assert Value.makeBoolean(True) == entry.value
    assert NT_PERSISTENT == entry.flags

    assert 1 == len(outgoing)
    assert not outgoing[0].only
    assert not outgoing[0].conn
    msg = outgoing[0].msg
    assert kEntryAssign == msg.type
    assert "foo" == msg.str
    if is_server:
        assert 0 == msg.id    # assigned as server

    else:
        assert 0xffff == msg.id    # not assigned as client

    assert 1 == msg.seq_num_uid
    assert Value.makeBoolean(True) == msg.value
    assert NT_PERSISTENT == msg.flags


def test_LoadPersistentUpdateFlags(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    fp = StringIO("[NetworkTables Storage 3.0]\ndouble \"foo2\"=0.0\n")
    assert storage.loadPersistent(fp=fp) is None
    
    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(0.0) == entry.value
    assert NT_PERSISTENT == entry.flags

    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kFlagsUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert NT_PERSISTENT == msg.flags

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0



def test_LoadPersistentUpdateValue(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    storage.m_entries.get("foo2").flags = NT_PERSISTENT

    fp = StringIO("[NetworkTables Storage 3.0]\ndouble \"foo2\"=1.0\n")
    assert storage.loadPersistent(fp=fp) is None
    
    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(1.0) == entry.value
    assert NT_PERSISTENT == entry.flags

    if is_server:
        assert 1 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kEntryUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert 2 == msg.seq_num_uid  # incremented
        assert Value.makeDouble(1.0) == msg.value

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented



def test_LoadPersistentUpdateValueFlags(storage_populated, outgoing, is_server):
    storage = storage_populated
    
    fp = StringIO("[NetworkTables Storage 3.0]\ndouble \"foo2\"=1.0\n")
    assert storage.loadPersistent(fp=fp) is None
    
    entry = storage.m_entries.get("foo2")
    assert Value.makeDouble(1.0) == entry.value
    assert NT_PERSISTENT == entry.flags

    if is_server:
        assert 2 == len(outgoing)
        assert not outgoing[0].only
        assert not outgoing[0].conn
        msg = outgoing[0].msg
        assert kEntryUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert 2 == msg.seq_num_uid  # incremented
        assert Value.makeDouble(1.0) == msg.value

        assert not outgoing[1].only
        assert not outgoing[1].conn
        msg = outgoing[1].msg
        assert kFlagsUpdate == msg.type
        assert 1 == msg.id  # assigned as server
        assert NT_PERSISTENT == msg.flags

    else:
        # shouldn't send an update id not assigned yet (happens on client only)
        assert len(outgoing) == 0
        assert 2 == storage.m_entries.get("foo2").seq_num  # still should be incremented



def test_loadPersistent(storage_empty, outgoing):
    storage = storage_empty
    
    inp = "[NetworkTables Storage 3.0]\n"
    inp += "boolean \"\\x00\\x03\\x05\\n\"=true\n"
    inp += "boolean \"boolean/false\"=false\n"
    inp += "boolean \"boolean/true\"=true\n"
    inp += "array boolean \"booleanarr/empty\"=\n"
    inp += "array boolean \"booleanarr/one\"=true\n"
    inp += "array boolean \"booleanarr/two\"=true,false\n"
    inp += "double \"double/big\"=1.3e+08\n"
    inp += "double \"double/neg\"=-1.5\n"
    inp += "double \"double/zero\"=0\n"
    inp += "array double \"doublearr/empty\"=\n"
    inp += "array double \"doublearr/one\"=0.5\n"
    inp += "array double \"doublearr/two\"=0.5,-0.25\n"
    inp += "raw \"raw/empty\"=\n"
    inp += "raw \"raw/normal\"=aGVsbG8=\n"
    inp += "raw \"raw/special\"=AAMFCg==\n"
    inp += "string \"string/empty\"=\"\"\n"
    inp += "string \"string/normal\"=\"hello\"\n"
    inp += "string \"string/special\"=\"\\x00\\x03\\x05\\n\"\n"
    inp += "array string \"stringarr/empty\"=\n"
    inp += "array string \"stringarr/one\"=\"hello\"\n"
    inp += "array string \"stringarr/two\"=\"hello\",\"world\\n\"\n"

    fp = StringIO(inp)
    assert storage.loadPersistent(fp=fp) is None
    
    assert 21 == len(storage.m_entries)
    assert 21 == len(outgoing)

    assert Value.makeBoolean(True) == storage.getEntryValue("boolean/true")
    assert Value.makeBoolean(False) == storage.getEntryValue("boolean/false")
    assert Value.makeDouble(-1.5) == storage.getEntryValue("double/neg")
    assert Value.makeDouble(0.0) == storage.getEntryValue("double/zero")
    assert Value.makeDouble(1.3e8) == storage.getEntryValue("double/big")
    assert Value.makeString("") == storage.getEntryValue("string/empty")
    assert Value.makeString("hello") == storage.getEntryValue("string/normal")
    assert Value.makeString("\0\3\5\n") == storage.getEntryValue("string/special")
    assert Value.makeRaw(b"") == storage.getEntryValue("raw/empty")
    assert Value.makeRaw(b"hello") == storage.getEntryValue("raw/normal")
    assert Value.makeRaw(b"\0\3\5\n") == storage.getEntryValue("raw/special")
    assert Value.makeBooleanArray([]) == storage.getEntryValue("booleanarr/empty")
    assert Value.makeBooleanArray([True]) == storage.getEntryValue("booleanarr/one")
    assert Value.makeBooleanArray([True, False]) == storage.getEntryValue("booleanarr/two")
    assert Value.makeDoubleArray([]) == storage.getEntryValue("doublearr/empty")
    assert Value.makeDoubleArray([0.5]) == storage.getEntryValue("doublearr/one")
    assert Value.makeDoubleArray([0.5, -0.25]) == storage.getEntryValue("doublearr/two")
    assert Value.makeStringArray([]) == storage.getEntryValue("stringarr/empty")
    assert Value.makeStringArray(["hello"]) == storage.getEntryValue("stringarr/one")
    assert Value.makeStringArray(["hello", "world\n"]) == storage.getEntryValue("stringarr/two")
    assert Value.makeBoolean(True) == storage.getEntryValue("\0\3\5\n")


def test_LoadPersistentWarn(storage_empty, outgoing):
    storage = storage_empty
    
    fp = StringIO("[NetworkTables Storage 3.0]\nboolean \"foo\"=foo\n")
    
    #EXPECT_CALL(warn,
    #            Warn(2, llvm.StringRef("unrecognized boolean value, not 'True' or 'False'")))
    assert storage.loadPersistent(fp=fp) is None

    assert len(storage.m_entries) == 0
    assert len(storage.m_idmap) == 0
    assert len(outgoing) == 0



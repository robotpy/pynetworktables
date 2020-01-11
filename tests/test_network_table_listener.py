#
# These tests are leftover from the original pynetworktables tests
#

from unittest.mock import call, Mock
import pytest

from _pynetworktables import NetworkTables


@pytest.fixture(scope="function")
def table1(nt):
    return nt.getTable("/test1")


@pytest.fixture(scope="function")
def table2(nt):
    return nt.getTable("/test2")


@pytest.fixture(scope="function")
def table3(nt):
    return nt.getTable("/test3")


@pytest.fixture(scope="function")
def subtable1(nt):
    return nt.getTable("/test2/sub1")


@pytest.fixture(scope="function")
def subtable2(nt):
    return nt.getTable("/test2/sub2")


@pytest.fixture(scope="function")
def subtable3(nt):
    return nt.getTable("/test3/suba")


@pytest.fixture(scope="function")
def subtable4(nt):
    return nt.getTable("/test3/suba/subb")


def test_key_listener_immediate_notify(table1, nt_flush):

    listener1 = Mock()

    table1.putBoolean("MyKey1", True)
    table1.putBoolean("MyKey1", False)
    table1.putBoolean("MyKey2", True)
    table1.putBoolean("MyKey4", False)
    nt_flush()

    table1.addEntryListener(listener1.valueChanged, True, localNotify=True)

    nt_flush()
    listener1.valueChanged.assert_has_calls(
        [
            call(table1, "MyKey1", False, True),
            call(table1, "MyKey2", True, True),
            call(table1, "MyKey4", False, True),
        ],
        True,
    )
    assert len(listener1.mock_calls) == 3
    listener1.reset_mock()

    table1.putBoolean("MyKey", False)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey", False, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey1", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey1", False)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", False, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey4", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey4", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()


def test_key_listener_not_immediate_notify(table1, nt_flush):

    listener1 = Mock()

    table1.putBoolean("MyKey1", True)
    table1.putBoolean("MyKey1", False)
    table1.putBoolean("MyKey2", True)
    table1.putBoolean("MyKey4", False)

    table1.addEntryListener(listener1.valueChanged, False, localNotify=True)
    assert len(listener1.mock_calls) == 0
    listener1.reset_mock()

    table1.putBoolean("MyKey", False)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey", False, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey1", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey1", False)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", False, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey4", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey4", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()


def test_specific_key_listener(table1, nt_flush):

    listener1 = Mock()

    table1.addEntryListener(
        listener1.valueChanged, False, key="MyKey1", localNotify=True
    )
    nt_flush()
    assert len(listener1.mock_calls) == 0

    table1.putBoolean("MyKey1", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey2", True)
    nt_flush()
    assert len(listener1.mock_calls) == 0


def test_specific_entry_listener(table1, nt_flush):

    listener1 = Mock()
    NotifyFlags = NetworkTables.NotifyFlags

    entry = table1.getEntry("MyKey1")
    entry.addListener(
        listener1.valueChanged, NotifyFlags.NEW | NotifyFlags.UPDATE | NotifyFlags.LOCAL
    )
    nt_flush()
    assert len(listener1.mock_calls) == 0

    table1.putBoolean("MyKey1", True)
    nt_flush()
    listener1.valueChanged.assert_called_once_with(entry, "/test1/MyKey1", True, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    table1.putBoolean("MyKey2", True)
    nt_flush()
    assert len(listener1.mock_calls) == 0


def test_subtable_listener(table2, subtable1, subtable2, nt_flush):

    listener1 = Mock()

    table2.putBoolean("MyKey1", True)
    table2.putBoolean("MyKey1", False)
    table2.addSubTableListener(listener1.valueChanged, localNotify=True)
    table2.putBoolean("MyKey2", True)
    table2.putBoolean("MyKey4", False)

    subtable1.putBoolean("MyKey1", False)

    nt_flush()
    listener1.valueChanged.assert_called_once_with(table2, "sub1", subtable1, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    subtable1.putBoolean("MyKey2", True)
    subtable1.putBoolean("MyKey1", True)
    subtable2.putBoolean("MyKey1", False)

    nt_flush()
    listener1.valueChanged.assert_called_once_with(table2, "sub2", subtable2, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()


def test_subsubtable_listener(table3, subtable3, subtable4, nt_flush):
    listener1 = Mock()

    table3.addSubTableListener(listener1.valueChanged, localNotify=True)
    subtable3.addSubTableListener(listener1.valueChanged, localNotify=True)
    subtable4.addEntryListener(listener1.valueChanged, True, localNotify=True)

    subtable4.putBoolean("MyKey1", False)

    nt_flush()
    listener1.valueChanged.assert_has_calls(
        [
            call(table3, "suba", subtable3, True),
            call(subtable3, "subb", subtable4, True),
            call(subtable4, "MyKey1", False, True),
        ],
        True,
    )
    assert len(listener1.mock_calls) == 3
    listener1.reset_mock()

    subtable4.putBoolean("MyKey1", True)

    nt_flush()
    listener1.valueChanged.assert_called_once_with(subtable4, "MyKey1", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()

    listener2 = Mock()

    table3.addSubTableListener(listener2.valueChanged, localNotify=True)
    subtable3.addSubTableListener(listener2.valueChanged, localNotify=True)
    subtable4.addEntryListener(listener2.valueChanged, True, localNotify=True)

    nt_flush()
    listener2.valueChanged.assert_has_calls(
        [
            call(table3, "suba", subtable3, True),
            call(subtable3, "subb", subtable4, True),
            call(subtable4, "MyKey1", True, True),
        ],
        True,
    )
    assert len(listener1.mock_calls) == 0
    assert len(listener2.mock_calls) == 3
    listener2.reset_mock()


def test_global_listener(nt, nt_flush, table1, subtable3):
    listener = Mock()

    nt.addEntryListener(listener)
    listener.assert_not_called()

    table1.putString("t1", "hi")
    subtable3.putString("tt", "y0")
    nt_flush()
    listener.assert_has_calls(
        [call("/test1/t1", "hi", True), call("/test3/suba/tt", "y0", True)]
    )
    listener.reset_mock()

    nt.removeEntryListener(listener)

    table1.putString("s", "1")
    nt_flush()
    listener.assert_not_called()

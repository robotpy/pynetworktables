import pytest
import networktables

try:
    from unittest.mock import call, Mock
except ImportError:
    from mock import call, Mock

class NullStreamFactory:
    def createStream(self):
        return None

@pytest.fixture(scope='function')
def client():
    return networktables.NetworkTableClient(NullStreamFactory())

@pytest.fixture(scope='function')
def provider(client):
    return networktables.NetworkTableProvider(client)

@pytest.fixture(scope='function')
def table1(provider):
    return provider.getTable('/test1')
    
@pytest.fixture(scope='function')
def table2(provider):
    return provider.getTable('/test2')

@pytest.fixture(scope='function')
def table3(provider):
    return provider.getTable('/test3')

@pytest.fixture(scope='function')
def subtable1(provider):
    return provider.getTable('/test2/sub1')
    
@pytest.fixture(scope='function')
def subtable2(provider):
    return provider.getTable('/test2/sub2')

@pytest.fixture(scope='function')
def subtable3(provider):
    return provider.getTable('/test3/suba')
    
@pytest.fixture(scope='function')
def subtable4(provider):
    return provider.getTable('/test3/suba/subb')

def test_key_listener_immediate_notify(table1):
    
    listener1 = Mock()
    
    table1.putBoolean("MyKey1", True)
    table1.putBoolean("MyKey1", False)
    table1.putBoolean("MyKey2", True)
    table1.putBoolean("MyKey4", False)
    
    table1.addTableListener(listener1.valueChanged, True)
    
    listener1.valueChanged.assert_has_calls([
        call(table1, "MyKey1", False, True),
        call(table1, "MyKey2", True, True),
        call(table1, "MyKey4", False, True),
    ], True)
    assert len(listener1.mock_calls) == 3
    listener1.reset_mock()
    
    table1.putBoolean("MyKey", False)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey", False, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey1", True)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey1", False)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", False, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey4", True)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey4", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
def test_key_listener_not_immediate_notify(table1):
    
    listener1 = Mock()
    
    table1.putBoolean("MyKey1", True)
    table1.putBoolean("MyKey1", False)
    table1.putBoolean("MyKey2", True)
    table1.putBoolean("MyKey4", False)
    
    table1.addTableListener(listener1.valueChanged, False)
    assert len(listener1.mock_calls) == 0
    listener1.reset_mock()
    
    table1.putBoolean("MyKey", False)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey", False, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey1", True)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey1", False)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", False, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean("MyKey4", True)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey4", True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
def test_specific_key_listener(table1):
    
    listener1 = Mock()
    
    table1.addTableListener(listener1.valueChanged, False, key='MyKey1')
    
    table1.putBoolean('MyKey1', True)
    listener1.valueChanged.assert_called_once_with(table1, "MyKey1", True, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    table1.putBoolean('MyKey2', True)
    assert len(listener1.mock_calls) == 0
    
    
    
def test_subtable_listener(table2, subtable1, subtable2):
    
    listener1 = Mock()
    
    table2.putBoolean("MyKey1", True)
    table2.putBoolean("MyKey1", False)
    table2.addSubTableListener(listener1.valueChanged)
    table2.putBoolean("MyKey2", True)
    table2.putBoolean("MyKey4", False)

    subtable1.putBoolean("MyKey1", False)
    listener1.valueChanged.assert_called_once_with(table2, "sub1", subtable1, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    subtable1.putBoolean("MyKey2", True)
    subtable1.putBoolean("MyKey1", True)
    
    subtable2.putBoolean('MyKey1', False)
    listener1.valueChanged.assert_called_once_with(table2, "sub2", subtable2, True)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    
def test_subsubtable_listener(table3, subtable3, subtable4):
    listener1 = Mock()
    
    table3.addSubTableListener(listener1.valueChanged)
    subtable3.addSubTableListener(listener1.valueChanged)
    subtable4.addTableListener(listener1.valueChanged, True)
    
    subtable4.putBoolean('MyKey1', False)
    listener1.valueChanged.assert_has_calls([
        call(table3, 'suba', subtable3, True),
        call(subtable3, 'subb', subtable4, True),
        call(subtable4, 'MyKey1', False, True)
    ], True)
    assert len(listener1.mock_calls) == 3
    listener1.reset_mock()
    
    subtable4.putBoolean('MyKey1', True)
    listener1.valueChanged.assert_called_once_with(subtable4, 'MyKey1', True, False)
    assert len(listener1.mock_calls) == 1
    listener1.reset_mock()
    
    listener2 = Mock()
    
    table3.addSubTableListener(listener2.valueChanged)
    subtable3.addSubTableListener(listener2.valueChanged)
    subtable4.addTableListener(listener2.valueChanged, True)
    
    listener2.valueChanged.assert_has_calls([
        call(table3, 'suba', subtable3, True),
        call(subtable3, 'subb', subtable4, True),
        call(subtable4, 'MyKey1', True, True)
    ], True)
    assert len(listener1.mock_calls) == 0
    assert len(listener2.mock_calls) == 3
    listener2.reset_mock()
    
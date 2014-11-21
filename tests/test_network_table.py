
import pytest
import networktables

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


def test_put_double(table1):
    
    table1.putNumber('double', 42.42)
    assert table1.getNumber('double') == 42.42
    
    with pytest.raises(KeyError):
        table1.getNumber('Non-Existant')
        
    assert table1.getNumber('Non-Existant', 44.44) == 44.44

def test_put_boolean(table1):
    
    table1.putBoolean('boolean', True)
    assert table1.getBoolean('boolean') == True
    
    with pytest.raises(KeyError):
        table1.getBoolean('Non-Existant')
        
    assert table1.getBoolean('Non-Existant', False) == False
    
def test_put_string(table1):
        
    table1.putString('String', 'Test 1')
    assert table1.getString('String') == 'Test 1'
    
    with pytest.raises(KeyError):
        table1.getString('Non-Existant')
        
    assert table1.getString('Non-Existant', 'Test 3') == 'Test 3'

def test_multi_data_type(table1):
    
    table1.putNumber('double1', 1)
    table1.putNumber('double2', 2)
    table1.putNumber('double3', 3)
    table1.putBoolean('bool1', False)
    table1.putBoolean('bool2', True)
    table1.putString('string1', 'String 1')
    table1.putString('string2', 'String 2')
    table1.putString('string3', 'String 3')
    
    assert table1.getNumber('double1') == 1
    assert table1.getNumber('double2') == 2
    assert table1.getNumber('double3') == 3
    assert table1.getBoolean('bool1') == False
    assert table1.getBoolean('bool2') == True
    assert table1.getString('string1') == 'String 1'
    assert table1.getString('string2') == 'String 2'
    assert table1.getString('string3') == 'String 3'
    
    table1.putNumber('double1', 4)
    table1.putNumber('double2', 5)
    table1.putNumber('double3', 6)
    table1.putBoolean('bool1', True)
    table1.putBoolean('bool2', False)
    table1.putString('string1', 'String 4')
    table1.putString('string2', 'String 5')
    table1.putString('string3', 'String 6')
    
    assert table1.getNumber('double1') == 4
    assert table1.getNumber('double2') == 5
    assert table1.getNumber('double3') == 6
    assert table1.getBoolean('bool1') == True
    assert table1.getBoolean('bool2') == False
    assert table1.getString('string1') == 'String 4'
    assert table1.getString('string2') == 'String 5'
    assert table1.getString('string3') == 'String 6'

def test_multi_table(table1, table2):
    
    table1.putNumber('table1double', 1)
    table1.putBoolean('table1boolean', True)
    table1.putString('table1string', 'Table 1')
    
    with pytest.raises(KeyError):
        table2.getNumber('table1double')
    with pytest.raises(KeyError):
        table2.getBoolean('table1boolean')
    with pytest.raises(KeyError):
        table2.getString('table1string')
        
    table2.putNumber('table2double', 2)
    table2.putBoolean('table2boolean', False)
    table2.putString('table2string', 'Table 2')
    
    with pytest.raises(KeyError):
        table1.getNumber('table2double')
    with pytest.raises(KeyError):
        table1.getBoolean('table2boolean')
    with pytest.raises(KeyError):
        table1.getString('table2string')

def test_get_table(provider, table1, table2):
    assert provider.getTable('/test1') is table1
    assert provider.getTable('/test2') is table2
    
    assert table1 is not table2

    table3 = provider.getTable('/test3')
    assert table1 is not table3
    assert table2 is not table3

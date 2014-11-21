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

@pytest.fixture(scope='function')
def table3(provider):
    return provider.getTable('/test3')

@pytest.fixture(scope='function')
def subtable1(provider):
    return provider.getTable('/test2/sub1')
    
@pytest.fixture(scope='function')
def subtable2(provider):
    return provider.getTable('/test2/sub2')
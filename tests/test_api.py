#
# These tests stand up a separate client and server instance of 
# networktables and tests the 'real' user API to ensure that it
# works correctly
#

from __future__ import print_function

from contextlib import contextmanager
import pytest

from networktables import NetworkTables
from ntcore.support.compat import monotonic

import threading

import logging
logger = logging.getLogger('nt.test')

class NtTestBase(NetworkTables):
    
    _wait_lock = threading.Condition()
    
    @classmethod
    def _init_common(cls, proto_rev):
        # This resets the instance to be independent
        cls.shutdown()
        cls._api.dispatcher.setDefaultProtoRev(proto_rev)
        cls.proto_rev = proto_rev
        
        cls.enableVerboseLogging()
        cls._wait_init()
    
    @classmethod
    def _init_server(cls, proto_rev, server_port=0):
        cls._init_common(proto_rev)
        
        cls.port = server_port
        cls._serverListenAddress = '127.0.0.1'
        cls.initialize()
        
        assert cls._api.dispatcher.m_server_acceptor.waitForStart(timeout=1)
        cls.port = cls._api.dispatcher.m_server_acceptor.m_port
    
    @classmethod
    def _init_client(cls, server, proto_rev):
        cls._init_common(proto_rev)
        
        cls.setPort(server.port)
        cls.initialize(server='127.0.0.1')
    
    @classmethod
    def _wait_init(cls):
        cls._wait = 0
        
        cls._api.addEntryListener('', cls._wait_cb, 
                                  NetworkTables.NotifyFlags.NEW |
                                  NetworkTables.NotifyFlags.UPDATE |
                                  NetworkTables.NotifyFlags.DELETE |
                                  NetworkTables.NotifyFlags.FLAGS)
    
    @classmethod
    def _wait_cb(cls, *args):
        with cls._wait_lock:
            cls._wait += 1
            cls._wait_lock.notify()
    
    
    @classmethod
    @contextmanager
    def expect_changes(cls, count):
        '''Use this on the *other* instance that you're making 
        changes on, to wait for the changes to propagate to the
        other instance'''
        
        with cls._wait_lock:
            cls._wait = 0
        
        logger.info("Begin actions")
        yield
        logger.info("Waiting for %s changes", count)
        
        with cls._wait_lock:
            wait_until = monotonic() + 1
            while cls._wait != count:
                cls._wait_lock.wait(1)
                if monotonic() > wait_until:
                    assert False, "Timeout waiting for %s changes (got %s)" % (count, cls._wait)

# Each test should cover each NT version combination
# 0x0200 -> 0x0300
# 0x0300 -> 0x0200
# 0x0300 -> 0x0300

@pytest.fixture(params=[
    0x0200, 0x0300
])
def nt_server(request):
    
    class NtServer(NtTestBase):
        pass
    
    NtServer._init_server(request.param)
    yield NtServer
    NtServer.shutdown()

@pytest.fixture(params=[
    0x0200, 0x0300
])
def nt_client(request, nt_server):
    
    class NtClient(NtTestBase):
        pass
    
    NtClient._init_client(nt_server, request.param)
    yield NtClient
    NtClient.shutdown()


# test defaults
def doc(nt):
    t = nt.getTable('nope')
    
    with pytest.raises(KeyError):
        t.getBoolean('b')
    
    with pytest.raises(KeyError):
        t.getNumber('n')
        
    with pytest.raises(KeyError):
        t.getString('s')
    
    with pytest.raises(KeyError):
        t.getBooleanArray('ba')
    
    with pytest.raises(KeyError):
        t.getNumberArray('na')
        
    with pytest.raises(KeyError):
        t.getStringArray('sa')
        
    with pytest.raises(KeyError):
        t.getValue('v')
    
    assert t.getBoolean('b', True) is True
    assert t.getNumber('n', 1) == 1
    assert t.getString('s', 'sss') == 'sss'
    assert t.getBooleanArray('ba', (True,)) == (True,)
    assert t.getNumberArray('na', (1,)) == (1,)
    assert t.getStringArray('sa', ('ss',)) == ('ss',)
    assert t.getValue('v', 'vvv') == 'vvv'

def do(nt1, nt2, t):
        
    t1 = nt1.getTable(t)
    with nt2.expect_changes(7):
        t1.putBoolean('bool', True)
        t1.putNumber('number1', 1)
        t1.putNumber('number2', 1.5)
        t1.putString('string', 'string')
        t1.putBooleanArray('ba', (True, False))
        t1.putNumberArray('na', (1, 2))
        t1.putStringArray('sa', ('s', 't'))
    
    t2 = nt2.getTable(t)
    assert t2.getBoolean('bool') is True
    assert t2.getNumber('number1') == 1
    assert t2.getNumber('number2') == 1.5
    assert t2.getString('string') == 'string'
    assert t2.getBooleanArray('ba') == (True, False) 
    assert t2.getNumberArray('na') == (1, 2)
    assert t2.getStringArray('sa') == ('s', 't')
    
    # Value testing
    with nt2.expect_changes(5):
        t1.putValue('v_b', False)
        t1.putValue('v_n1', 2)
        t1.putValue('v_n2', 2.5)
        t1.putValue('v_s', 'ssss')
        
        t1.putValue('v_v', 0)
        
    print(t2.getKeys())
    assert t2.getBoolean('v_b') is False
    assert t2.getNumber('v_n1') == 2
    assert t2.getNumber('v_n2') == 2.5
    assert t2.getString('v_s') == 'ssss'
    assert t2.getValue('v_v') == 0
    
    # Ensure that updating values work!
    with nt2.expect_changes(7):
        t1.putBoolean('bool', False)
        t1.putNumber('number1', 2)
        t1.putNumber('number2', 2.5)
        t1.putString('string', 'sss')
        t1.putBooleanArray('ba', (False, True, False))
        t1.putNumberArray('na', (2, 1))
        t1.putStringArray('sa', ('t', 's'))
    
    t2 = nt2.getTable(t)
    assert t2.getBoolean('bool') is False
    assert t2.getNumber('number1') == 2
    assert t2.getNumber('number2') == 2.5
    assert t2.getString('string') == 'sss'
    assert t2.getBooleanArray('ba') == (False, True, False) 
    assert t2.getNumberArray('na') == (2, 1)
    assert t2.getStringArray('sa') == ('t', 's')
    
    # Try out deletes -- but NT2 doesn't support them
    if nt2.proto_rev == 0x0300:
        if nt1.proto_rev == 0x0300:
            with nt2.expect_changes(1):
                t1.delete('bool')
                
            with pytest.raises(KeyError):
                t2.getBoolean('bool')
        else:
            t1.delete('bool')
            
            with nt2.expect_changes(1):
                t1.putBoolean('ooo', True)
                
            assert t2.getBoolean('bool') is False
            
    else:
        t1.delete('bool')
        
        with nt2.expect_changes(1):
            t1.putBoolean('ooo', True)
                
        assert t2.getBoolean('bool') is False


def test_basic(nt_client, nt_server):
    
    assert nt_server.isServer()
    assert not nt_client.isServer()
        
    doc(nt_client)
    doc(nt_server)
    
    # server -> client
    do(nt_server, nt_client, 'server2client')
    
    # client -> server
    do(nt_client, nt_server, 'client2server')

    assert nt_client.isConnected()
    assert nt_server.isConnected()
    

def test_reconnect(nt_client, nt_server):
    
    server_port = nt_server.port
    
    with nt_server.expect_changes(1):
        ct = nt_client.getTable('t')
        ct.putBoolean('foo', True)
        
    st = nt_server.getTable('t')
    assert st.getBoolean('foo') == True
    
    # Client disconnect testing
    nt_client.shutdown()
    
    with nt_client.expect_changes(1):
        nt_client._init_client(nt_server, nt_client.proto_rev)
        ct = nt_client.getTable('t')
        
    assert ct.getBoolean('foo') == True
    
    # Server disconnect testing
    nt_server.shutdown()
    
    with nt_server.expect_changes(1):
        nt_server._init_server(nt_server.proto_rev, server_port)
        
    st = nt_server.getTable('t')
    assert st.getBoolean('foo') == True


    
    

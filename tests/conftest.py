
#
# Useful fixtures
#

from contextlib import contextmanager

log_datefmt = "%H:%M:%S"
log_format = "%(asctime)s:%(msecs)03d %(levelname)-8s: %(name)-8s: %(message)s"

import logging
logging.basicConfig(level=logging.DEBUG, format=log_format, datefmt=log_datefmt)


logger = logging.getLogger('conftest')

import pytest

from networktables import NetworkTables
from ntcore.support.compat import Condition

#
# Fixtures for a usable in-memory version of networktables
#

@pytest.fixture(scope='function', params=[True, False])
def nt(request):
    '''Starts/stops global networktables instance for testing'''
    NetworkTables.setTestMode(server=request.param)
    NetworkTables.initialize()
    
    yield NetworkTables
    
    NetworkTables.shutdown()


@pytest.fixture(scope='function')
def entry_notifier(nt):
    return nt._api.entry_notifier

@pytest.fixture(scope='function')
def conn_notifier(nt):
    return nt._api.conn_notifier

@pytest.fixture(scope='function')
def nt_flush(nt):
    '''Flushes NT key notifications'''
    
    def _flush():
        assert nt._api.waitForEntryListenerQueue(1.0)
        assert nt._api.waitForConnectionListenerQueue(1.0)
        
    return _flush


#
# Live NT instance fixtures
#

class NtTestBase(NetworkTables):
    '''
        Object for managing a live pair of NT server/client
    '''
    
    _wait_lock = None
    
    @classmethod
    def _init_common(cls, proto_rev):
        # This resets the instance to be independent
        cls.shutdown()
        cls._api.dispatcher.setDefaultProtoRev(proto_rev)
        cls.proto_rev = proto_rev
        
        cls.enableVerboseLogging()
        #cls._wait_init()
    
    @classmethod
    def _init_server(cls, proto_rev, server_port=0):
        cls._init_common(proto_rev)
        
        cls.port = server_port
        cls._serverListenAddress = '127.0.0.1'
        
    
    @classmethod
    def _init_client(cls, proto_rev):
        cls._init_common(proto_rev)
    
    @classmethod
    def _wait_init(cls):
        cls._wait_lock = Condition()
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
            #logger.info('Wait callback, got: %s', args)
            cls._wait_lock.notify()
    
    
    @classmethod
    @contextmanager
    def expect_changes(cls, count):
        '''Use this on the *other* instance that you're making 
        changes on, to wait for the changes to propagate to the
        other instance'''
        
        if cls._wait_lock is None:
            cls._wait_init()
        
        with cls._wait_lock:
            cls._wait = 0
        
        logger.info("Begin actions")
        yield
        logger.info("Waiting for %s changes", count)
        
        with cls._wait_lock:
            result = cls._wait_lock.wait_for(lambda: cls._wait == count, 4), \
                  "Timeout waiting for %s changes (got %s)" % (count, cls._wait)
            logger.info("expect_changes: %s", result)
            assert result

# Each test should cover each NT version combination
# 0x0200 -> 0x0300
# 0x0300 -> 0x0200
# 0x0300 -> 0x0300

@pytest.fixture(params=[
    0x0200, 0x0300
])
def nt_server(request):
    
    class NtServer(NtTestBase):
        
        _test_saved_port = None
        
        @classmethod
        def start_test(cls):
            # Restore server port on restart
            if cls._test_saved_port is not None:
                cls.port = cls._test_saved_port
                cls._api.dispatcher.setDefaultProtoRev(request.param)
            
            cls.initialize()
            
            assert cls._api.dispatcher.m_server_acceptor.waitForStart(timeout=1)
            cls.port = cls._api.dispatcher.m_server_acceptor.m_port
            cls._test_saved_port = cls.port
    
    NtServer._init_server(request.param)
    yield NtServer
    NtServer.shutdown()

@pytest.fixture(params=[
    0x0200, 0x0300
])
def nt_client(request, nt_server):
    
    class NtClient(NtTestBase):
        @classmethod
        def start_test(cls):
            cls._api.dispatcher.setDefaultProtoRev(request.param)
            cls.setPort(nt_server.port)
            cls.initialize(server='127.0.0.1')
    
    NtClient._init_client(request.param)
    yield NtClient
    NtClient.shutdown()

@pytest.fixture
def nt_live(nt_server, nt_client):
    '''This fixture automatically starts the client and server'''
    
    nt_server.start_test()
    nt_client.start_test()
    
    return nt_server, nt_client
    

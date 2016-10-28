
#
# Useful fixtures
#

import threading

import logging
logging.basicConfig(level=logging.DEBUG)

import pytest

from networktables import NetworkTables

@pytest.fixture(scope='function', params=[True, False])
def nt(request):
    '''Starts/stops global networktables instance for testing'''
    NetworkTables.setTestMode(server=request.param)
    NetworkTables.initialize()
    
    yield NetworkTables
    
    NetworkTables.shutdown()


@pytest.fixture(scope='function')
def notifier(nt):
    return nt._api.notifier

@pytest.fixture(scope='function')
def nt_flush(notifier):
    '''Flushes NT key notifications'''
    
    # this reaches deep into the API to flush the notifier
    
    # replace the queue function
    tcond = threading.Condition()
    qcond = threading.Condition()
    
    q = notifier.m_notifications
    _get = q.get
    
    flushed = [None]
    
    def get():
        # notify the waiter
        while True:
            print("get?")
            if not q.empty():
                print("get")
                ret = _get()
                print ("->", ret)
                return ret
            
            with qcond:
                print("qnotify")
                flushed[0] = True
                qcond.notify()
        
            with tcond:
                print("twait")
                tcond.wait()
    
    q.get = get
    
    def flush():
        with qcond:
            with tcond:
                print("tnotify")
                tcond.notify()
            print("qwait")
            
            flushed[0] = False
            qcond.wait(1)
            
            if not flushed[0]:
                raise Exception("flush failed")
    
    yield flush
    
    # free the queue function
    q.get = _get

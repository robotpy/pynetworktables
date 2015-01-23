'''
    Tools for finding deadlocks in networktables
    
    Protocol notes:
    
    - Must not be holding a lock when making a network read/write
    - Must not be holding a lock when calling out to a listener?
        - Or detect such a deadlock?
    
'''

__all__ = ["create_rlock", 'sock_makefile']

import inspect
import threading
import time

def create_rlock():
    return threading.RLock()

def sock_makefile(s, mode):
    return s.makefile(mode)
    


# Call this before creating any NetworkTable objects
def enable_lock_debugging():
    
    rlocks_lock = threading.Lock()
    threads = {} # dict of lists, count of list is number of locks in this thread
    
    class WrappedLock(threading._PyRLock):
        
        def __init__(self):
            threading._PyRLock.__init__(self)
            
            curframe = inspect.currentframe()
            calframe = inspect.getouterframes(curframe, 3)
            self._nt_caller = '%s:%s %s' % (calframe[2][1], calframe[2][2], calframe[2][3])
        
        def acquire(self, blocking=True, timeout=-1):
            retval = threading._PyRLock.acquire(self, blocking=blocking, timeout=timeout)
            if retval != False:
                with rlocks_lock:
                    threads.setdefault(threading.current_thread(), []).append(self)
    
        __enter__ = acquire
    
        def release(self):
            threading._PyRLock.release(self)
            with rlocks_lock:
                threads[threading.current_thread()].remove(self)
    
    def create_tracked_rlock():
        return WrappedLock()
        
    def assert_not_locked(t):
        with rlocks_lock:
            
            locks = threads.get(threading.current_thread(), [])
            #print(locks)
            if len(locks) == 0:
                return
            
            assert_str = ','.join([lock._nt_caller for lock in locks])
            assert False, "ERROR: network %s was made while holding lock created at %s" % (t, assert_str)
    
    class WrappedFile:
        def __init__(self, file):
            self._file = file
            
        def write(self, data):
            print("W-HAHA")
            assert_not_locked('write')
            time.sleep(1)
            return self._file.write(data)
            
        def read(self, *args, **kwargs):
            print("R-HAHA")
            assert_not_locked('read')
            time.sleep(1)
            return self._file.read(*args, **kwargs)
            
            
        def __getattr__(self, attr):
            return getattr(self._file, attr)
    
    
    def blocking_sock_makefile(s, mode):
        return WrappedFile(s.makefile(mode))
    
    g = globals()
    g['create_rlock'] = create_tracked_rlock
    g['sock_makefile'] = blocking_sock_makefile



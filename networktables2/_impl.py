
__all__ = ["create_rlock", 'sock_makefile']

import threading

def create_rlock(name):
    return threading.RLock()

def sock_makefile(s, mode):
    return s.makefile(mode)


# Call this before creating any NetworkTable objects
def enable_lock_debugging():
    
    from . import _impl_debug
    
    g = globals()
    g['create_rlock'] = _impl_debug.create_tracked_rlock
    g['sock_makefile'] = _impl_debug.blocking_sock_makefile



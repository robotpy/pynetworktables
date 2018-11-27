# notrack

__all__ = ["create_rlock", "sock_makefile"]

import socket
import threading


def create_rlock(name):
    return threading.RLock()


def sock_makefile(s, mode):
    return s.makefile(mode)


def sock_create_connection(address):
    return socket.create_connection(address)


# Call this before creating any NetworkTable objects
def enable_lock_debugging(sock_block_period=None):

    from . import _impl_debug

    _impl_debug.sock_block_period = sock_block_period

    g = globals()
    g["create_rlock"] = _impl_debug.create_tracked_rlock
    g["sock_makefile"] = _impl_debug.blocking_sock_makefile
    g["sock_create_connection"] = _impl_debug.blocking_sock_create_connection

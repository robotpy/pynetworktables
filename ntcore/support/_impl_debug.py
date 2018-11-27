# notrack
"""
    Instrumentation for finding deadlocks in networktables
"""

from __future__ import print_function

import inspect
import socket
import threading
import time

# Number of seconds to block
sock_block_period = None

# List of locks that can be acquired from the main thread
main_locks = ["entry_lock", "trans_lock"]

# List of locks that are allowed to be held when accessing a socket
# -> must never be locks that can be acquired by the main thread
sock_locks = ["client_conn_lock", "server_conn_lock", "write_lock"]

# Dictionary of locks
# key: name, value: locks that can be held when acquiring the lock
locks = {
    # Never held by robot thread
    "client_conn_lock": ["client_conn_lock"],
    "entry_lock": ["entry_lock", "client_conn_lock"],
    # Never held by robot thread
    "server_conn_lock": ["server_conn_lock"],
    "trans_lock": [
        "entry_lock",
        # Not 100% sure if this should be allowed
        # -> this only happens when NetworkTable API calls are made from
        #    a fired listener
        "server_conn_lock",
        "client_conn_lock",
    ],
    # Never held by robot thread
    "write_lock": ["client_conn_lock", "server_conn_lock", "write_lock"],
}

local = threading.local()


class WrappedLock(threading._PyRLock):
    def __init__(self, name):
        threading._PyRLock.__init__(self)
        self._name = name
        self._nt_creator = _get_caller()

    def acquire(self, blocking=True, timeout=-1):

        # This check isn't strictly true..
        if isinstance(threading.current_thread(), threading._MainThread):
            assert self._name in main_locks, (
                "%s cannot be held in main thread" % self._name
            )

        if not hasattr(local, "held_locks"):
            local.held_locks = []

        for lock in local.held_locks:
            assert (
                lock in locks[self._name]
            ), "Cannot hold %s when trying to acquire %s" % (lock._name, self._name)

        retval = threading._PyRLock.acquire(self, blocking=blocking, timeout=timeout)
        if retval != False:
            local.held_locks.append(self)

    __enter__ = acquire

    def release(self):
        threading._PyRLock.release(self)
        assert local.held_locks[-1] == self
        local.held_locks.pop()

    # Allow this to be used in comparisons

    def __eq__(self, other):
        if isinstance(other, str):
            return self._name.__eq__(other)
        else:
            return self._name.__eq__(other._name)

    def __cmp__(self, other):
        if isinstance(other, str):
            return self._name.__cmp__(other)
        else:
            return self._name.__cmp__(other._name)

    def __hash__(self):
        return self._name.__hash__()


def create_tracked_rlock(name):
    assert name in locks
    return WrappedLock(name)


def assert_not_locked(t):

    assert not isinstance(
        threading.current_thread(), threading._MainThread
    ), "Should not make socket calls from main thread"

    if not hasattr(local, "held_locks"):
        local.held_locks = []

    for lock in local.held_locks:
        assert lock in sock_locks, "ERROR: network %s was made while holding %s" % (
            t,
            lock._name,
        )


class WrappedFile:
    def __init__(self, file):
        self._file = file

    def write(self, data):
        assert_not_locked("write")
        if sock_block_period:
            time.sleep(sock_block_period)
        return self._file.write(data)

    def read(self, *args, **kwargs):
        assert_not_locked("read")
        if sock_block_period:
            time.sleep(sock_block_period)
        return self._file.read(*args, **kwargs)

    def __getattr__(self, attr):
        return getattr(self._file, attr)


def blocking_sock_makefile(s, mode):
    return WrappedFile(s.makefile(mode))


def blocking_sock_create_connection(address):
    assert_not_locked("connect")
    if sock_block_period:
        time.sleep(sock_block_period)
    return socket.create_connection(address)


def _get_caller():
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 3)
    return "%s:%s %s" % (calframe[3][1], calframe[3][2], calframe[3][3])

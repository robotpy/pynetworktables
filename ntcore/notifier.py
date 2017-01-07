# validated: 2016-10-27 DS a73166a src/Notifier.cpp src/Notifier.h
'''----------------------------------------------------------------------------'''
''' Copyright (c) FIRST 2015. All Rights Reserved.                             '''
''' Open Source Software - may be modified and shared by FRC teams. The code   '''
''' must be accompanied by the FIRST BSD license file in the root directory of '''
''' the project.                                                               '''
'''----------------------------------------------------------------------------'''

from collections import namedtuple
import threading

from .constants import (
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS
)

from .support.compat import Queue

import logging
logger = logging.getLogger('nt')


_EntryCallback = namedtuple('EntryCallback', [
    'prefix',
    'callback',
    'flags'
])

_EntryNotification = namedtuple('EntryNotification', [
    'is_entry',
    'name',
    'value',
    'flags',
    'only'
])

_ConnectionNotification = namedtuple('ConnectionNotification', [
    'is_entry',
    'connected',
    'conn_info',
    'only'
])

class _Escape(Exception):
    pass


class UidVector(dict):
    
    def __init__(self):
        self.idx = 0
        self.lock = threading.Lock()
    
    def add(self, item):
        with self.lock:
            idx = self.idx
            self.idx += 1
        
        self[idx] = item
        return idx


_assign_both = NT_NOTIFY_UPDATE | NT_NOTIFY_FLAGS


class Notifier(object):

    def __init__(self, verbose=False):
        self.m_mutex = threading.Lock()
        
        self.m_verbose = verbose
        
        self.m_active = False
        self.m_owner = None
        
        self.m_local_notifiers = False
        self.m_local_entry_notifiers = False
        
        self.m_entry_listeners = UidVector()
        self.m_conn_listeners = set()
        
        # In python we don't need multiple queues
        self.m_notifications = Queue()
        
        self.m_on_start = None
        self.m_on_exit = None
        
        # Python specific: autoValue support
        self.m_autovalues = {}
        
    def setVerboseLogging(self, verbose):
        self.m_verbose = verbose
    
    def start(self):
        if not self.m_owner:
            self.m_active = True
            self.m_owner = threading.Thread(target=self._thread_main, name='notifier_thread')
            self.m_owner.daemon = True
            self.m_owner.start()
    
    def stop(self):
        if self.m_owner:
            self.m_active = False
            self.m_notifications.put(None)
            self.m_owner.join()
            self.m_owner = None
    
    def _thread_main(self):
        
        if self.m_on_start:
            self.m_on_start()
        
        try:
            while self.m_active:
                item = self.m_notifications.get()
                    
                if not self.m_active:
                    raise _Escape() # goto done
        
                # Entry notifications
                if item.is_entry:
        
                    if not item.value:
                        continue
                    
                    item_name = item.name
                    item_value = item.value.value
                    item_flags = item.flags
        
                    if item.only:
                        try:
                            # ntcore difference: no uid in callback
                            item.only(item_name, item_value, item_flags)
                        except Exception:
                            logger.warn("Unhandled exception processing notify callback", exc_info=True)
                        continue
                    
                    # Use copy because iterator might get invalidated.
                    for listener in list(self.m_entry_listeners.values()):
                        
                        # Flags must be within requested flag set for this listener.
                        # Because assign messages can result in both a value and flags update,
                        # we handle that case specially.
                        listen_flags = listener.flags
                        flags = item_flags
                        
                        if (flags & _assign_both) == _assign_both:
                            if (listen_flags & _assign_both) == 0:
                                continue
        
                            listen_flags &= ~_assign_both
                            flags &= ~_assign_both
        
                        if (flags & ~listen_flags) != 0:
                            continue
                        
                        # must match prefix
                        if not item_name.startswith(listener.prefix):
                            continue
                        
                        try:
                            # ntcore difference: no uid in callback
                            listener.callback(item_name, item_value, item_flags)
                        except Exception:
                            logger.warn("Unhandled exception processing notify callback", exc_info=True)
                
                # Connection notifications
                else:
                    if item.only:
                        try:
                            # ntcore difference: no uid in callback
                            item.only(item.connected, item.conn_info)
                        except Exception:
                            logger.warn("Unhandled exception processing notify callback", exc_info=True)
                        continue
                    
                    # Use copy because iterator might get invalidated.
                    for listener in list(self.m_conn_listeners):
                        try:
                            # ntcore difference: no uid in callback
                            listener(item.connected, item.conn_info)
                        except Exception:
                            logger.warn("Unhandled exception processing notify callback", exc_info=True)
        
        except _Escape:
            pass # because goto doesn't exist in python
        except Exception:
            logger.exception("Unhandled exception in notifier thread")
        
        logger.debug('Notifier thread exiting')
        
        if self.m_on_exit:
            self.m_on_exit()
    
    
    def addEntryListener(self, prefix, callback, flags):
        if self.m_verbose:
            logger.debug("%s entry listeners active", len(self.m_entry_listeners) + 1)
        
        self.start()
        if (flags & NT_NOTIFY_LOCAL) != 0:
            self.m_local_notifiers = True
            self.m_local_entry_notifiers = True
    
        return self.m_entry_listeners.add(_EntryCallback(prefix, callback, flags))
    
    def removeEntryListener(self, entry_listener_uid):
        try:
            del self.m_entry_listeners[entry_listener_uid]
        except KeyError:
            pass
        
    def createAutoValue(self, key, value):
        self.m_local_notifiers = True
        return self.m_autovalues.setdefault(key, value)
    
    def notifyEntry(self, name, value, flags, only=None):
        
        # Python-specific autovalue support
        vv = value.value
        if vv is not None:
            autovalue = self.m_autovalues.get(name)
            if autovalue is not None:
                autovalue._AutoUpdateValue__value = value.value
        
        # optimization: don't generate needless local queue entries if we have
        # no local listeners (as this is a common case on the server side)
        if not self.m_local_entry_notifiers and (flags & NT_NOTIFY_LOCAL) != 0:
            return
    
        if not self.m_owner:
            return
        
        self.m_notifications.put(_EntryNotification(True, name, value, flags, only))
    
    
    def addConnectionListener(self, callback):
        if self.m_verbose:
            logger.debug("%s connection listeners active", len(self.m_conn_listeners) + 1)
        
        self.start()
        self.m_conn_listeners.add(callback)
    
    def removeConnectionListener(self, callback):
        try:
            self.m_conn_listeners.remove(callback)
        except KeyError:
            pass
    
    def notifyConnection(self, connected, conn_info, only=None):
        if not self.m_owner:
            return
        
        self.m_notifications.put(_ConnectionNotification(False, connected, conn_info, only))

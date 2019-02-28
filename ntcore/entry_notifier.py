# validated: 2017-10-01 DS e4a8bff70e77 cpp/EntryNotifier.cpp cpp/EntryNotifier.h cpp/IEntryNotifier.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

from collections import namedtuple

from .callback_manager import CallbackManager, CallbackThread

from .constants import (
    NT_NOTIFY_IMMEDIATE,
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS,
)


_EntryListenerData = namedtuple(
    "EntryListenerData",
    [
        "prefix",
        "local_id",  # we don't have entry handles like ntcore has
        "flags",
        "callback",
        "poller_uid",
    ],
)

#
_EntryNotification = namedtuple(
    "EntryNotification", ["name", "value", "flags", "local_id"]
)

_assign_both = NT_NOTIFY_UPDATE | NT_NOTIFY_FLAGS
_immediate_local = NT_NOTIFY_IMMEDIATE | NT_NOTIFY_LOCAL


class EntryNotifierThread(CallbackThread):
    def __init__(self):
        CallbackThread.__init__(self, "entry-notifier")

    def matches(self, listener, data):
        if not data.value:
            return False

        # must match local id or prefix
        # -> python-specific: match this first, since it's the most likely thing
        #    to not match
        if listener.local_id is not None:
            if listener.local_id != data.local_id:
                return False
        else:
            if not data.name.startswith(listener.prefix):
                return False

        # Flags must be within requested flag set for this listener.
        # Because assign messages can result in both a value and flags update,
        # we handle that case specially.
        listen_flags = listener.flags & ~_immediate_local
        flags = data.flags & ~_immediate_local

        if (flags & _assign_both) == _assign_both:
            if (listen_flags & _assign_both) == 0:
                return False
            listen_flags &= ~_assign_both
            flags &= ~_assign_both

        if (flags & ~listen_flags) != 0:
            return False

        return True

    def setListener(self, data, listener_uid):
        pass

    def doCallback(self, callback, data):
        callback(data)


class EntryNotifier(CallbackManager):

    THREAD_CLASS = EntryNotifierThread

    def __init__(self, verbose):
        CallbackManager.__init__(self, verbose)

        self.m_local_notifiers = False

    def add(self, callback, prefix, flags):
        if (flags & NT_NOTIFY_LOCAL) != 0:
            self.m_local_notifiers = True
        return self.doAdd(_EntryListenerData(prefix, None, flags, callback, None))

    def addById(self, callback, local_id, flags):
        if (flags & NT_NOTIFY_LOCAL) != 0:
            self.m_local_notifiers = True
        return self.doAdd(_EntryListenerData(None, local_id, flags, callback, None))

    def addPolled(self, poller_uid, prefix, flags):
        if (flags & NT_NOTIFY_LOCAL) != 0:
            self.m_local_notifiers = True
        return self.doAdd(_EntryListenerData(prefix, None, flags, None, poller_uid))

    def addPolledById(self, poller_uid, local_id, flags):
        if (flags & NT_NOTIFY_LOCAL) != 0:
            self.m_local_notifiers = True
        return self.doAdd(_EntryListenerData(None, local_id, flags, None, poller_uid))

    def notifyEntry(self, local_id, name, value, flags, only_listener=None):

        # optimization: don't generate needless local queue entries if we have
        # no local listeners (as this is a common case on the server side)
        if not self.m_local_notifiers and (flags & NT_NOTIFY_LOCAL) != 0:
            return

        self.send(only_listener, _EntryNotification(name, value, flags, local_id))

    def start(self):
        CallbackManager.start(self)

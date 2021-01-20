# validated: 2019-02-26 DS 0e1f9c2ed271 cpp/Storage.cpp cpp/Storage.h cpp/Storage_load.cpp cpp/Storage_save.cpp
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

import os
import threading
from time import monotonic

from .message import Message
from .network_connection import NetworkConnection
from .storage_load import load_entries
from .storage_save import save_entries
from .structs import EntryInfo, ConnectionInfo
from .value import Value

from .support.lists import ensure_id_exists

from .constants import (
    kEntryAssign,
    kEntryUpdate,
    kFlagsUpdate,
    kEntryDelete,
    kClearEntries,
    kExecuteRpc,
    kRpcResponse,
    NT_UNASSIGNED,
    NT_PERSISTENT,
    NT_RPC,
    NT_NOTIFY_IMMEDIATE,
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_NEW,
    NT_NOTIFY_DELETE,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS,
)

import logging

logger = logging.getLogger("nt")


class _Entry(object):
    __slots__ = [
        "name",
        "value",
        "flags",
        "isPersistent",
        "id",
        "local_id",
        "seq_num",
        "local_write",
        "rpc_uid",
        "rpc_call_uid",
        "user_entry",
    ]

    def __init__(self, name, local_id, user_entry):

        # We redundantly store the name so that it's available when accessing the
        # raw Entry* via the ID map.
        self.name = name

        # The current value and flags.
        self.value = None
        self.flags = 0

        # Unique ID for self entry as used in network messages.  The value is
        # assigned by the server, on the client this is 0xffff until an
        # entry assignment is received back from the server.
        self.id = 0xFFFF

        # Local ID
        self.local_id = local_id

        # Sequence number for update resolution.
        self.seq_num = 0

        # If value has been written locally.  Used during initial handshake
        # on client to determine whether or not to accept remote changes.
        self.local_write = False

        # RPC handle
        self.rpc_uid = None

        # Last UID used when calling self RPC (primarily for client use).  This
        # is incremented for each call.
        self.rpc_call_uid = 0

        # python-specific: User-visible entry for optimized value retrieval
        # -> user_entry._value must always be set when self.value is set
        self.user_entry = user_entry

        # python-specific: this is checked often, so don't recompute it
        self.isPersistent = False

    # micro-optimizations: value is called all the time, so use its attributes
    # instead

    # @property
    # def value(self):
    #     return self._value

    # @value.setter
    # def value(self, value):
    #     self._value = value
    #     self.user_entry._value = value

    def increment_seqnum(self):
        self.seq_num += 1
        self.seq_num &= 0xFFFF

    def isSeqNewerThan(self, other):
        """
        self > other
        """
        seq_num = self.seq_num
        if seq_num < other:
            return (other - seq_num) > 32768
        elif seq_num > other:
            return (seq_num - other) < 32768
        else:
            return False

    def isSeqNewerOrEqual(self, other):
        """
        self >= other
        """
        seq_num = self.seq_num
        if seq_num < other:
            return (other - seq_num) > 32768
        elif seq_num > other:
            return (seq_num - other) < 32768
        else:
            return True

    def isRpc(self):
        return self.value.type == NT_RPC

    def __repr__(self):
        return "<_Entry name='%s' value=%s flags=%s id=%s local_id=%s seq_num=%s local_write=%s rpc_uid=%s rpc_call_uid=%s" % (
            self.name,
            self.value,
            self.flags,
            self.id,
            self.local_id,
            self.seq_num,
            self.local_write,
            self.rpc_uid,
            self.rpc_call_uid,
        )


class Storage(object):
    def __init__(self, entry_notifier, rpc_server, user_entry_creator):
        self.m_notifier = entry_notifier
        self.m_rpc_server = rpc_server

        # python-specific
        self.m_user_entry_creator = user_entry_creator

        self.m_mutex = threading.Lock()
        self.m_entries = {}
        self.m_idmap = []
        self.m_localmap = []
        self.m_rpc_results = {}
        self.m_rpc_blocking_calls = set()

        # If any persistent values have changed
        self.m_persistent_dirty = False

        # condition variable and termination flag for blocking on a RPC result
        self.m_terminating = False
        self.m_rpc_results_cond = threading.Condition(self.m_mutex)

        # configured by dispatcher at startup
        self.m_dispatcher = None
        self.m_server = True

        # python-specific
        self.m_dispatcher_queue_outgoing = lambda *a: None
        self._enter_outgoing = None

        # Differs from ntcore because python doesn't have switch statements...
        self._process_fns = {
            kEntryAssign: self._processIncomingEntryAssign,
            kEntryUpdate: self._processIncomingEntryUpdate,
            kFlagsUpdate: self._processIncomingFlagsUpdate,
            kEntryDelete: self._processIncomingEntryDelete,
            kClearEntries: self._processIncomingClearEntries,
            kExecuteRpc: self._processIncomingExecuteRpc,
            kRpcResponse: self._processIncomingRpcResponse,
        }

    def stop(self):
        self.m_terminating = True
        with self.m_mutex:
            self.m_rpc_results_cond.notify_all()

    def setDispatcher(self, dispatcher, server):
        with self.m_mutex:
            self.m_dispatcher = dispatcher
            self.m_dispatcher_queue_outgoing = dispatcher._queueOutgoing
            self.m_server = server

    def clearDispatcher(self):
        self.m_dispatcher = None
        self.m_dispatcher_queue_outgoing = None

    def getMessageEntryType(self, msg_id):
        with self.m_mutex:
            if msg_id >= len(self.m_idmap):
                return NT_UNASSIGNED

            entry = self.m_idmap[msg_id]
            if not entry or not entry.value:
                return NT_UNASSIGNED

            return entry.value.type

    #
    # Python specific functions to save us code
    # .. originally used a contextmanager, but that caused
    #    a lot of overhead
    #

    def __enter__(self):
        self.m_mutex.acquire()

        outgoing = []
        self._enter_outgoing = outgoing
        return outgoing

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.m_mutex.release()
        if exc_type is None:
            queue_outgoing = self.m_dispatcher_queue_outgoing
            # This has to happen outside the lock
            for o in self._enter_outgoing:
                queue_outgoing(*o)

    def processIncoming(self, msg, conn):
        # Note: c++ version takes a third param (weak_conn), but it's
        #       not needed here as conn == weak_conn
        fn = self._process_fns.get(msg.type)
        if fn:
            with self as outgoing:
                fn(msg, conn, outgoing)

    def _processIncomingEntryAssign(self, msg, conn, outgoing):

        msg_id = msg.id
        name = msg.str
        entry = None
        may_need_update = False

        if self.m_server:
            # if we're a server, id=0xffff requests are requests for an id
            # to be assigned, we need to send the assignment back to
            # the sender as well as all other connections.
            if msg_id == 0xFFFF:
                entry = self._getOrNew(name)
                # see if it was already assigned; ignore if so.
                if entry.id != 0xFFFF:
                    return

                entry.flags = msg.flags
                entry.isPersistent = (msg.flags & NT_PERSISTENT) != 0
                entry.seq_num = msg.seq_num_uid
                self._setEntryValueImpl(entry, msg.value, outgoing, False)
                return

            if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
                # ignore arbitrary entry assignments
                # this can happen due to e.g. assignment to deleted entry
                logger.debug("server: received assignment to unknown entry")
                return

            entry = self.m_idmap[msg_id]
        else:
            # clients simply accept assignments
            if msg_id == 0xFFFF:
                logger.debug("client: received entry assignment request?")
                return

            ensure_id_exists(self.m_idmap, msg_id)

            entry = self.m_idmap[msg_id]
            if entry is None:
                # create local
                entry = self._getOrNew(name)
                entry.id = msg_id
                self.m_idmap[msg_id] = entry
                if entry.value is None:
                    # didn't exist at all (rather than just being a response to a
                    # id assignment request)
                    entry.value = entry.user_entry._value = msg.value
                    entry.flags = msg.flags
                    entry.isPersistent = (msg.flags & NT_PERSISTENT) != 0
                    entry.seq_num = msg.seq_num_uid

                    # notify
                    self.m_notifier.notifyEntry(
                        entry.local_id, name, entry.value, NT_NOTIFY_NEW
                    )
                    return

                may_need_update = True  # we may need to send an update message

                # if the received flags don't match what we sent, most likely
                # updated flags locally in the interim; send flags update message.
                if msg.flags != entry.flags:
                    outmsg = Message.flagsUpdate(msg_id, entry.flags)
                    outgoing.append((outmsg, None, None))

        # common client and server handling

        # already exists; ignore if sequence number not higher than local
        seq_num = msg.seq_num_uid
        if entry.isSeqNewerThan(seq_num):
            if may_need_update:
                outmsg = Message.entryUpdate(entry.id, entry.seq_num, entry.value)
                outgoing.append((outmsg, None, None))

            return

        # sanity check: name should match id
        if msg.str != entry.name:
            logger.debug("entry assignment for same id with different name?")
            return

        notify_flags = NT_NOTIFY_UPDATE

        # don't update flags from a <3.0 remote (not part of message)
        # don't update flags if self is a server response to a client id request
        if not may_need_update and conn.get_proto_rev() >= 0x0300:
            # python-specific: move this check
            # update persistent dirty flag if persistent flag changed
            # if (entry.flags & NT_PERSISTENT) != (msg.flags & NT_PERSISTENT):
            #     self.m_persistent_dirty = True

            if entry.flags != msg.flags:
                notify_flags |= NT_NOTIFY_FLAGS

                # (moved here) update persistent dirty flag if persistent flag changed
                if (entry.flags & NT_PERSISTENT) != (msg.flags & NT_PERSISTENT):
                    self.m_persistent_dirty = True

            entry.flags = msg.flags
            entry.isPersistent = (msg.flags & NT_PERSISTENT) != 0

        # update persistent dirty flag if the value changed and it's persistent
        if entry.isPersistent and entry.value != msg.value:
            self.m_persistent_dirty = True

        # update local
        entry.value = entry.user_entry._value = msg.value
        entry.seq_num = seq_num

        # notify
        self.m_notifier.notifyEntry(entry.local_id, name, entry.value, notify_flags)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outmsg = Message.entryAssign(
                entry.name, msg_id, msg.seq_num_uid, msg.value, entry.flags
            )
            outgoing.append((outmsg, None, conn))

    def _processIncomingEntryUpdate(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates;
            # this can happen due to deleted entries
            logger.debug("received update to unknown entry")
            return

        entry = self.m_idmap[msg_id]

        # ignore if sequence number not higher than local
        seq_num = msg.seq_num_uid
        if entry.isSeqNewerOrEqual(seq_num):
            return

        # update local
        entry.value = entry.user_entry._value = msg.value
        entry.seq_num = seq_num

        # update persistent dirty flag if it's a persistent value
        if entry.isPersistent:
            self.m_persistent_dirty = True

        # notify
        self.m_notifier.notifyEntry(
            entry.local_id, entry.name, entry.value, NT_NOTIFY_UPDATE
        )

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))

    def _processIncomingFlagsUpdate(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates
            # this can happen due to deleted entries
            logger.debug("received flags update to unknown entry")
            return

        self._setEntryFlagsImpl(self.m_idmap[msg_id], msg.flags, outgoing, False)
        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))

    def _processIncomingEntryDelete(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates
            # this can happen due to deleted entries
            logger.debug("received delete to unknown entry")
            return

        self._deleteEntryImpl(self.m_idmap[msg_id], outgoing, False)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))

    def _processIncomingClearEntries(self, msg, conn, outgoing):
        # update local
        self._deleteAllEntriesImpl(False)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))

    def _processIncomingExecuteRpc(self, msg, conn, outgoing):
        if not self.m_server:
            return  # only process on server

        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore call to non-existent RPC
            # this can happen due to deleted entries
            logger.debug("received RPC call to unknown entry")
            return

        entry = self.m_idmap[msg_id]
        if not entry.value or not entry.isRpc():
            logger.debug("received RPC call to non-RPC entry")
            return

        call_uid = msg.seq_num_uid
        # XXX: TODO
        assert False
        self.m_rpc_server.processRpc(
            entry.local_id,
            entry.rpc_call_uid,
            entry.name,
            msg,
            entry.rpc_callback,
            conn.uid(),
            conn.queueOutgoing,
            conn.info(),
        )

    def _processIncomingRpcResponse(self, msg, conn, outgoing):
        if self.m_server:
            return  # only process on client

        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore call to non-existent RPC
            # this can happen due to deleted entries
            logger.debug("received RPC response to unknown entry")
            return

        entry = self.m_idmap[msg_id]
        if not entry.value or not entry.isRpc():
            logger.debug("received RPC call to non-RPC entry")
            return

        self.m_rpc_results[(entry.local_id, msg.seq_num_uid)] = msg.str
        self.m_rpc_results_cond.notify_all()

    def getInitialAssignments(self, conn, msgs):
        with self.m_mutex:
            conn.set_state(NetworkConnection.State.kSynchronized)
            for entry in self.m_entries.values():
                if entry.value is None:
                    continue
                msgs.append(
                    Message.entryAssign(
                        entry.name, entry.id, entry.seq_num, entry.value, entry.flags
                    )
                )

    def applyInitialAssignments(self, conn, msgs, new_server, out_msgs):
        with self as update_msgs:
            if self.m_server:
                return  # should not do this on server

            conn.set_state(NetworkConnection.State.kSynchronized)

            # clear existing id's
            for entry in self.m_entries.values():
                entry.id = 0xFFFF

            # clear existing idmap
            del self.m_idmap[:]

            # apply assignments
            for msg in msgs:
                if msg.type != kEntryAssign:
                    logger.debug("client: received non-entry assignment request?")
                    continue

                msg_id = msg.id
                if msg_id == 0xFFFF:
                    logger.debug("client: received entry assignment request?")
                    continue

                seq_num = msg.seq_num_uid
                name = msg.str

                entry = self._getOrNew(name)
                entry.seq_num = seq_num
                entry.id = msg_id

                if entry.value is None:
                    entry.value = entry.user_entry._value = msg.value
                    entry.flags = msg.flags
                    entry.isPersistent = (msg.flags & NT_PERSISTENT) != 0

                    # notify
                    self.m_notifier.notifyEntry(
                        entry.local_id, name, entry.value, NT_NOTIFY_NEW
                    )
                else:
                    # if we have written the value locally and the value is not persistent,
                    # then we don't update the local value and instead send it back to the
                    # server as an update message
                    if entry.local_write and not entry.isPersistent:
                        entry.increment_seqnum()
                        update_msgs.append(
                            (
                                Message.entryUpdate(
                                    entry.id, entry.seq_num, entry.value
                                ),
                                None,
                                None,
                            )
                        )
                    else:
                        entry.value = entry.user_entry._value = msg.value
                        notify_flags = NT_NOTIFY_UPDATE
                        # don't update flags from a <3.0 remote (not part of message)
                        if conn.get_proto_rev() >= 0x0300:
                            if entry.flags != msg.flags:
                                notify_flags |= NT_NOTIFY_FLAGS

                            entry.flags = msg.flags
                            entry.isPersistent = (msg.flags & NT_PERSISTENT) != 0

                        # notify
                        self.m_notifier.notifyEntry(
                            entry.local_id, name, entry.value, notify_flags
                        )

                # save to idmap
                ensure_id_exists(self.m_idmap, msg_id)
                self.m_idmap[msg_id] = entry

            # delete or generate assign messages for unassigned local entries
            def _shouldDelete(entry):
                #  was assigned by the server, don't delete
                if entry.id != 0xFFFF:
                    return False

                # if we have written the value locally, we send an assign message to the
                # server instead of deleting
                if entry.local_write:
                    out_msgs.append(
                        Message.entryAssign(
                            entry.name,
                            entry.id,
                            entry.seq_num,
                            entry.value,
                            entry.flags,
                        )
                    )
                    return False

                # otherwise delete
                return True

            self._deleteAllEntriesImpl(False, _shouldDelete)

    def getEntryValue(self, name):
        with self.m_mutex:
            e = self.m_entries.get(name)
            if e:
                return e.value

    def setDefaultEntryValue(self, name, value):
        if not name:
            return False  # can't compare empty name

        if value is None:
            return False  # can't compare to a null value

        with self as outgoing:
            entry = self._getOrNew(name)

            # We return early if value already exists; if types match return true
            if entry.value is not None:
                return entry.value.type == value.type

            self._setEntryValueImpl(entry, value, outgoing, True)
            return True

    def setDefaultEntryValueById(self, local_id, value):
        if value is None:
            return False  # can't compare to a null value

        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return False

            # We return early if value already exists; if types match return true
            if entry.value:
                return entry.value.type == value.type

            self._setEntryValueImpl(entry, value, outgoing, True)
            return True

    def setEntryValue(self, name, value):
        if not name:
            return True
        if value is None:
            return True

        with self as outgoing:
            entry = self._getOrNew(name)
            if entry.value is not None and entry.value.type != value.type:
                return False  # error on type mismatch

            self._setEntryValueImpl(entry, value, outgoing, True)
            return True

    def setEntryValueById(self, local_id, value):
        if value is None:
            return True

        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return True

            if entry.value and entry.value.type != value.type:
                return False  # error on type mismatch

            self._setEntryValueImpl(entry, value, outgoing, True)
            return True

    def _setEntryValueImpl(self, entry, value, outgoing, local):

        if value is None:
            return True

        old_value = entry.value
        entry.value = entry.user_entry._value = value

        # if we're the server, assign an id if it doesn't have one
        if self.m_server and entry.id == 0xFFFF:
            entry.id = len(self.m_idmap)
            self.m_idmap.append(entry)

        # update persistent dirty flag if value changed and it's persistent
        if entry.isPersistent and (old_value is None or old_value != value):
            self.m_persistent_dirty = True

        # notify
        nflag = NT_NOTIFY_LOCAL if local else 0
        if old_value is None:
            self.m_notifier.notifyEntry(
                entry.local_id, entry.name, value, NT_NOTIFY_NEW | nflag
            )

        elif old_value != value:
            self.m_notifier.notifyEntry(
                entry.local_id, entry.name, value, NT_NOTIFY_UPDATE | nflag
            )

        # remember local changes
        if local:
            entry.local_write = True

        # generate message
        if outgoing is None or (not local and not self.m_server):
            return

        if old_value is None or old_value.type != value.type:
            if local:
                entry.increment_seqnum()
            msg = Message.entryAssign(
                entry.name, entry.id, entry.seq_num, value, entry.flags
            )
            outgoing.append((msg, None, None))

        elif old_value != value:
            if local:
                entry.increment_seqnum()

            # don't send an update if we don't have an assigned id yet
            if entry.id != 0xFFFF:
                msg = Message.entryUpdate(entry.id, entry.seq_num, value)
                outgoing.append((msg, None, None))

    def setEntryTypeValue(self, name, value):
        if not name:
            return
        if value is None:
            return

        with self as outgoing:
            entry = self._getOrNew(name)
            self._setEntryValueImpl(entry, value, outgoing, True)

    def setEntryTypeValueById(self, local_id, value):
        if value is None:
            return

        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return
            self._setEntryValueImpl(entry, value, outgoing, True)

    def setEntryFlags(self, name, flags):
        if not name:
            return

        with self as outgoing:
            entry = self.m_entries.get(name)
            if entry is None:
                return
            self._setEntryFlagsImpl(entry, flags, outgoing, True)

    def setEntryFlagsById(self, local_id, flags):
        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return
            self._setEntryFlagsImpl(entry, flags, outgoing, True)

    def _setEntryFlagsImpl(self, entry, flags, outgoing, local):
        if entry.value is None or entry.flags == flags:
            return

        # update persistent dirty flag if persistent flag changed
        if (entry.flags & NT_PERSISTENT) != (flags & NT_PERSISTENT):
            self.m_persistent_dirty = True

        entry.flags = flags
        entry.isPersistent = (flags & NT_PERSISTENT) != 0

        # notify
        self.m_notifier.notifyEntry(
            entry.local_id,
            entry.name,
            entry.value,
            NT_NOTIFY_FLAGS | (NT_NOTIFY_LOCAL if local else 0),
        )

        # generate message
        if not local or outgoing is None:
            return

        entry_id = entry.id

        # don't send an update if we don't have an assigned id yet
        if entry_id != 0xFFFF:
            outgoing.append((Message.flagsUpdate(entry_id, flags), None, None))

    def getEntryFlags(self, name):
        with self.m_mutex:
            entry = self.m_entries.get(name)
            return entry.flags if entry else 0

    def getEntryFlagsById(self, local_id):
        with self.m_mutex:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return 0
            else:
                return entry.flags

    def deleteEntry(self, name):
        if not name:
            return

        with self as outgoing:
            try:
                entry = self.m_entries[name]
            except KeyError:
                return
            else:
                self._deleteEntryImpl(entry, outgoing, True)

    def deleteEntryById(self, local_id):
        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return
            else:
                self._deleteEntryImpl(entry, outgoing, True)

    def _deleteEntryImpl(self, entry, outgoing, local):

        entry_id = entry.id
        if entry_id < len(self.m_idmap):
            self.m_idmap[entry_id] = None

        # empty the value and reset id and local_write flag
        old_value = entry.value
        entry.value = entry.user_entry._value = None
        entry.id = 0xFFFF
        entry.local_write = False

        # Remove RPC if there was one
        if entry.rpc_uid is not None:
            self.m_rpc_server.removeRpc(entry.rpc_uid)
            entry.rpc_uid = None

        # update persistent dirty flag if it's a persistent value
        if entry.isPersistent:
            self.m_persistent_dirty = True

        # reset flags
        entry.flags = 0
        entry.isPersistent = False

        if old_value is None:
            return  # was not previously assigned

        # notify
        self.m_notifier.notifyEntry(
            entry.local_id,
            entry.name,
            old_value,
            NT_NOTIFY_DELETE | (NT_NOTIFY_LOCAL if local else 0),
        )

        # if it had a value, generate message
        # don't send an update if we don't have an assigned id yet
        if outgoing is not None and local and entry_id != 0xFFFF:
            outgoing.append((Message.entryDelete(entry_id), None, None))

    def _defaultShouldDelete(self, entry):
        return not entry.isPersistent

    def _deleteAllEntriesImpl(self, local, should_delete=None):
        if should_delete is None:
            should_delete = self._defaultShouldDelete

        notify_flags = NT_NOTIFY_DELETE | (NT_NOTIFY_LOCAL if local else 0)
        deleted = False

        for name, entry in self.m_entries.items():
            if entry.value is not None and should_delete(entry):
                # notify it's being deleted
                self.m_notifier.notifyEntry(
                    entry.local_id, entry.name, entry.value, notify_flags
                )

                # remove it from idmap
                if entry.id < len(self.m_idmap):
                    self.m_idmap[entry.id] = None

                entry.id = 0xFFFF
                entry.local_write = False
                entry.value = entry.user_entry._value = None

                deleted = True

        return deleted

    def deleteAllEntries(self):
        with self as outgoing:
            deleted = self._deleteAllEntriesImpl(True)

            # generate message
            if deleted and outgoing is not None:
                outgoing.append((Message.clearEntries(), None, None))

    def _getOrNew(self, name):
        entry = self.m_entries.get(name)
        if not entry:
            local_id = len(self.m_localmap)
            user_entry = self.m_user_entry_creator(name, local_id)
            entry = _Entry(name, local_id, user_entry)
            self.m_entries[name] = entry
            self.m_localmap.append(entry)
        return entry

    # ntcore: getEntry
    def getEntryId(self, name):
        if name:
            with self.m_mutex:
                entry = self._getOrNew(name)
                return entry.local_id

    # python-specific
    def getEntry(self, name):
        if name:
            with self.m_mutex:
                entry = self._getOrNew(name)
                return entry.user_entry

    # python-specific: returns user entries instead of ids
    def getEntries(self, prefix, types):
        with self.m_mutex:
            entries = []
            types = types if isinstance(types, int) else ord(types)
            for k, entry in self.m_entries.items():
                if entry.value is None or not k.startswith(prefix):
                    continue
                if types != 0 and ((types & ord(entry.value.type)) == 0):
                    continue
                entries.append(entry.user_entry)
        return entries

    def getEntryInfoById(self, local_id):
        with self.m_mutex:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return EntryInfo(None, NT_UNASSIGNED, 0)
            else:
                return EntryInfo(entry.name, entry.value.type, entry.flags)

    def getEntryNameById(self, local_id):
        with self.m_mutex:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return None
            else:
                return entry.name

    def getEntryTypeById(self, local_id):
        with self.m_mutex:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return NT_UNASSIGNED
            else:
                if entry.value is None:
                    return NT_UNASSIGNED
                return entry.value.type

    def getEntryInfo(self, prefix, types):
        with self.m_mutex:
            infos = []
            types = types if isinstance(types, int) else ord(types)
            for k, entry in self.m_entries.items():
                value = entry.value
                if value is None or not k.startswith(prefix):
                    continue

                if types != 0 and (types & ord(value.type)) == 0:
                    continue

                info = EntryInfo(entry.name, value.type, entry.flags)
                infos.append(info)

            return infos

    def addListener(self, prefix, callback, flags):
        with self.m_mutex:
            uid = self.m_notifier.add(callback, prefix, flags)
            # perform immediate notifications
            if (flags & NT_NOTIFY_IMMEDIATE) != 0 and (flags & NT_NOTIFY_NEW) != 0:
                for k, entry in self.m_entries.items():
                    if entry.value is None or not k.startswith(prefix):
                        continue
                    self.m_notifier.notifyEntry(
                        entry.local_id,
                        k,
                        entry.value,
                        NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW,
                        uid,
                    )
        return uid

    def addListenerById(self, local_id, callback, flags):
        with self.m_mutex:
            uid = self.m_notifier.addById(callback, local_id, flags)
            # perform immediate notifications
            if (flags & NT_NOTIFY_IMMEDIATE) != 0 and (flags & NT_NOTIFY_NEW) != 0:
                try:
                    entry = self.m_localmap[local_id]
                except IndexError:
                    pass
                else:
                    # if no value, don't notify
                    if entry.value is not None:
                        self.m_notifier.notifyEntry(
                            local_id,
                            entry.name,
                            entry.value,
                            NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW,
                            uid,
                        )
        return uid

    def addPolledListener(self, poller_uid, prefix, flags):
        with self.m_mutex:
            uid = self.m_notifier.addPolled(poller_uid, prefix, flags)
            # perform immediate notifications
            if (flags & NT_NOTIFY_IMMEDIATE) != 0 and (flags & NT_NOTIFY_NEW) != 0:
                for k, entry in self.m_entries.items():
                    if entry.value is None or not k.startswith(prefix):
                        continue
                    self.m_notifier.notifyEntry(
                        entry.local_id,
                        k,
                        entry.value,
                        NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW,
                        uid,
                    )
        return uid

    def addPolledListenerById(self, poller_uid, local_id, flags):
        with self.m_mutex:
            uid = self.m_notifier.addPolledById(poller_uid, local_id, flags)
            # perform immediate notifications
            if (flags & NT_NOTIFY_IMMEDIATE) != 0 and (flags & NT_NOTIFY_NEW) != 0:
                try:
                    entry = self.m_localmap[local_id]
                except IndexError:
                    pass
                else:
                    # if no value, don't notify
                    if entry.value is not None:
                        self.m_notifier.notifyEntry(
                            local_id,
                            entry.name,
                            entry.value,
                            NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW,
                            uid,
                        )
        return uid

    def _getPersistentEntries(self, periodic):
        # copy values out of storage as quickly as possible so lock isn't held
        with self.m_mutex:
            if periodic and not self.m_persistent_dirty:
                return False

            self.m_persistent_dirty = False

            entries = [
                (entry.name, entry.value)
                for entry in self.m_entries.values()
                if entry.value is not None and entry.isPersistent
            ]

        # sort in name order
        entries.sort()
        return entries

    # ntcore: called getEntries
    def getEntryValues(self, prefix):
        # copy values out of storage as quickly as possible so lock isn't held
        with self.m_mutex:
            entries = [
                (entry.name, entry.value)
                for entry in self.m_entries.values()
                if entry.value is not None and entry.name.startswith(prefix)
            ]

        # sort in name order
        entries.sort()
        return entries

    def createRpc(self, local_id, defn, rpc_uid):
        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return

            old_value = entry.value
            value = Value.makeRpc(defn)
            entry.value = entry.user_entry._value = value

            # set up the RPC info
            entry.rpc_uid = rpc_uid

            if old_value == value:
                return

            # assign an id if it doesn't have one
            if entry.id == 0xFFFF:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)

            # generate message
            if outgoing is not None:
                if old_value is None or old_value.type != value.type:
                    entry.increment_seqnum()
                    msg = Message.entryAssign(
                        entry.name, entry.id, entry.seq_num, value, entry.flags
                    )
                else:
                    entry.increment_seqnum()
                    msg = Message.entryUpdate(entry.id, entry.seq_num, value)

                outgoing.append((msg, None, None))

    def callRpc(self, local_id, params):
        with self as outgoing:
            try:
                entry = self.m_localmap[local_id]
            except IndexError:
                return 0

            if entry.value is None or not entry.isRpc():
                return 0

            entry.rpc_call_uid += 1
            entry.rpc_call_uid &= 0xFFFF
            call_uid = entry.rpc_call_uid

            msg = Message.executeRpc(entry.id, call_uid, params)
            if not self.m_server:
                outgoing.append((msg, None, None))
                return call_uid

            # RPCs are unlikely to be used locally on the server, handle it
            # gracefully anyway.
            rpc_uid = entry.rpc_uid
            name = entry.name

        conn_info = ConnectionInfo("Server", "localhost", 0, monotonic(), 0x0300)
        self.m_rpc_server.processRpc(
            local_id, call_uid, name, msg, conn_info, self._process_rpc, rpc_uid
        )
        return call_uid

    def _process_rpc(self, local_id, call_uid, result):
        with self.m_mutex:
            self.m_rpc_results[(local_id, call_uid)] = result
            self.m_rpc_results_cond.notify_all()

    def getRpcResult(self, local_id, call_uid, timeout=None):
        # returns timed_out, result

        with self.m_mutex:
            call_pair = (local_id, call_uid)

            # only allow one blocking call per rpc call uid
            if call_pair in self.m_rpc_blocking_calls:
                return False, None

            self.m_rpc_blocking_calls.add(call_pair)
            wait_until = monotonic() + timeout

            try:
                while True:
                    result = self.m_rpc_results.pop(call_pair, None)
                    if result is None:
                        if timeout == 0 or self.m_terminating:
                            return False, None

                        if timeout < 0:
                            self.m_rpc_results_cond.wait()
                        else:
                            ttw = monotonic() - wait_until
                            if ttw <= 0:
                                return False, None

                            self.m_rpc_results_cond.wait(ttw)

                        # if element does not exist, have been canceled
                        if call_pair not in self.m_rpc_blocking_calls:
                            return False, None

                        if self.m_terminating:
                            return False, None

                        continue

                    return True, result
            finally:
                try:
                    self.m_rpc_blocking_calls.remove(call_pair)
                except KeyError:
                    pass

    def cancelBlockingRpcResult(self, call_uid):
        with self.m_mutex:
            # safe to erase even if id does not exist
            self.m_rpc_blocking_calls.erase(call_uid)
            self.m_rpc_results_cond.notify_all()

    #
    # Persistence stuff from Storage_load.cpp/Storage_save.cpp
    #

    # from Storage_load.cpp
    def loadPersistent(self, filename=None, fp=None):
        return self._loadFromFile(True, "", filename, fp)

    def loadEntries(self, filename=None, fp=None, prefix=""):
        return self._loadFromFile(False, prefix, filename, fp)

    def _loadFromFile(self, persistent, prefix, filename, fp):
        try:
            if fp:
                entries = load_entries(fp, filename if filename else "<string>", prefix)
            else:
                with open(filename, "r") as fp:
                    entries = load_entries(fp, filename, prefix)
        except IOError as e:
            return "Error reading file: %s" % e
        else:
            self._loadEntries(entries, persistent)
            return

    def _loadEntries(self, entries, persistent):
        # entries is a list of (str, Value) tuples

        # copy values into storage as quickly as possible so lock isn't held
        with self as outgoing:
            for name, value in entries:
                entry = self._getOrNew(name)
                old_value = entry.value
                entry.value = entry.user_entry._value = value
                was_persist = entry.isPersistent
                if not was_persist and persistent:
                    entry.flags |= NT_PERSISTENT
                    entry.isPersistent = True

                # if we're the server, an id if it doesn't have one
                if self.m_server and entry.id == 0xFFFF:
                    entry.id = len(self.m_idmap)
                    self.m_idmap.append(entry)

                # notify (for local listeners)
                if self.m_notifier.m_local_notifiers:
                    if old_value is None:
                        self.m_notifier.notifyEntry(
                            entry.local_id, name, value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL
                        )
                    elif old_value != value:
                        notify_flags = NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL
                        if not was_persist and persistent:
                            notify_flags |= NT_NOTIFY_FLAGS

                        self.m_notifier.notifyEntry(
                            entry.local_id, name, value, notify_flags
                        )
                    elif not was_persist and persistent:
                        self.m_notifier.notifyEntry(
                            entry.local_id,
                            name,
                            value,
                            NT_NOTIFY_FLAGS | NT_NOTIFY_LOCAL,
                        )

                if outgoing is None:
                    continue  # shortcut

                entry.increment_seqnum()

                # put on update queue
                if old_value is None or old_value.type != value.type:
                    outgoing.append(
                        (
                            Message.entryAssign(
                                name, entry.id, entry.seq_num, value, entry.flags
                            ),
                            None,
                            None,
                        )
                    )
                elif entry.id != 0xFFFF:
                    # don't send an update if we don't have an assigned id yet
                    if old_value != value:
                        outgoing.append(
                            (
                                Message.entryUpdate(entry.id, entry.seq_num, value),
                                None,
                                None,
                            )
                        )
                    if not was_persist and persistent:
                        outgoing.append(
                            (Message.flagsUpdate(entry.id, entry.flags), None, None)
                        )

    # from Storage_save.cpp
    def savePersistent(self, filename=None, periodic=False, fp=None):
        entries = self._getPersistentEntries(periodic)
        if entries == False:
            return

        err = self._saveEntries(entries, filename, fp)
        if err and periodic:
            self.m_persistent_dirty = True
        return err

    def saveEntries(self, prefix, filename=None, fp=None):
        entries = self.getEntryValues(prefix)
        return self._saveEntries(entries, filename, fp)

    def _saveEntries(self, entries, filename, fp):
        # Going to not use tempfile to keep compatibility with ntcore,
        # as having to cleanup temp files on the RIO is probably bad
        if fp:
            try:
                save_entries(fp, entries)
            except IOError as e:
                return "Error writing file: %s" % e
        else:
            tmp = "%s.tmp" % filename
            bak = "%s.bak" % filename

            try:
                with open(tmp, "w") as fp:
                    save_entries(fp, entries)
                    os.fsync(fp.fileno())
            except IOError as e:
                return "Error writing file: %s" % e

            try:
                os.replace(filename, bak)
            except OSError:
                pass  # ignored

            try:
                os.replace(tmp, filename)
            except OSError as e:
                try:
                    # try to restore backup
                    os.replace(bak, filename)
                except OSError:
                    pass

                return "Could not rename temp file to real file: %s" % e

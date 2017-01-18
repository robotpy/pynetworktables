# validated: 2016-10-27 DS a7eca7d src/Storage.cpp src/Storage.h
'''----------------------------------------------------------------------------'''
''' Copyright (c) FIRST 2015. All Rights Reserved.                             '''
''' Open Source Software - may be modified and shared by FRC teams. The code   '''
''' must be accompanied by the FIRST BSD license file in the root directory of '''
''' the project.                                                               '''
'''----------------------------------------------------------------------------'''

import os
import threading

from .message import Message
from .network_connection import NetworkConnection
from .persistence import load_entries, save_entries
from .structs import EntryInfo, ConnectionInfo
from .value import Value

from .support.compat import monotonic, file_replace
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
    
    NT_NOTIFY_IMMEDIATE,
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_NEW,
    NT_NOTIFY_DELETE,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS
)

import logging
logger = logging.getLogger('nt')



class _Entry(object):
    __slots__ = ['name', 'value', 'flags',
                 'id', 'seq_num', 'rpc_callback',
                 'rpc_call_uid']
    
    def __init__(self, name, value=None, flags=0, seq_num=0):
        # We redundantly store the name so that it's available when accessing the
        # raw Entry* via the ID map.
        self.name = name
        
        # The current value and flags.
        self.value = value
        self.flags = flags
        
        # Unique ID for self entry as used in network messages.  The value is
        # assigned by the server, on the client this is 0xffff until an
        # entry assignment is received back from the server.
        self.id = 0xffff
        
        # Sequence number for update resolution.
        self.seq_num = seq_num
        
        # RPC callback function.  Null if either not an RPC or if the RPC is
        # polled.
        self.rpc_callback = None
        
        # Last UID used when calling self RPC (primarily for client use).  This
        # is incremented for each call.
        self.rpc_call_uid = 0
        
    def isPersistent(self):
        return (self.flags & NT_PERSISTENT) != 0 
    
    def increment_seqnum(self):
        self.seq_num += 1
        self.seq_num &= 0xffff
        
    def isSeqNewerThan(self, other):
        seq_num = self.seq_num
        if other < seq_num:
            return (seq_num - other) < 32768
        elif other > seq_num:
            return (other - seq_num) > 32768
        else:
            return True
        
    def __repr__(self):
        return "<_Entry name='%s' value=%s flags=%s id=%s seq_num=%s rpc_callback=%s rpc_call_uid=%s" % \
            (self.name, self.value, self.flags, self.id,
             self.seq_num, self.rpc_callback, self.rpc_call_uid)


class Storage(object):
    
    def __init__(self, notifier, rpc_server):
        self.m_notifier = notifier
        self.m_rpc_server = rpc_server
        
        self.m_mutex = threading.Lock()
        self.m_entries = {}
        self.m_idmap = []
        self.m_rpc_results = {}
        self.m_rpc_blocking_calls = set()
        
        # If any persistent values have changed
        self.m_persistent_dirty = False
        
        # used to ensure that only a single persistent operation happens
        self.m_persistence_save_lock = threading.Lock()
        
        # condition variable and termination flag for blocking on a RPC result
        self.m_terminating = False
        self.m_rpc_results_cond = threading.Condition()
        
        # configured by dispatcher at startup
        self.m_queue_outgoing = None
        self.m_server = True
        
        self._process_fns = {
            kEntryAssign:   self._processEntryAssign,
            kEntryUpdate:   self._processEntryUpdate,
            kFlagsUpdate:   self._processFlagsUpdate,
            kEntryDelete:   self._processEntryDelete,
            kClearEntries:  self._processClearEntries,
            kExecuteRpc:    self._processExecuteRpc,
            kRpcResponse:   self._processRpcResponse
        }
    
    def stop(self):
        self.m_terminating = True
        with self.m_rpc_results_cond:
            self.m_rpc_results_cond.notify_all()
    
    def setOutgoing(self, queue_outgoing, server):
        with self.m_mutex:
            self.m_queue_outgoing = queue_outgoing
            self.m_server = server
    
    def clearOutgoing(self):
        self.m_queue_outgoing = None
    
    def getEntryType(self, msg_id):
        with self.m_mutex:
            if msg_id >= len(self.m_idmap):
                return NT_UNASSIGNED
        
            entry = self.m_idmap[msg_id]
            if not entry or not entry.value:
                return NT_UNASSIGNED
        
            return entry.value.type
    
    
    def processIncoming(self, msg, conn):
        # Note: c++ version takes a third param (weak_conn), but it's
        #       not needed here as conn == weak_conn
        fn = self._process_fns.get(msg.type)
        if fn:
            
            with self.m_mutex:
                queue_outgoing = self.m_queue_outgoing
                outgoing = [] if queue_outgoing else None
                fn(msg, conn, outgoing)
                    
            # this has to happen outside the lock
            if outgoing:
                for o in outgoing:
                    queue_outgoing(*o)
    
    def _processEntryAssign(self, msg, conn, outgoing):

        msg_id = msg.id
        name = msg.str
        entry = None
        may_need_update = False
        
        if self.m_server:
            # if we're a server, id=0xffff requests are requests for an id
            # to be assigned, we need to send the assignment back to
            # the sender as well as all other connections.
            if msg_id == 0xffff:
                # see if it was already assigned; ignore if so.
                entry = self.m_entries.get(name)
                if name in self.m_entries:
                    return
                
                # create it locally
                entry = _Entry(name, msg.value)
                msg_id = len(self.m_idmap)
                self.m_entries[name] = entry
                
                entry.flags = msg.flags
                entry.id = msg_id
                self.m_idmap.append(entry)

                # update persistent dirty flag if it's persistent
                if entry.isPersistent():
                    self.m_persistent_dirty = True
                
                # notify
                self.m_notifier.notifyEntry(name, entry.value, NT_NOTIFY_NEW)

                # send the assignment to everyone (including the originator)
                if outgoing is not None:
                    outmsg = Message.entryAssign(name, msg_id, entry.seq_num, msg.value, msg.flags)
                    outgoing.append((outmsg, None, None))

                return

            if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
                # ignore arbitrary entry assignments
                # this can happen due to e.g. assignment to deleted entry
                logger.debug("server: received assignment to unknown entry")
                return

            entry = self.m_idmap[msg_id]

        else:
            # clients simply accept assignments
            if msg_id == 0xffff:
                logger.debug("client: received entry assignment request?")
                return

            ensure_id_exists(self.m_idmap, msg_id)
            
            entry = self.m_idmap[msg_id]
            if not entry:
                # create local
                entry = self.m_entries.get(name)
                if not entry:
                    # didn't exist at all (rather than just being a response to a
                    # id assignment request)
                    entry = _Entry(name, msg.value)
                    entry.flags = msg.flags
                    entry.id = msg_id
                    self.m_entries[name] = entry
                    self.m_idmap[msg_id] = entry

                    # notify
                    self.m_notifier.notifyEntry(name, entry.value, NT_NOTIFY_NEW)
                    return

                may_need_update = True;  # we may need to send an update message
                entry.id = msg_id
                self.m_idmap[msg_id] = entry

                # if the received flags don't match what we sent, most likely
                # updated flags locally in the interim; send flags update message.
                if msg.flags != entry.flags and outgoing is not None:
                    outmsg = Message.flagsUpdate(msg_id, entry.flags)
                    outgoing.append((outmsg, None, None))


        # common client and server handling

        # already exists; ignore if sequence number not higher than local
        seq_num = msg.seq_num_uid
        if entry.isSeqNewerThan(seq_num):
            if may_need_update and outgoing is not None:
                outmsg = Message.entryUpdate(entry.id, entry.seq_num,
                                             entry.value)
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
            # update persistent dirty flag if persistent flag changed
            if (entry.flags & NT_PERSISTENT) != (msg.flags & NT_PERSISTENT):
                self.m_persistent_dirty = True

            if entry.flags != msg.flags:
                notify_flags |= NT_NOTIFY_FLAGS

            entry.flags = msg.flags


        # update persistent dirty flag if the value changed and it's persistent
        if entry.isPersistent() and entry.value != msg.value:
            self.m_persistent_dirty = True


        # update local
        entry.value = msg.value
        entry.seq_num = seq_num

        # notify
        self.m_notifier.notifyEntry(name, entry.value, notify_flags)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outmsg = Message.entryAssign(entry.name, msg_id, msg.seq_num_uid,
                                         msg.value, entry.flags)
            outgoing.append((outmsg, None, conn))
    
    def _processEntryUpdate(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates
            # self can happen due to deleted entries
            logger.debug("received update to unknown entry")
            return

        entry = self.m_idmap[msg_id]

        # ignore if sequence number not higher than local
        seq_num = msg.seq_num_uid
        if entry.isSeqNewerThan(seq_num):
            return
        
        # update local
        entry.value = msg.value
        entry.seq_num = seq_num

        # update persistent dirty flag if it's a persistent value
        if entry.isPersistent():
            self.m_persistent_dirty = True
        
        # notify
        self.m_notifier.notifyEntry(entry.name, entry.value, NT_NOTIFY_UPDATE)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))
    
    def _processFlagsUpdate(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates
            # self can happen due to deleted entries
            logger.debug("received flags update to unknown entry")
            return

        entry = self.m_idmap[msg_id]

        # ignore if flags didn't actually change
        if entry.flags == msg.flags:
            return


        # update persistent dirty flag if persistent flag changed
        if (entry.flags & NT_PERSISTENT) != (msg.flags & NT_PERSISTENT):
            self.m_persistent_dirty = True


        # update local
        entry.flags = msg.flags

        # notify
        self.m_notifier.notifyEntry(entry.name, entry.value, NT_NOTIFY_FLAGS)

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))
    
    def _processEntryDelete(self, msg, conn, outgoing):
        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore arbitrary entry updates
            # self can happen due to deleted entries
            logger.debug("received delete to unknown entry")
            return

        entry = self.m_idmap[msg_id]

        # update persistent dirty flag if it's a persistent value
        if entry.isPersistent():
            self.m_persistent_dirty = True


        # delete it from idmap
        self.m_idmap[msg_id] = None

        # get entry (as we'll need it for notify) and erase it from the map
        try:
            entry2 = self.m_entries.pop(entry.name)
        except KeyError:
            # it should always be in the map, sanity check just in case
            pass
        else:
            self.m_notifier.notifyEntry(entry2.name, entry2.value, NT_NOTIFY_DELETE)
        
        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))
    
    def _processClearEntries(self, msg, conn, outgoing):
        # update local
        self._deleteAllEntriesImpl()

        # broadcast to all other connections (note for client there won't
        # be any other connections, don't bother)
        if self.m_server and outgoing is not None:
            outgoing.append((msg, None, conn))
    
    def _processExecuteRpc(self, msg, conn, outgoing):
        if not self.m_server:
            return    # only process on server

        msg_id = msg.id
        if msg_id >= len(self.m_idmap) or not self.m_idmap[msg_id]:
            # ignore call to non-existent RPC
            # self can happen due to deleted entries
            logger.debug("received RPC call to unknown entry")
            return

        entry = self.m_idmap[msg_id]
        if not entry.value.IsRpc():
            logger.debug("received RPC call to non-RPC entry")
            return

        self.m_rpc_server.processRpc(entry.name, msg, entry.rpc_callback,
                                     conn.uid(), conn.queueOutgoing, conn.info())
    
    def _processRpcResponse(self, msg, conn, outgoing):
        if self.m_server:
            return    # only process on client
        
        self.m_rpc_results[(msg.id, msg.seq_num_uid)] = msg.str
        self.m_rpc_results_cond.notify_all()
    
    def getInitialAssignments(self, conn, msgs):
        with self.m_mutex:
            conn.set_state(NetworkConnection.State.kSynchronized)
            for entry in self.m_entries.values():
                msgs.append(Message.entryAssign(entry.name, entry.id,
                                                entry.seq_num,
                                                entry.value, entry.flags))
    
    def applyInitialAssignments(self, conn, msgs, new_server, out_msgs):
        with self.m_mutex:
            if self.m_server:
                return    # should not do this on server
        
            conn.set_state(NetworkConnection.State.kSynchronized)
        
            update_msgs = []
        
            # clear existing id's
            for entry in self.m_entries.values():
                entry.id = 0xffff
        
            # clear existing idmap
            del self.m_idmap[:]
        
            # apply assignments
            for msg in msgs:
                if msg.type != kEntryAssign:
                    logger.debug("client: received non-entry assignment request?")
                    continue
        
                msg_id = msg.id
                if msg_id == 0xffff:
                    logger.debug("client: received entry assignment request?")
                    continue
        
                seq_num = msg.seq_num_uid
                name = msg.str
        
                entry = self.m_entries.get(name)
                if not entry:
                    # doesn't currently exist
                    entry = _Entry(name, msg.value, msg.flags, seq_num)
                    self.m_entries[name] = entry
                    
                    # notify
                    self.m_notifier.notifyEntry(name, entry.value, NT_NOTIFY_NEW)
        
                else:
                    # if reconnect and sequence number not higher than local, we
                    # don't update the local value and instead send it back to the server
                    # as an update message
                    if not new_server and entry.isSeqNewerThan(seq_num):
                        update_msgs.append(Message.entryUpdate(entry.id, entry.seq_num, entry.value))
        
                    else:
                        entry.value = msg.value
                        entry.seq_num = seq_num
                        notify_flags = NT_NOTIFY_UPDATE
                        # don't update flags from a <3.0 remote (not part of message)
                        if conn.get_proto_rev() >= 0x0300:
                            if entry.flags != msg.flags:
                                notify_flags |= NT_NOTIFY_FLAGS
        
                            entry.flags = msg.flags
        
                        # notify
                        self.m_notifier.notifyEntry(name, entry.value, notify_flags)
        
                # set id and save to idmap
                entry.id = msg_id
                
                ensure_id_exists(self.m_idmap, msg_id)
                self.m_idmap[msg_id] = entry
            
            # generate assign messages for unassigned local entries
            for entry in self.m_entries.values():
                if entry.id != 0xffff:
                    continue
        
                out_msgs.append(Message.entryAssign(entry.name, entry.id,
                                                    entry.seq_num,
                                                    entry.value, entry.flags))
        
            queue_outgoing = self.m_queue_outgoing
        
        # Outside of mutex
        for msg in update_msgs:
            queue_outgoing(msg, None, None)
    
    def getEntryValue(self, name):
        with self.m_mutex:
            e = self.m_entries.get(name)
            if e:
                return e.value
    
    def setDefaultEntryValue(self, name, value):
        if not value:
            return False    # can't compare to a null value
    
        if not name:
            return False    # can't compare empty name
    
        with self.m_mutex:
            entry = self.m_entries.get(name)
            if entry:   # entry already exists
                old_value = entry.value
                
                # if types match return True
                if old_value.type == value.type:
                    return True
                else:
                    return False    # entry exists but doesn't match type
        
            # if we've gotten here, does not exist, we can write it.
            # don't need to compare old value as we know it will assign
            entry = _Entry(name, value)
            self.m_entries[name] = entry
            
            # if we're the server, an id if it doesn't have one
            if self.m_server and entry.id == 0xffff:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)
        
            # notify (for local listeners)
            if self.m_notifier.m_local_notifiers:
                # always a new entry if we got this far
                self.m_notifier.notifyEntry(name, value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)
        
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return True
            
            msg = Message.entryAssign(name, entry.id, entry.seq_num,
                                            entry.value, entry.flags)
            
        # Outside of mutex
        queue_outgoing(msg, None, None)
        return True
    
    def setEntryValue(self, name, value):
        if not name:
            return True
    
        if not value:
            return True
    
        with self.m_mutex:
            entry = self.m_entries.get(name)
            if not entry:
                old_value = None
                entry = _Entry(name, value)
                self.m_entries[name] = entry
            else:
                old_value = entry.value
                if old_value.type != value.type:
                    return False    # error on type mismatch
                
                entry.value = value
            
            # if we're the server, an id if it doesn't have one
            if self.m_server and entry.id == 0xffff:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)
            
            # update persistent dirty flag if value changed and it's persistent
            if entry.isPersistent() and old_value != value:
                self.m_persistent_dirty = True
            
            # notify (for local listeners)
            if self.m_notifier.m_local_notifiers:
                if old_value is None:
                    self.m_notifier.notifyEntry(name, value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)
        
                elif old_value != value:
                    self.m_notifier.notifyEntry(name, value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)
            
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return True
        
            msg = None
            
            if old_value is None:
                msg = Message.entryAssign(name, entry.id, entry.seq_num,
                                                value, entry.flags)
        
            elif old_value != value:
                entry.increment_seqnum()
                
                # don't send an update if we don't have an assigned id yet
                if entry.id != 0xffff:
                    msg = Message.entryUpdate(entry.id, entry.seq_num, value)
        
        # unlocked mutex
        if msg:
            queue_outgoing(msg, None, None)
            
        return True
    
    def setEntryTypeValue(self, name, value):
        if not name:
            return
    
        if not value:
            return
    
        with self.m_mutex:
            entry = self.m_entries.get(name)
            if not entry:
                old_value = None
                entry = _Entry(name, value)
                self.m_entries[name] = entry
            else:
                old_value = entry.value
                if old_value == value:
                    return
                
                entry.value = value
            
            # if we're the server, an id if it doesn't have one
            if self.m_server and entry.id == 0xffff:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)
            
            # update persistent dirty flag if it's a persistent value
            if entry.isPersistent():
                self.m_persistent_dirty = True
            
            # notify (for local listeners)
            if self.m_notifier.m_local_notifiers:
                if old_value is None:
                    self.m_notifier.notifyEntry(name, value, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)
        
                else:
                    self.m_notifier.notifyEntry(name, value, NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL)
            
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return
            
            msg = None
            
            if old_value is None or old_value.type != value.type:
                entry.increment_seqnum()
                
                msg = Message.entryAssign(name, entry.id, entry.seq_num,
                                                value, entry.flags)
            else:
                entry.increment_seqnum()
                
                # don't send an update if we don't have an assigned id yet
                if entry.id != 0xffff:
                    msg = Message.entryUpdate(entry.id, entry.seq_num, value)
            
        # unlocked mutex
        if msg:
            queue_outgoing(msg, None, None)
    
    def setEntryFlags(self, name, flags):
        if not name:
            return
    
        with self.m_mutex:
            entry = self.m_entries.get(name)
            if not entry:
                return
        
            if entry.flags == flags:
                return
            
            # update persistent dirty flag if persistent flag changed
            if (entry.flags & NT_PERSISTENT) != (flags & NT_PERSISTENT):
                self.m_persistent_dirty = True
            
            entry.flags = flags
        
            # notify
            self.m_notifier.notifyEntry(name, entry.value, NT_NOTIFY_FLAGS | NT_NOTIFY_LOCAL)
        
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return
            
            entry_id = entry.id
            
        # don't send an update if we don't have an assigned id yet
        if entry_id != 0xffff:
            queue_outgoing(Message.flagsUpdate(entry_id, flags), None, None)
    
    def getEntryFlags(self, name):
        with self.m_mutex:
            entry = self.m_entries.get(name)
            return entry.flags if entry else 0
    
    def deleteEntry(self, name):
        with self.m_mutex:
            entry = self.m_entries.pop(name, None)
            if not entry:
                return
        
            entry_id = entry.id
        
            # update persistent dirty flag if it's a persistent value
            if entry.isPersistent():
                self.m_persistent_dirty = True
            
            if entry_id < len(self.m_idmap):
                self.m_idmap[entry_id] = None
            
            if not entry.value:
                return
            
            # notify
            self.m_notifier.notifyEntry(name, entry.value,
                                        NT_NOTIFY_DELETE | NT_NOTIFY_LOCAL)
        
            # if it had a value, message
            # don't send an update if we don't have an assigned id yet
            queue_outgoing = self.m_queue_outgoing
            
        if entry_id != 0xffff and queue_outgoing:
            queue_outgoing(Message.entryDelete(entry_id), None, None)
    
    def _deleteAllEntriesImpl(self):
        if not self.m_entries:
            return
    
        # only delete non-persistent values
        # can't erase without invalidating iterators, grab a list of keys
        for k in list(self.m_entries.keys()):
            entry = self.m_entries.get(k)
            if not entry.isPersistent():
                # notify it's being deleted
                if self.m_notifier.m_local_notifiers:
                    self.m_notifier.notifyEntry(k, entry,
                                                NT_NOTIFY_DELETE | NT_NOTIFY_LOCAL)
    
                # remove it from idmap
                if entry.id != 0xffff:
                    self.m_idmap[entry.id] = None
            
                # Delete it
                self.m_entries.pop(k)
    
    def deleteAllEntries(self):
        with self.m_mutex:
            if not self.m_entries:
                return
        
            self._deleteAllEntriesImpl()
        
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return
        
        queue_outgoing(Message.clearEntries(), None, None)
    
    def getEntryInfo(self, prefix, types):
        with self.m_mutex:
            infos = []
            types = types if isinstance(types, int) else ord(types)
            for k, entry in self.m_entries.items():
                if not k.startswith(prefix):
                    continue
                
                value = entry.value
                if not value:
                    continue
        
                if types != 0 and (types & ord(value.type)) == 0:
                    continue
        
                info = EntryInfo(entry.name, value.type, entry.flags)
                infos.append(info)
        
            return infos
    
    def notifyEntries(self, prefix, only):
        with self.m_mutex:
            
            for k, entry in self.m_entries.items():
                if not k.startswith(prefix):
                    continue
                
                self.m_notifier.notifyEntry(k, entry.value, NT_NOTIFY_IMMEDIATE,
                                            only)
    
    def _putPersistentEntries(self, entries):
        
        msgs = []
        
        # copy values into storage as quickly as possible so lock isn't held
        with self.m_mutex:
            queue_outgoing = self.m_queue_outgoing
            for name, value in entries:
                entry = self.m_entries.get(name)
                if not entry:
                    entry = _Entry(name)
                    self.m_entries[name] = entry
    
                old_value = entry.value
                entry.value = value
                was_persist = entry.isPersistent()
                if not was_persist:
                    entry.flags |= NT_PERSISTENT
                
                # if we're the server, an id if it doesn't have one
                if self.m_server and entry.id == 0xffff:
                    entry.id = len(self.m_idmap)
                    self.m_idmap.append(entry)
                
                # notify (for local listeners)
                if self.m_notifier.m_local_notifiers:
                    if old_value is None:
                        self.m_notifier.notifyEntry(name, value,
                                                    NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)
                    elif old_value != value:
                        notify_flags = NT_NOTIFY_UPDATE | NT_NOTIFY_LOCAL
                        if not was_persist:
                            notify_flags |= NT_NOTIFY_FLAGS
    
                        self.m_notifier.notifyEntry(name, value, notify_flags)
    
                if not queue_outgoing:
                    continue    # shortcut
    
                entry.increment_seqnum()
    
                # put on update queue
                if old_value is None or old_value.type != value.type:
                    msgs.append(Message.entryAssign(name, entry.id,
                                                    entry.seq_num,
                                                    value, entry.flags))
                elif entry.id != 0xffff:
                    # don't send an update if we don't have an assigned id yet
                    if old_value != value:
                        msgs.append(Message.entryUpdate(entry.id, entry.seq_num, value))
                    if not was_persist:
                        msgs.append(Message.flagsUpdate(entry.id, entry.flags))
            
        if queue_outgoing:
            for msg in msgs:
                queue_outgoing(msg, None, None)
    
    def _getPersistentEntries(self, periodic):
        
        # copy values out of storage as quickly as possible so lock isn't held
        with self.m_mutex:
            if periodic and not self.m_persistent_dirty:
                return False
            
            self.m_persistent_dirty = False
            
            entries = [(entry.name, entry.value) for entry in self.m_entries.values() \
                       if entry.isPersistent()]
        
        # sort in name order
        entries.sort()
        return entries
    
    def loadPersistent(self, filename=None, fp=None):
        try:
            if fp:
                entries = load_entries(fp, filename if filename else '<string>')
            else:
                with open(filename, 'r') as fp:
                    entries = load_entries(fp, filename)
        except IOError as e:
            return 'Error reading file: %s' % e
        else:
            self._putPersistentEntries(entries)
            return
    
    def savePersistent(self, filename=None, periodic=False, fp=None):
        with self.m_persistence_save_lock:
            entries = self._getPersistentEntries(periodic)
            if entries is False:
                return
        
            # Going to not use tempfile to keep compatibility with ntcore,
            # as having to cleanup temp files on the RIO is probably bad
            if fp:
                save_entries(fp, entries)
            else:
                tmp = '%s.tmp' % filename
                bak = '%s.bak' % filename
                
                try:
                    with open(tmp, 'w') as fp:
                        save_entries(fp, entries)
                        os.fsync(fp.fileno())
                except IOError as e:
                    return 'Error writing file: %s' % e
                
                try:
                    file_replace(filename, bak)
                except OSError:
                    pass # ignored
                    
                try:
                    file_replace(tmp, filename)
                except OSError as e:
                    try:
                        # try to restore backup
                        file_replace(bak, filename)
                    except OSError:
                        pass
                        
                    return 'Could not rename temp file to real file: %s' % e
            
            self.m_persistent_dirty = False
    
    def createRpc(self, name, defn, callback):
        if not name or defn or not callback:
            return
    
        with self.m_mutex:
            if not self.m_server:
                return    # only server can create RPCs
            
            entry = self.m_entries.get(name)
            if not entry:
                entry = _Entry(name)
                self.m_entries[name] = entry
            
            old_value = entry.value
            value = Value.makeRpc(defn)
            entry.value = value
        
            # set up the callback
            entry.rpc_callback = callback
        
            # start the RPC server
            self.m_rpc_server.start()
        
            if old_value == value:
                return
            
            # assign an id if it doesn't have one
            if entry.id == 0xffff:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)
            
            # generate message
            if not self.m_queue_outgoing:
                return
        
            queue_outgoing = self.m_queue_outgoing
            msg = None
            
            if old_value is None or old_value.type != value.type:
                entry.increment_seqnum()
                msg = Message.entryAssign(name, entry.id, entry.seq_num,
                                                value, entry.flags)
            else:
                entry.increment_seqnum()
                msg = Message.entryUpdate(entry.id, entry.seq_num, value)
                
        # unlocked mutex
        if msg:
            queue_outgoing(msg, None, None)
    
    def createPolledRpc(self, name, defn):
        if not name or not defn:
            return
        
        with self.m_mutex:
            if not self.m_server:
                return    # only server can create RPCs
            
            entry = self.m_entries.get(name)
            if not entry:
                entry = _Entry(name)
                self.m_entries[name] = entry
            
            old_value = entry.value
            value = Value.makeRpc(defn)
            entry.value = value
        
            # a None callback indicates a polled RPC
            entry.rpc_callback = None
        
            if old_value == value:
                return
            
            # assign an id if it doesn't have one
            if entry.id == 0xffff:
                entry.id = len(self.m_idmap)
                self.m_idmap.append(entry)
            
            # generate message
            queue_outgoing = self.m_queue_outgoing
            if not queue_outgoing:
                return
            
            msg = None
            
            if old_value is None or old_value.type != value.type:
                entry.increment_seqnum()
                msg = Message.entryAssign(name, entry.id, entry.seq_num,
                                                value, entry.flags)
            else:
                entry.increment_seqnum()
                msg = Message.entryUpdate(entry.id, entry.seq_num, value)
                
        # unlocked mutex
        if msg:
            queue_outgoing(msg, None, None)
    
    def callRpc(self, name, params):
        self.m_mutex.acquire()
        locked = True
        try:
            entry = self.m_entries.get(name)
            if not entry:
                return 0
            
            if not entry.value.isRpc():
                return 0
        
            entry.rpc_call_uid += 1
            entry.rpc_call_uid &= 0xffff
            
            combined_uid = (entry.id << 16) | entry.rpc_call_uid
            msg = Message.executeRpc(entry.id, entry.rpc_call_uid, params)
            if self.m_server:
                # RPCs are unlikely to be used locally on the server, handle it
                # gracefully anyway.
                rpc_callback = entry.rpc_callback
                
                self.m_mutex.release()
                locked = False
                
                conn_info = ConnectionInfo('Server', 'localhost', 0, monotonic(), 0x0300)
                self.m_rpc_server.processRpc(name, msg, rpc_callback, 0xffff,
                                             self._process_rpc, conn_info)
            else:
                queue_outgoing = self.m_queue_outgoing
                
                self.m_mutex.release()
                locked = False
                
                queue_outgoing(msg, None, None)
        
            return combined_uid
        finally:
            if locked:
                self.m_mutex.release()
    
    def _process_rpc(self, msg):
        with self.m_mutex:
            self.m_rpc_results[(msg.id, msg.seq_num_uid)] = msg.str
            self.m_rpc_results_cond.notify_all()
    
    def getRpcResult(self, blocking, call_uid, time_out=-1):
        with self.m_mutex:
            # only allow one blocking call per rpc call uid
            if call_uid in self.m_rpc_blocking_calls:
                return False, None
        
            self.m_rpc_blocking_calls.add(call_uid)
            wait_until = monotonic() + time_out
        
            try:
                while True:
                    result = self.m_rpc_results.get(call_uid) 
                    if not result:
                        if not blocking or self.m_terminating:
                            return False, None
            
                        if time_out <= 0:
                            self.m_rpc_results_cond.wait()
                        else:
                            ttw = monotonic() - wait_until
                            if ttw <= 0:
                                return False, None
                            
                            self.m_rpc_results_cond.wait(ttw)
            
                        # if element does not exist, have been canceled
                        if call_uid not in self.m_rpc_blocking_calls:
                            return False, None
            
                        if self.m_terminating:
                            return False, None
            
                        continue
                    
                    self.m_rpc_results.pop(call_uid, None)
                    return True, result
            finally:
                try:
                    self.m_rpc_blocking_calls.remove(call_uid)
                except KeyError:
                    pass
    
    def cancelBlockingRpcResult(self, call_uid):
        with self.m_mutex:
            # safe to erase even if id does not exist
            self.m_rpc_blocking_calls.erase(call_uid)
            self.m_rpc_results_cond.notify_all()
    
    
    
   

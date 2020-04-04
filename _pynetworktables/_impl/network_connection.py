# validated: 2017-09-28 DS cedbafeb286d cpp/NetworkConnection.cpp cpp/NetworkConnection.h cpp/INetworkConnection.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

import threading
from time import monotonic

try:
    # Python 3.7 only, should be more efficient
    from queue import SimpleQueue as Queue, Empty
except ImportError:
    from queue import Queue, Empty


from .constants import (
    kEntryAssign,
    kEntryUpdate,
    kFlagsUpdate,
    kEntryDelete,
    kClearEntries,
    msgtype_str,
)

from .message import Message
from .structs import ConnectionInfo
from .wire import WireCodec

from .support.lists import Pair
from .support.safe_thread import SafeThread

from .tcpsockets.tcp_stream import StreamEOF

import logging

logger = logging.getLogger("nt")

_empty_pair = Pair(0, 0)

_state_map = {
    0: "created",
    1: "init",
    2: "handshake",
    3: "synchronized",
    4: "active",
    5: "dead",
}


class NetworkConnection(object):
    class State(object):
        kCreated = 0
        kInit = 1
        kHandshake = 2
        kSynchronized = 3
        kActive = 4
        kDead = 5

    def __init__(self, uid, stream, notifier, handshake, get_entry_type, verbose=False):

        # logging debugging
        self.m_verbose = verbose

        self.m_uid = uid
        self.m_stream = stream
        self.m_notifier = notifier
        self.m_handshake = handshake
        self.m_get_entry_type = get_entry_type

        self.m_active = False
        self.m_proto_rev = 0x0300
        self.state = self.State.kCreated
        self.m_state_mutex = threading.Lock()
        self.m_last_update = 0

        self.m_outgoing = Queue()

        self.m_process_incoming = None
        self.m_read_thread = None
        self.m_write_thread = None

        self.m_remote_id_mutex = threading.Lock()
        self.m_remote_id = None
        self.m_last_post = 0

        self.m_pending_mutex = threading.Lock()
        self.m_pending_outgoing = []
        self.m_pending_update = {}

        # Condition variables for shutdown
        self.m_shutdown_mutex = threading.Lock()
        # Not needed in python
        # self.m_read_shutdown_cv = threading.Condition()
        # self.m_write_shutdown_cv = threading.Condition()
        self.m_read_shutdown = False
        self.m_write_shutdown = False

        # turn off Nagle algorithm; we bundle packets for transmission
        try:
            self.m_stream.setNoDelay()
        except IOError as e:
            logger.warning("Setting TCP_NODELAY: %s", e)

    def start(self):
        if self.m_active:
            return

        self.m_active = True
        self.set_state(self.State.kInit)

        # clear queue
        try:
            while True:
                self.m_outgoing.get_nowait()
        except Empty:
            pass

        # reset shutdown flags
        with self.m_shutdown_mutex:
            self.m_read_shutdown = False
            self.m_write_shutdown = False

        # start threads
        self.m_write_thread = SafeThread(
            target=self._writeThreadMain, name="nt-net-write"
        )
        self.m_read_thread = SafeThread(target=self._readThreadMain, name="nt-net-read")

    def __repr__(self):
        try:
            return "<NetworkConnection 0x%x %s>" % (id(self), self.info())
        except Exception:
            return "<NetworkConnection 0x%x ???>" % id(self)

    def stop(self):
        logger.debug("NetworkConnection stopping (%s)", self)

        if not self.m_active:
            return

        self.set_state(self.State.kDead)
        self.m_active = False
        # closing the stream so the read thread terminates
        self.m_stream.close()

        # send an empty outgoing message set so the write thread terminates
        self.m_outgoing.put([])

        # wait for threads to terminate, timeout
        self.m_write_thread.join(1)
        if self.m_write_thread.is_alive():
            logger.warning("%s did not die", self.m_write_thread.name)

        self.m_read_thread.join(1)
        if self.m_read_thread.is_alive():
            logger.warning("%s did not die", self.m_write_thread.name)

        # clear queue
        try:
            while True:
                self.m_outgoing.get_nowait()
        except Empty:
            pass

    def get_proto_rev(self):
        return self.m_proto_rev

    def get_stream(self):
        return self.m_stream

    def info(self):
        return ConnectionInfo(
            self.remote_id(),
            self.m_stream.getPeerIP(),
            self.m_stream.getPeerPort(),
            self.m_last_update,
            self.m_proto_rev,
        )

    def is_connected(self):
        return self.state == self.State.kActive

    def last_update(self):
        return self.m_last_update

    def set_process_incoming(self, func):
        self.m_process_incoming = func

    def set_proto_rev(self, proto_rev):
        self.m_proto_rev = proto_rev

    def set_state(self, state):
        with self.m_state_mutex:
            State = self.State

            # Don't update state any more once we've died
            if self.state == State.kDead:
                return

            # One-shot notify state changes
            if self.state != State.kActive and state == State.kActive:
                info = self.info()
                self.m_notifier.notifyConnection(True, info)
                logger.info(
                    "CONNECTED %s port %s (%s)",
                    info.remote_ip,
                    info.remote_port,
                    info.remote_id,
                )
            elif self.state != State.kDead and state == State.kDead:
                info = self.info()
                self.m_notifier.notifyConnection(False, info)
                logger.info(
                    "DISCONNECTED %s port %s (%s)",
                    info.remote_ip,
                    info.remote_port,
                    info.remote_id,
                )

            if self.m_verbose:
                logger.debug(
                    "%s: %s -> %s", self, _state_map[self.state], _state_map[state]
                )

            self.state = state

    # python optimization: don't use getter here
    # def state(self):
    #     return self.m_state

    def remote_id(self):
        with self.m_remote_id_mutex:
            return self.m_remote_id

    def set_remote_id(self, remote_id):
        with self.m_remote_id_mutex:
            self.m_remote_id = remote_id

    def uid(self):
        return self.m_uid

    def _sendMessages(self, msgs):
        self.m_outgoing.put(msgs)

    def _readThreadMain(self):
        decoder = WireCodec(self.m_proto_rev)

        verbose = self.m_verbose

        def _getMessage():
            decoder.set_proto_rev(self.m_proto_rev)
            try:
                return Message.read(self.m_stream, decoder, self.m_get_entry_type)
            except IOError as e:
                logger.warning("read error in handshake: %s", e)

                # terminate connection on bad message
                self.m_stream.close()

                return None

        self.set_state(self.State.kHandshake)

        try:
            handshake_success = self.m_handshake(self, _getMessage, self._sendMessages)
        except Exception:
            logger.exception("Unhandled exception during handshake")
            handshake_success = False

        if not handshake_success:
            self.set_state(self.State.kDead)
            self.m_active = False
        else:
            self.set_state(self.State.kActive)

            try:
                while self.m_active:
                    if not self.m_stream:
                        break

                    decoder.set_proto_rev(self.m_proto_rev)

                    try:
                        msg = Message.read(
                            self.m_stream, decoder, self.m_get_entry_type
                        )
                    except Exception as e:
                        if not isinstance(e, StreamEOF):
                            if verbose:
                                logger.exception("read error")
                            else:
                                logger.warning("read error: %s", e)

                        # terminate connection on bad message
                        self.m_stream.close()

                        break

                    if verbose:
                        logger.debug(
                            "%s received type=%s with str=%s id=%s seq_num=%s value=%s",
                            self.m_stream.sock_type,
                            msgtype_str(msg.type),
                            msg.str,
                            msg.id,
                            msg.seq_num_uid,
                            msg.value,
                        )

                    self.m_last_update = monotonic()
                    self.m_process_incoming(msg, self)
            except IOError as e:
                # connection died probably
                logger.debug("IOError in read thread: %s", e)
            except Exception:
                logger.warning("Unhandled exception in read thread", exc_info=True)

            self.set_state(self.State.kDead)
            self.m_active = False

        # also kill write thread
        self.m_outgoing.put([])

        with self.m_shutdown_mutex:
            self.m_read_shutdown = True

    def _writeThreadMain(self):
        encoder = WireCodec(self.m_proto_rev)

        verbose = self.m_verbose
        out = []

        try:
            while self.m_active:
                msgs = self.m_outgoing.get()

                if verbose:
                    logger.debug("write thread woke up")
                    if msgs:
                        logger.debug(
                            "%s sending %s messages", self.m_stream.sock_type, len(msgs)
                        )

                if not msgs:
                    continue

                encoder.set_proto_rev(self.m_proto_rev)

                # python-optimization: checking verbose causes extra overhead
                if verbose:
                    for msg in msgs:
                        if msg:
                            logger.debug(
                                "%s sending type=%s with str=%s id=%s seq_num=%s value=%s",
                                self.m_stream.sock_type,
                                msgtype_str(msg.type),
                                msg.str,
                                msg.id,
                                msg.seq_num_uid,
                                msg.value,
                            )
                            msg.write(out, encoder)
                else:
                    for msg in msgs:
                        if msg:
                            msg.write(out, encoder)

                if not self.m_stream:
                    break

                if not out:
                    continue

                self.m_stream.send(b"".join(out))

                del out[:]

                # if verbose:
                #    logger.debug('send %s bytes', encoder.size())
        except IOError as e:
            # connection died probably
            if not isinstance(e, StreamEOF):
                logger.debug("IOError in write thread: %s", e)
        except Exception:
            logger.warning("Unhandled exception in write thread", exc_info=True)

        self.set_state(self.State.kDead)
        self.m_active = False
        self.m_stream.close()  # also kill read thread

        with self.m_shutdown_mutex:
            self.m_write_shutdown = True

    def queueOutgoing(self, msg):
        with self.m_pending_mutex:

            # Merge with previous.  One case we don't combine: delete/assign loop.
            msgtype = msg.type
            if msgtype in [kEntryAssign, kEntryUpdate]:

                # don't do this for unassigned id's
                msg_id = msg.id
                if msg_id == 0xFFFF:
                    self.m_pending_outgoing.append(msg)
                    return

                mpend = self.m_pending_update.get(msg_id)
                if mpend is not None and mpend.first != 0:
                    # overwrite the previous one for this id
                    oldidx = mpend.first - 1
                    oldmsg = self.m_pending_outgoing[oldidx]
                    if (
                        oldmsg
                        and oldmsg.type == kEntryAssign
                        and msgtype == kEntryUpdate
                    ):
                        # need to update assignment with seq_num and value
                        oldmsg = Message.entryAssign(
                            oldmsg.str, msg_id, msg.seq_num_uid, msg.value, oldmsg.flags
                        )

                    else:
                        oldmsg = msg  # easy update

                    self.m_pending_outgoing[oldidx] = oldmsg

                else:
                    # new, remember it
                    pos = len(self.m_pending_outgoing)
                    self.m_pending_outgoing.append(msg)
                    self.m_pending_update[msg_id] = Pair(pos + 1, 0)

            elif msgtype == kEntryDelete:
                # don't do this for unassigned id's
                msg_id = msg.id
                if msg_id == 0xFFFF:
                    self.m_pending_outgoing.append(msg)
                    return

                # clear previous updates
                mpend = self.m_pending_update.get(msg_id)
                if mpend is not None:
                    if mpend.first != 0:
                        self.m_pending_outgoing[mpend.first - 1] = None

                    if mpend.second != 0:
                        self.m_pending_outgoing[mpend.second - 1] = None

                    self.m_pending_update[msg_id] = _empty_pair

                # add deletion
                self.m_pending_outgoing.append(msg)

            elif msgtype == kFlagsUpdate:
                # don't do this for unassigned id's
                msg_id = msg.id
                if id == 0xFFFF:
                    self.m_pending_outgoing.append(msg)
                    return

                mpend = self.m_pending_update.get(msg_id)
                if mpend is not None and mpend.second != 0:
                    # overwrite the previous one for this id
                    self.m_pending_outgoing[mpend.second - 1] = msg

                else:
                    # new, remember it
                    pos = len(self.m_pending_outgoing)
                    self.m_pending_outgoing.append(msg)
                    self.m_pending_update[msg_id] = Pair(0, pos + 1)

            elif msgtype == kClearEntries:
                # knock out all previous assigns/updates!
                for i, m in enumerate(self.m_pending_outgoing):
                    if not m:
                        continue

                    t = m.type
                    if t in [
                        kEntryAssign,
                        kEntryUpdate,
                        kFlagsUpdate,
                        kEntryDelete,
                        kClearEntries,
                    ]:
                        self.m_pending_outgoing[i] = None

                self.m_pending_update.clear()
                self.m_pending_outgoing.append(msg)

            else:
                self.m_pending_outgoing.append(msg)

    def postOutgoing(self, keep_alive):
        with self.m_pending_mutex:
            # optimization: don't call monotonic unless needed
            # now = monotonic()
            if not self.m_pending_outgoing:
                if not keep_alive:
                    return

                # send keep-alives once a second (if no other messages have been sent)
                now = monotonic()
                if (now - self.m_last_post) < 1.0:
                    return

                self.m_outgoing.put((Message.keepAlive(),))

            else:
                now = monotonic()
                self.m_outgoing.put(self.m_pending_outgoing)

                self.m_pending_outgoing = []
                self.m_pending_update.clear()

            self.m_last_post = now

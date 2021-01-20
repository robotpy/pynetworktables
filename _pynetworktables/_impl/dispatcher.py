# validated: 2019-01-04 DS ceed1d74dc30 cpp/Dispatcher.cpp cpp/Dispatcher.h cpp/IDispatcher.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

import threading
import time

from .message import Message
from .network_connection import NetworkConnection

from .tcpsockets.tcp_acceptor import TcpAcceptor
from .tcpsockets.tcp_connector import TcpConnector

from .support.safe_thread import SafeThread

from .constants import (
    kKeepAlive,
    kClientHello,
    kProtoUnsup,
    kServerHello,
    kServerHelloDone,
    kClientHelloDone,
    kEntryAssign,
    NT_NET_MODE_NONE,
    NT_NET_MODE_SERVER,
    NT_NET_MODE_CLIENT,
    NT_NET_MODE_STARTING,
    NT_NET_MODE_FAILURE,
    NT_NET_MODE_TEST,
)

import logging

logger = logging.getLogger("nt")


class Dispatcher(object):
    def __init__(self, storage, conn_notifier, verbose=False):

        # logging debugging
        self.m_verbose = verbose

        self.m_storage = storage
        self.m_notifier = conn_notifier
        self.m_networkMode = NT_NET_MODE_NONE
        self.m_persist_filename = None
        self.m_server_acceptor = None
        self.m_client_connector_override = None
        self.m_client_connector = None
        self.m_connections_uid = 0

        self.m_default_proto = 0x0300  # for testing

        # Mutex for user-accessible items
        self.m_user_mutex = threading.RLock()
        self.m_connections = []

        # Circular import issue
        try:
            from .version import __version__
        except ImportError:
            __version__ = "[unknown version]"

        self.m_identity = "pynetworktables %s" % __version__

        self.m_active = False  # set to false to terminate threads
        self.m_update_rate = 0.050  # periodic dispatch rate, in s

        # Condition variable for forced dispatch wakeup (flush)
        self.m_flush_mutex = threading.Lock()
        self.m_flush_cv = threading.Condition(self.m_flush_mutex)
        self.m_last_flush = 0
        self.m_do_flush = False

        # Condition variable for client reconnect (uses user mutex)
        self.m_reconnect_cv = threading.Condition(self.m_user_mutex)
        self.m_reconnect_proto_rev = self.m_default_proto
        self.m_do_reconnect = True

    def setVerboseLogging(self, verbose):
        self.m_verbose = verbose

    def setServer(self, server_or_servers):
        """
        :param server_or_servers: a tuple of (server, port) or a list of tuples of (server, port)
        """
        self._setConnector(server_or_servers)

    def setServerTeam(self, team, port):
        servers = [
            "10.%d.%d.2" % (team / 100, team % 100),
            "roboRIO-%d-FRC.local" % team,
            "172.22.11.2",
            "roboRIO-%d-FRC.lan" % team,
            "roboRIO-%d-FRC.frc-field.local" % team,
        ]
        self.setServer([(s, port) for s in servers])

    def setServerOverride(self, server, port):
        self._setConnectorOverride((server, port))

    def clearServerOverride(self):
        self._clearConnectorOverride()

    def getNetworkMode(self):
        return self.m_networkMode

    # python-specific
    def startTestMode(self, is_server):
        with self.m_user_mutex:
            if self.m_active:
                return False
            self.m_active = True

            if is_server:
                self.m_networkMode = NT_NET_MODE_SERVER | NT_NET_MODE_TEST
            else:
                self.m_networkMode = NT_NET_MODE_CLIENT | NT_NET_MODE_TEST

        return True

    def startServer(self, persist_filename, listen_address, port):

        with self.m_user_mutex:
            if self.m_active:
                return False
            self.m_active = True

        logger.info("NetworkTables initialized in server mode")

        acceptor = TcpAcceptor(port, listen_address.strip())

        self.m_networkMode = NT_NET_MODE_SERVER | NT_NET_MODE_STARTING
        self.m_persist_filename = persist_filename
        self.m_server_acceptor = acceptor

        # Load persistent file.  Ignore errors, pass along warnings.
        if self.m_verbose:
            logger.debug("persistent filename is %s", persist_filename)

        if persist_filename:
            self.m_storage.loadPersistent(persist_filename)

        self.m_storage.setDispatcher(self, True)

        self.m_dispatch_thread = SafeThread(
            target=self._dispatchThreadMain, name="nt-dispatch-thread"
        )
        self.m_clientserver_thread = SafeThread(
            target=self._serverThreadMain, name="nt-server-thread"
        )
        return True

    def startClient(self):
        with self.m_user_mutex:
            if self.m_active:
                return False
            self.m_active = True

        logger.info("NetworkTables initialized in client mode")

        self.m_networkMode = NT_NET_MODE_CLIENT | NT_NET_MODE_STARTING
        self.m_storage.setDispatcher(self, False)

        self.m_dispatch_thread = SafeThread(
            target=self._dispatchThreadMain, name="nt-dispatch-thread"
        )
        self.m_clientserver_thread = SafeThread(
            target=self._clientThreadMain, name="nt-client-thread"
        )

        return False

    def stop(self):
        with self.m_user_mutex:
            if not self.m_active:
                return

            self.m_active = False

            # python-specific
            if self.m_networkMode & NT_NET_MODE_TEST != 0:
                return

        # wake up dispatch thread with a flush
        with self.m_flush_mutex:
            self.m_flush_cv.notify()

        # wake up client thread with a reconnect
        with self.m_user_mutex:
            self.m_client_connector = None

        self._clientReconnect()

        # wake up server thread by shutting down the socket
        if self.m_server_acceptor:
            self.m_server_acceptor.shutdown()

        # join threads, timeout
        self.m_dispatch_thread.join(1)
        self.m_clientserver_thread.join(1)

        with self.m_user_mutex:
            conns = self.m_connections
            self.m_connections = []

        # close all connections
        for conn in conns:
            conn.stop()

        # cleanup the server socket
        # -> needed because we don't have destructors
        if self.m_server_acceptor:
            self.m_server_acceptor.close()

    def setUpdateRate(self, interval):
        # don't allow update rates faster than 10 ms or slower than 1 second
        interval = float(interval)

        if interval < 0.01:
            interval = 0.01

        elif interval > 1.0:
            interval = 1.0

        self.m_update_rate = interval

    def setIdentity(self, name):
        with self.m_user_mutex:
            self.m_identity = name

    def setDefaultProtoRev(self, proto_rev):
        self.m_default_proto = proto_rev
        self.m_reconnect_proto_rev = proto_rev

    def flush(self):
        now = time.monotonic()
        with self.m_flush_mutex:
            # don't allow flushes more often than every 10 ms
            if (now - self.m_last_flush) < 0.010:
                return

            self.m_last_flush = now
            self.m_do_flush = True

            self.m_flush_cv.notify()

    def getConnections(self):
        conns = []
        if not self.m_active:
            return conns

        with self.m_user_mutex:
            for conn in self.m_connections:
                if conn.state != NetworkConnection.State.kActive:
                    continue

                conns.append(conn.info())

        return conns

    def isConnected(self):
        if self.m_active:
            with self.m_user_mutex:
                for conn in self.m_connections:
                    if conn.is_connected():
                        return True
        return False

    def isServer(self):
        return (self.m_networkMode & NT_NET_MODE_SERVER) != 0

    def addListener(self, callback, immediate_notify):
        with self.m_user_mutex:
            uid = self.m_notifier.add(callback)
            # perform immediate notifications
            if immediate_notify:
                for conn in self.m_connections:
                    if conn.is_connected():
                        self.m_notifier.notifyConnection(True, conn.info(), uid)
        return uid

    def addPolledListener(self, poller_uid, immediate_notify):
        with self.m_user_mutex:
            uid = self.m_notifier.addPolled(poller_uid)
            # perform immediate notifications
            if immediate_notify:
                for conn in self.m_connections:
                    if conn.is_connected():
                        self.m_notifier.notifyConnection(True, conn.info(), uid)
        return uid

    def _strip_connectors(self, connector):
        if isinstance(connector, tuple):
            server, port = connector
            return (server.strip(), port)
        else:
            return [(server.strip(), port) for server, port in connector]

    def _setConnector(self, connector):
        with self.m_user_mutex:
            self.m_client_connector = self._strip_connectors(connector)

    def _setConnectorOverride(self, connector):
        with self.m_user_mutex:
            self.m_client_connector_override = self._strip_connectors(connector)

    def _clearConnectorOverride(self):
        with self.m_user_mutex:
            self.m_client_connector_override = None

    def _dispatchWaitFor(self):
        return not self.m_active or self.m_do_flush

    def _dispatchThreadMain(self):
        timeout_time = time.monotonic()

        save_delta_time = 1.0
        next_save_time = timeout_time + save_delta_time

        count = 0
        is_server = self.m_networkMode & NT_NET_MODE_SERVER
        verbose = self.m_verbose

        # python micro-optimizations because this is a loop
        monotonic = time.monotonic
        kActive = NetworkConnection.State.kActive
        kDead = NetworkConnection.State.kDead

        while self.m_active:
            # handle loop taking too long
            start = monotonic()
            if start > timeout_time or timeout_time > start + self.m_update_rate:
                timeout_time = start

            # wait for periodic or when flushed
            timeout_time += self.m_update_rate
            with self.m_flush_mutex:
                self.m_flush_cv.wait_for(self._dispatchWaitFor, timeout_time - start)
                self.m_do_flush = False

            # in case we were woken up to terminate
            if not self.m_active:
                break

            # perform periodic persistent save
            if is_server and self.m_persist_filename and start > next_save_time:
                next_save_time += save_delta_time
                # handle loop taking too long
                if start > next_save_time:
                    next_save_time = start + save_delta_time

                err = self.m_storage.savePersistent(self.m_persist_filename, True)
                if err:
                    logger.warning("periodic persistent save: %s", err)

            with self.m_user_mutex:
                reconnect = False

                if verbose:
                    count += 1
                    if count > 10:
                        logger.debug(
                            "dispatch running %s connections", len(self.m_connections)
                        )
                        count = 0

                for conn in self.m_connections:
                    # post outgoing messages if connection is active
                    # only send keep-alives on client
                    state = conn.state
                    if state == kActive:
                        conn.postOutgoing(not is_server)

                    # if client, if connection died
                    if not is_server and state == kDead:
                        reconnect = True

                # reconnect if we disconnected (and a reconnect is not in progress)
                if reconnect and not self.m_do_reconnect:
                    self.m_do_reconnect = True
                    self.m_reconnect_cv.notify()

    def _queueOutgoing(self, msg, only, except_):
        with self.m_user_mutex:
            for conn in self.m_connections:
                if conn == except_:
                    continue

                if only and conn != only:
                    continue

                state = conn.state
                if (
                    state != NetworkConnection.State.kSynchronized
                    and state != NetworkConnection.State.kActive
                ):
                    continue

                conn.queueOutgoing(msg)

    def _serverThreadMain(self):
        if not self.m_server_acceptor.start():
            self.m_active = False
            self.m_networkMode = NT_NET_MODE_SERVER | NT_NET_MODE_FAILURE
            return

        self.m_networkMode = NT_NET_MODE_SERVER

        try:
            while self.m_active:
                stream = self.m_server_acceptor.accept()
                if not stream:
                    self.m_active = False
                    return

                if not self.m_active:
                    return

                logger.debug(
                    "server: client connection from %s port %s",
                    stream.getPeerIP(),
                    stream.getPeerPort(),
                )

                # add to connections list
                connection_uid = self.m_connections_uid
                self.m_connections_uid += 1
                conn = NetworkConnection(
                    connection_uid,
                    stream,
                    self.m_notifier,
                    self._serverHandshake,
                    self.m_storage.getMessageEntryType,
                    verbose=self.m_verbose,
                )

                conn.set_process_incoming(self.m_storage.processIncoming)

                with self.m_user_mutex:
                    # reuse dead connection slots
                    for i in range(len(self.m_connections)):
                        c = self.m_connections[i]
                        if c.state == NetworkConnection.State.kDead:
                            self.m_connections[i] = conn
                            break
                    else:
                        self.m_connections.append(conn)

                    conn.start()
        finally:
            self.m_networkMode = NT_NET_MODE_NONE

    def _clientThreadMain(self):
        try:
            tcp_connector = TcpConnector(1, self.m_verbose)

            while self.m_active:
                # sleep between retries
                time.sleep(0.250)
                tcp_connector.setVerbose(self.m_verbose)

                # get next server to connect to
                with self.m_user_mutex:
                    if self.m_client_connector_override:
                        server_or_servers = self.m_client_connector_override
                    else:
                        if not self.m_client_connector:
                            self.m_networkMode = (
                                NT_NET_MODE_CLIENT | NT_NET_MODE_FAILURE
                            )
                            continue
                        server_or_servers = self.m_client_connector

                # try to connect (with timeout)
                if self.m_verbose:
                    logger.debug("client trying to connect")

                stream = tcp_connector.connect(server_or_servers)
                if not stream:
                    self.m_networkMode = NT_NET_MODE_CLIENT | NT_NET_MODE_FAILURE
                    continue  # keep retrying

                logger.debug("client connected")
                self.m_networkMode = NT_NET_MODE_CLIENT

                with self.m_user_mutex:
                    connection_uid = self.m_connections_uid
                    self.m_connections_uid += 1

                    conn = NetworkConnection(
                        connection_uid,
                        stream,
                        self.m_notifier,
                        self._clientHandshake,
                        self.m_storage.getMessageEntryType,
                        verbose=self.m_verbose,
                    )

                    conn.set_process_incoming(self.m_storage.processIncoming)

                    # disconnect any current
                    # -> different from ntcore because we don't have destructors
                    for c in self.m_connections:
                        if c != conn:
                            c.stop()

                    del self.m_connections[:]
                    self.m_connections.append(conn)
                    conn.set_proto_rev(self.m_reconnect_proto_rev)
                    conn.start()

                    # reconnect the next time starting with latest protocol revision
                    self.m_reconnect_proto_rev = self.m_default_proto

                    # block until told to reconnect
                    self.m_do_reconnect = False

                    self.m_reconnect_cv.wait_for(
                        lambda: not self.m_active or self.m_do_reconnect
                    )
        finally:
            self.m_networkMode = NT_NET_MODE_NONE

    def _clientHandshake(self, conn, get_msg, send_msgs):
        # get identity
        with self.m_user_mutex:
            self_id = self.m_identity

        # send client hello
        if self.m_verbose:
            logger.debug("client: sending hello")

        send_msgs((Message.clientHello(conn.get_proto_rev(), self_id),))

        # wait for response
        msg = get_msg()
        if not msg:
            # disconnected, retry
            logger.debug("client: server disconnected before first response")
            return False

        if msg.type == kProtoUnsup:
            if msg.id == 0x0200:
                logger.debug("client: connected to NT2 server, reconnecting...")
                self._clientReconnect(0x0200)
            else:
                logger.debug("client: connected to 0x%04x server, giving up...", msg.id)

            return False

        new_server = True
        if conn.get_proto_rev() >= 0x0300:
            # should be server hello; if not, disconnect.
            if not msg.type == kServerHello:
                return False

            remote_id = msg.str
            if (msg.flags & 1) != 0:
                new_server = False

            # get the next message
            msg = get_msg()
        else:
            remote_id = "NT2 server"

        conn.set_remote_id(remote_id)

        # receive initial assignments
        incoming = []
        verbose = self.m_verbose

        while True:
            if not msg:
                # disconnected, retry
                logger.debug("client: server disconnected during initial entries")
                return False

            if msg.type == kServerHelloDone:
                break

            if msg.type == kKeepAlive:
                # shouldn't receive a keep alive, but handle gracefully
                msg = get_msg()
                continue

            if not msg.type == kEntryAssign:
                # unexpected message
                logger.debug(
                    "client: received message (%s) other than entry assignment during initial handshake",
                    msg.type,
                )
                return False

            if verbose:
                logger.debug(
                    "client %s: received assign str=%s id=%s seq_num=%s val=%s",
                    self_id,
                    msg.str,
                    msg.id,
                    msg.seq_num_uid,
                    msg.value,
                )

            incoming.append(msg)
            # get the next message
            msg = get_msg()

        # generate outgoing assignments
        outgoing = []

        self.m_storage.applyInitialAssignments(conn, incoming, new_server, outgoing)

        if conn.get_proto_rev() >= 0x0300:
            outgoing.append(Message.clientHelloDone())

        if outgoing:
            send_msgs(outgoing)

        # stream = conn.get_stream()
        # logger.info("client: CONNECTED to server %s port %s",
        #            stream.getPeerIP(), stream.getPeerPort())

        return True

    def _serverHandshake(self, conn, get_msg, send_msgs):

        verbose = self.m_verbose

        # Wait for the client to send us a hello.
        msg = get_msg()
        if not msg:
            logger.debug("server: client disconnected before sending hello")
            return False

        if not msg.type == kClientHello:
            logger.debug("server: client initial message was not client hello")
            return False

        # Check that the client requested version is not too high.
        proto_rev = msg.id
        if proto_rev > self.m_default_proto:
            logger.debug(
                "server: client requested proto > 0x%04x", self.m_default_proto
            )
            send_msgs((Message.protoUnsup(self.m_default_proto),))
            return False

        if proto_rev >= 0x0300:
            remote_id = msg.str
        else:
            remote_id = "NT2 client"

        conn.set_remote_id(remote_id)

        # Set the proto version to the client requested version
        if verbose:
            logger.debug("server: client protocol 0x%04x", proto_rev)
        conn.set_proto_rev(proto_rev)

        # Send initial set of assignments
        outgoing = []

        # Start with server hello.  TODO: initial connection flag
        if proto_rev >= 0x0300:
            with self.m_user_mutex:
                outgoing.append(Message.serverHello(0, self.m_identity))

        # Get snapshot of initial assignments
        self.m_storage.getInitialAssignments(conn, outgoing)

        # Finish with server hello done
        outgoing.append(Message.serverHelloDone())

        # Batch transmit
        if verbose:
            logger.debug("server: sending initial assignments")

        send_msgs(outgoing)

        # In proto rev 3.0 and later, handshake concludes with a client hello
        # done message, we can batch the assigns before marking the connection
        # active.  In pre-3.0, need to just immediately mark it active and hand
        # off control to the dispatcher to assign them as they arrive.
        if proto_rev >= 0x0300:
            # receive client initial assignments
            incoming = []
            while True:
                # get the next message (blocks)
                msg = get_msg()
                if not msg:
                    # disconnected, retry
                    logger.debug("server: disconnected waiting for initial entries")
                    return False

                if msg.type == kClientHelloDone:
                    break
                # shouldn't receive a keep alive, but handle gracefully
                elif msg.type == kKeepAlive:
                    continue

                if msg.type != kEntryAssign:
                    # unexpected message
                    logger.debug(
                        "server: received message (%s) other than entry assignment during initial handshake",
                        msg.type,
                    )
                    return False

                if verbose:
                    logger.debug(
                        "received assign str=%s id=%s seq_num=%s",
                        msg.str,
                        msg.id,
                        msg.seq_num_uid,
                    )

                incoming.append(msg)

            for msg in incoming:
                self.m_storage.processIncoming(msg, conn)

        # stream = conn.get_stream()
        # logger.info("server: client CONNECTED %s port %s",
        #            stream.getPeerIP(), stream.getPeerPort())

        return True

    def _clientReconnect(self, proto_rev=0x0300):
        if self.m_networkMode & NT_NET_MODE_SERVER != 0:
            return

        with self.m_user_mutex:
            self.m_reconnect_proto_rev = proto_rev
            self.m_do_reconnect = True

            self.m_reconnect_cv.notify()

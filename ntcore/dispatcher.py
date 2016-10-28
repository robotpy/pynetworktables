# validated: 2016-10-27 DS 273a395 src/Dispatcher.cpp
'''----------------------------------------------------------------------------'''
''' Copyright (c) FIRST 2015. All Rights Reserved.                             '''
''' Open Source Software - may be modified and shared by FRC teams. The code   '''
''' must be accompanied by the FIRST BSD license file in the root directory of '''
''' the project.                                                               '''
'''----------------------------------------------------------------------------'''

import threading
import time

from .message import Message
from .network_connection import NetworkConnection

from .tcpsockets.tcp_acceptor import TcpAcceptor
from .tcpsockets.tcp_connector import TcpConnector

from .support.compat import monotonic, Condition

from .constants import (
    kKeepAlive,
    kClientHello,
    kProtoUnsup,
    kServerHello,
    kServerHelloDone,
    kClientHelloDone,
    kEntryAssign,
)

import logging
logger = logging.getLogger('nt')


class Dispatcher(object):
    
    def __init__(self, storage, notifier, verbose=False):
        
        # logging debugging
        self.m_verbose = verbose
        
        self.m_storage = storage
        self.m_notifier = notifier
        self.m_server = False
        self.m_persist_filename = None
        self.m_server_acceptor = None
        self.m_client_connectors = []
        self.m_identity = ''
        self.m_default_proto = 0x0300 # for testing
        
        # Mutex for user-accessible items
        self.m_user_mutex = threading.RLock()
        self.m_connections = []
        
        self.m_active = False # set to false to terminate threads
        self.m_update_rate = 0.050 # periodic dispatch rate, in s
        
        self.m_flush_mutex = threading.Lock()
        self.m_flush_cv = Condition(self.m_flush_mutex)
        self.m_last_flush = 0
        self.m_do_flush = False
        
        self.m_reconnect_cv = Condition(self.m_user_mutex)
        self.m_reconnect_proto_rev = self.m_default_proto
        self.m_do_reconnect = True
    
    def setVerboseLogging(self, verbose):
        self.m_verbose = verbose
    
    def startServer(self, persist_filename, listen_address, port):
        acceptor = TcpAcceptor(port, listen_address)
        self._startServer(persist_filename, acceptor)
    
    def startClient(self, servers):
        # servers is a tuple of (server, port)
        connectors = [TcpConnector(server, port, 1) for server, port in servers]
        self._startClient(connectors)
    
    def _startServer(self, persist_filename, acceptor):
        
        with self.m_user_mutex:
            if self.m_active:
                return
    
            self.m_active = True
    
        self.m_server = True
        self.m_persist_filename = persist_filename
        self.m_server_acceptor = acceptor
    
        # Load persistent file.  Ignore errors, pass along warnings.
        if persist_filename:
            self.m_storage.loadPersistent(persist_filename)
    
        self.m_storage.setOutgoing(self._queueOutgoing,
                                   self.m_server)
    
        self.m_dispatch_thread = threading.Thread(target=self._dispatchThreadMain,
                                                  name='nt-dispatch-thread') 
        self.m_clientserver_thread = threading.Thread(target=self._serverThreadMain,
                                                      name='nt-server-thread')
        
        self.m_dispatch_thread.daemon = True
        self.m_clientserver_thread.daemon = True
        
        self.m_dispatch_thread.start()
        self.m_clientserver_thread.start()
    
    def _startClient(self, connectors):
        if not isinstance(connectors, list):
            connectors = [connectors]
        
        with self.m_user_mutex:
            if self.m_active:
                return
    
            self.m_active = True
            self.m_client_connectors = connectors[:]
    
        self.m_server = False
        self.m_storage.setOutgoing(self._queueOutgoing,
                                   self.m_server)
    
        self.m_dispatch_thread = threading.Thread(target=self._dispatchThreadMain,
                                                  name='nt-dispatch-thread') 
        self.m_clientserver_thread = threading.Thread(target=self._clientThreadMain,
                                                      name='nt-client-thread')
        
        self.m_dispatch_thread.daemon = True
        self.m_clientserver_thread.daemon = True
        
        self.m_dispatch_thread.start()
        self.m_clientserver_thread.start()
    
    
    def stop(self):
        if not self.m_active:
            return
        
        self.m_active = False
    
        # wake up dispatch thread with a flush
        with self.m_flush_mutex:
            self.m_flush_cv.notify()
    
        # wake up client thread with a reconnect
        with self.m_user_mutex:
            del self.m_client_connectors[:]
    
        self._clientReconnect()
    
        # wake up server thread by shutting down the socket
        if self.m_server_acceptor:
            self.m_server_acceptor.shutdown()
        
        # join threads, timeout
        self.m_dispatch_thread.join(1)
        if self.m_dispatch_thread.is_alive():
            logger.warn("%s did not die", self.m_dispatch_thread.name)
        
        self.m_clientserver_thread.join(1)
        if self.m_clientserver_thread.is_alive():
            logger.warn("%s did not die", self.m_clientserver_thread.name)
        
        with self.m_user_mutex:
            conns = self.m_connections
            self.m_connections = []
    
        # close all connections
        for conn in conns:
            conn.stop()
            
        # cleanup the server socket
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
        now = monotonic()
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
                if conn.state() != NetworkConnection.State.kActive:
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
        return self.m_server
    
    def notifyConnections(self, callback):
        with self.m_user_mutex:
            for conn in self.m_connections:
                conn.notifyIfActive(callback)
    
    def _dispatchWaitFor(self):
        return not self.m_active or self.m_do_flush
    
    def _dispatchThreadMain(self):
        timeout_time = monotonic()
    
        save_delta_time = 1.0
        next_save_time = timeout_time + save_delta_time
    
        count = 0
        is_server = self.m_server
        verbose = self.m_verbose
        
        while self.m_active:
            # handle loop taking too long
            start = monotonic()
            if start > timeout_time:
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
                        logger.debug("dispatch running %s connections",
                                     len(self.m_connections))
                        count = 0
                
                for conn in self.m_connections:
                    # post outgoing messages if connection is active
                    # only send keep-alives on client
                    state = conn.state()
                    if state == NetworkConnection.State.kActive:
                        conn.postOutgoing(not is_server)
                    
                    # if client, if connection died
                    if not is_server and state == NetworkConnection.State.kDead:
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
                
                state = conn.state()
                if (state != NetworkConnection.State.kSynchronized and
                    state != NetworkConnection.State.kActive):
                    continue
    
                conn.queueOutgoing(msg)
    
    def _serverThreadMain(self):
        if not self.m_server_acceptor.start():
            self.m_active = False
        
        try:
            while self.m_active:
                stream = self.m_server_acceptor.accept()
                if not stream:
                    self.m_active = False
                    return
        
                if not self.m_active:
                    return
        
                logger.debug("server: client connection from %s port %s",
                             stream.getPeerIP(), stream.getPeerPort())
        
                # add to connections list
                conn = NetworkConnection(stream, self.m_notifier,
                                         self._serverHandshake,
                                         self.m_storage.getEntryType,
                                         verbose=self.m_verbose)
                
                conn.set_process_incoming(self.m_storage.processIncoming)
                    
                with self.m_user_mutex:
                    # reuse dead connection slots
                    for i in range(len(self.m_connections)):
                        c = self.m_connections[i]
                        if c.state() == NetworkConnection.State.kDead:
                            c.stop()
                            self.m_connections[i] = conn
                            break
                    else:
                        self.m_connections.append(conn)
        
                    conn.start()
        finally:
            logger.debug("server thread exiting")
    
    def _clientThreadMain(self):
        i = 0
        
        try:
            while self.m_active:
                # sleep between retries
                time.sleep(0.250)
        
                # get next server to connect to
                with self.m_user_mutex:
                    if not self.m_client_connectors:
                        continue
        
                    if i >= len(self.m_client_connectors):
                        i = 0
        
                    connect = self.m_client_connectors[i]
                    i += 1
                
                # try to connect (with timeout)
                if self.m_verbose:
                    logger.debug("client trying to connect")
                    
                try:
                    stream = connect()
                except IOError:
                    continue    # keep retrying
        
                logger.debug("client connected")
        
                with self.m_user_mutex:
                    conn = NetworkConnection(stream, self.m_notifier,
                                             self._clientHandshake,
                                             self.m_storage.getEntryType,
                                             verbose=self.m_verbose)
                    
                    conn.set_process_incoming(self.m_storage.processIncoming)
                    
                    # disconnect any current
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
                    
                    while not (not self.m_active or self.m_do_reconnect):
                        self.m_reconnect_cv.wait()
        finally:
            logger.debug("client thread exiting")
    
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
            remote_id = 'NT2 server'
            
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
            
            if not msg.type == kEntryAssign:
                # unexpected message
                logger.debug("client: received message (%s) other than entry assignment during initial handshake",
                             msg.type)
                return False
            
            if verbose:
                logger.debug("received assign str=%s id=%s seq_num=%s",
                             msg.str, msg.id, msg.seq_num_uid)
    
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
            logger.debug("server: client requested proto > 0x%04x", self.m_default_proto)
            send_msgs((Message.protoUnsup(self.m_default_proto),))
            return False
    
        
        if proto_rev >= 0x0300:
            remote_id = msg.str
        else:
            remote_id = 'NT2 client'
        
        conn.set_remote_id(remote_id)
    
        # Set the proto version to the client requested version
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
                elif msg.type == kKeepAlive:
                    continue
                
                if msg.type != kEntryAssign:
                    # unexpected message
                    logger.debug("server: received message (%s) other than entry assignment during initial handshake",
                                 msg.type)
                    return False
                
                if verbose:
                    logger.debug("received assign str=%s id=%s seq_num=%s",
                                 msg.str, msg.id, msg.seq_num_uid)
    
                incoming.append(msg)
    
            for msg in incoming:
                self.m_storage.processIncoming(msg, conn)
    
        stream = conn.get_stream()
        return True
    
    def _clientReconnect(self, proto_rev=0x0300):
        if self.m_server:
            return
    
        with self.m_user_mutex:
            self.m_reconnect_proto_rev = proto_rev
            self.m_do_reconnect = True
    
            self.m_reconnect_cv.notify()


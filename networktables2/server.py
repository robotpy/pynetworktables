import threading
import time

from . import _impl
from .common import *
from .connection import *
from .networktablenode import NetworkTableNode
from .type import NetworkTableEntryTypeManager

import logging
logger = logging.getLogger('nt')

__all__ = ["NetworkTableServer"]

class ServerConnectionState:
    """Represents the state of a connection to the server
    """

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

# represents that the server has received the connection from the client but
# has not yet received the client hello
GOT_CONNECTION_FROM_CLIENT = ServerConnectionState("GOT_CONNECTION_FROM_CLIENT")
# represents that the client is in a connected non-error state
CONNECTED_TO_CLIENT = ServerConnectionState("CONNECTED_TO_CLIENT")
# represents that the client has disconnected from the server
CLIENT_DISCONNECTED = ServerConnectionState("CLIENT_DISCONNECTED")

class ServerError(ServerConnectionState):
    """Represents that the client is in an error state
    """

    def __init__(self, e):
        """Create a new error state
        :param e:
        """
        ServerConnectionState.__init__(self, "SERVER_ERROR")
        self.e = e

    def getException(self):
        """:returns: the exception that caused the client connection to enter
            an error state
        """
        return self.e

    def __str__(self):
        return "SERVER_ERROR: %s" % self.e

class ServerConnectionAdapter:
    """Object that adapts messages from a client to the server
    """

    def gotoState(self, newState):
        if self.connectionState != newState:
            logger.info("%s entered connection state: %s", self, newState)
            self.connectionState = newState

    def __init__(self, stream, entryStore, adapterListener, typeManager):
        """Create a server connection adapter for a given stream

        :param stream:
        :param entryStore:
        :param adapterListener:
        """
        self.connection = NetworkTableConnection(stream, typeManager)
        self.entryStore = entryStore
        self.adapterListener = adapterListener

        self.connectionState = None
        self.gotoState(GOT_CONNECTION_FROM_CLIENT)
        self.readManager = ReadManager(self,
                self.connection, name="Server Connection Reader Thread")
        self.readManager.start()
        
    def __str__(self):
        return 'Server 0x%08x' % id(self)

    def badMessage(self, e):
        self.gotoState(ServerError(e))
        self.adapterListener.close(self, True)

    def ioError(self, e):
        if isinstance(e, StreamEOF):
            self.gotoState(CLIENT_DISCONNECTED)
        else:
            self.gotoState(ServerError(e))
        self.adapterListener.close(self, False)

    def shutdown(self, closeStream):
        """stop the read thread and close the stream
        """
        self.readManager.stop()
        if closeStream:
            self.connection.close()

    def keepAlive(self):
        pass # just let it happen

    def clientHello(self, protocolRevision):
        if self.connectionState != GOT_CONNECTION_FROM_CLIENT:
            raise BadMessageError("A server should not receive a client hello after it has already connected/entered an error state")
        if protocolRevision != PROTOCOL_REVISION:
            self.connection.sendProtocolVersionUnsupported()
            raise BadMessageError("Client Connected with bad protocol revision: 0x%x" % protocolRevision)
        else:
            self.entryStore.sendServerHello(self.connection)
            self.gotoState(CONNECTED_TO_CLIENT)

    def protocolVersionUnsupported(self, protocolRevision):
        raise BadMessageError("A server should not receive a protocol version unsupported message")

    def serverHelloComplete(self):
        raise BadMessageError("A server should not receive a server hello complete message")

    def offerIncomingAssignment(self, entry):
        self.entryStore.offerIncomingAssignment(entry)

    def offerIncomingUpdate(self, entry, sequenceNumber, value):
        self.entryStore.offerIncomingUpdate(entry, sequenceNumber, value)

    def getEntry(self, id):
        return self.entryStore.getEntry(id)

    def sendEntry(self, entryBytes):
        try:
            if self.connectionState == CONNECTED_TO_CLIENT:
                self.connection.sendEntry(entryBytes)
        except IOError as e:
            self.ioError(e)
    
    def flush(self):
        try:
            self.connection.flush()
        except IOError as e:
            self.ioError(e)

    def getConnectionState(self):
        """:returns: the state of the connection
        """
        return self.connectionState

    def ensureAlive(self):
        try:
            self.connection.sendKeepAlive()
        except IOError as e:
            self.ioError(e)

class ServerNetworkTableEntryStore(AbstractNetworkTableEntryStore):
    """The entry store for a {@link NetworkTableServer}
    """

    def __init__(self, listenerManager):
        """Create a new Server entry store
        :param listenerManager: the listener manager that fires events from
            this entry store
        """
        AbstractNetworkTableEntryStore.__init__(self, listenerManager)
        self.nextId = 0

    def addEntry(self, newEntry):
        with self.entry_lock:
            entry = self.namedEntries.get(newEntry.name)

            if entry is None:
                newEntry.setId(self.nextId)
                self.nextId += 1
                self.idEntries[newEntry.getId()] = newEntry
                self.namedEntries[newEntry.name] = newEntry
                return True
            return False

    def updateEntry(self, entry, sequenceNumber, value):
        with self.entry_lock:
            if entry.putValue(sequenceNumber, value):
                return True
            return False

    def sendServerHello(self, connection):
        """Send all entries in the entry store as entry assignments in a
        single transaction
        :param connection:
        """
        transaction = []
        with self.entry_lock:
            # Cannot use sendEntry while holding entry lock!
            for entry in self.namedEntries.values():
                transaction.append(entry.getAssignmentBytes())
                
        for entry in transaction:
            connection.sendEntry(entry)
        connection.sendServerHelloComplete()
        connection.flush()

class ServerConnectionList:
    """A list of connections that the server currently has
    """

    def __init__(self):
        self.connections = []
        self.connectionsLock = _impl.create_rlock('server_conn_lock')

    def add(self, connection):
        """Add a connection to the list
        :param connection:
        """
        with self.connectionsLock:
            self.connections.append(connection)

    def close(self, connectionAdapter, closeStream):
        with self.connectionsLock:
            try:
                self.connections.remove(connectionAdapter)
            except ValueError:
                return
            logger.info("Close: %s", connectionAdapter)
            connectionAdapter.shutdown(closeStream)

    def closeAll(self):
        """close all connections and remove them
        """
        with self.connectionsLock:
            for connection in self.connections:
                logger.info("Close: %s", connection)
                connection.shutdown(True)
            del self.connections[:]

    def sendEntry(self, entryBytes):
        with self.connectionsLock:
            for connection in self.connections:
                connection.sendEntry(entryBytes)

    def flush(self):
        with self.connectionsLock:
            for connection in self.connections:
                connection.flush()

    def ensureAlive(self):
        with self.connectionsLock:
            for connection in self.connections:
                connection.ensureAlive()

class NetworkTableServer(NetworkTableNode):
    """A server node in NetworkTables 2.0
    """

    def __init__(self, streamProvider):
        """Create a NetworkTable Server
        :param streamProvider:
        """
        NetworkTableNode.__init__(self, ServerNetworkTableEntryStore(self))
        self.typeManager = NetworkTableEntryTypeManager()
        self.streamProvider = streamProvider

        self.connectionList = ServerConnectionList()
        self.writeManager = WriteManager(self.connectionList, self.entryStore, None)

        self.entryStore.setIncomingReceiver(self.writeManager)
        self.entryStore.setOutgoingReceiver(self.writeManager)

        # start incoming stream monitor
        self.running = True
        self.monitorThread = threading.Thread(target=self._incomingMonitor,
                                              name="Server Incoming Stream Monitor Thread")
        self.monitorThread.daemon = True
        self.monitorThread.start()

        # start write manager
        self.writeManager.start()

    def close(self):
        try:
            self.running = False
            self.monitorThread.join()
            self.writeManager.stop()
            self.connectionList.closeAll()
            time.sleep(1) #To get around bug where an error will occur in select if the socket server is closed before all sockets finish closing
            self.streamProvider.close()
            time.sleep(1)
        except IOError as e:
            logger.error("Error during close: %s", e)

    def isConnected(self):
        return True

    def isServer(self):
        return True

    def _incomingMonitor(self):
        while self.running:
            try:
                newStream = self.streamProvider.accept()
                if newStream is not None:
                    connectionAdapter = ServerConnectionAdapter(newStream, self.entryStore, self.connectionList, self.typeManager)
                    self.connectionList.add(connectionAdapter)
            except IOError:
                pass #could not get a new stream for some reason. ignore and continue


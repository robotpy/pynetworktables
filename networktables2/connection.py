
import threading

from . import _impl
from .entry import NetworkTableEntry
from .messages import *

__all__ = ["BadMessageError", "StreamEOF", "NetworkTableConnection",
           "ReadManager", "PROTOCOL_REVISION"]

class StreamEOF(IOError):
    pass

class ReadStream:
    def __init__(self, f):
        self.f = f

    def read(self, size=-1):
        data = self.f.read(size)
        if size is not None and size > 0 and len(data) != size:
            raise StreamEOF("end of file")
        return data

    def readStruct(self, s):
        data = self.f.read(s.size)
        if len(data) != s.size:
            raise StreamEOF("end of file")
        return s.unpack(data)

class NetworkTableConnection:
    """An abstraction for the NetworkTable protocol
    """
    def __init__(self, stream, typeManager):
        self.stream = stream
        self.rstream = ReadStream(stream.getInputStream())
        self.wstream = stream.getOutputStream()
        self.typeManager = typeManager
        self.write_lock = _impl.create_rlock('write_lock')
        self.isValid = True

    def close(self):
        if self.isValid:
            self.isValid = False
            self.stream.close()

    def flush(self):
        with self.write_lock:
            self.wstream.flush()

    def sendKeepAlive(self):
        with self.write_lock:
            self.wstream.write(KEEP_ALIVE.getBytes())
            self.wstream.flush()

    def sendClientHello(self):
        with self.write_lock:
            self.wstream.write(CLIENT_HELLO.getBytes(PROTOCOL_REVISION))
            self.wstream.flush()

    def sendServerHelloComplete(self):
        with self.write_lock:
            self.wstream.write(SERVER_HELLO_COMPLETE.getBytes())
            self.wstream.flush()

    def sendProtocolVersionUnsupported(self):
        with self.write_lock:
            self.wstream.write(PROTOCOL_UNSUPPORTED.getBytes(PROTOCOL_REVISION))
            self.wstream.flush()

    def sendEntry(self, entryBytes):
        # use entry.getAssignBytes or entry.getUpdateBytes
        with self.write_lock:
            self.wstream.write(entryBytes)
    
    def read(self, adapter):
        messageType = self.rstream.read(1)
        if messageType == KEEP_ALIVE.HEADER:
            adapter.keepAlive()
            
        elif messageType == CLIENT_HELLO.HEADER:
            protocolRevision = CLIENT_HELLO.read(self.rstream)[0]
            adapter.clientHello(protocolRevision)
            
        elif messageType == SERVER_HELLO_COMPLETE.HEADER:
            adapter.serverHelloComplete()
            
        elif messageType == PROTOCOL_UNSUPPORTED.HEADER:
            protocolRevision = PROTOCOL_UNSUPPORTED.read(self.rstream)[0]
            adapter.protocolVersionUnsupported(protocolRevision)
            
        elif messageType == ENTRY_ASSIGNMENT.HEADER:
            entryName, (typeId, entryId, entrySequenceNumber) = \
                    ENTRY_ASSIGNMENT.read(self.rstream)
            entryType = self.typeManager.getType(typeId)
            if entryType is None:
                raise BadMessageError("Unknown data type: 0x%x" % typeId)
            value = entryType.readValue(self.rstream)
            adapter.offerIncomingAssignment(NetworkTableEntry(entryName, entryType, value, id=entryId, sequenceNumber=entrySequenceNumber))
            
        elif messageType == FIELD_UPDATE.HEADER:
            entryId, entrySequenceNumber = FIELD_UPDATE.read(self.rstream)
            entry = adapter.getEntry(entryId)
            if entry is None:
                raise BadMessageError("Received update for unknown entry id: %d " % entryId)
            value = entry.getType().readValue(self.rstream)
            adapter.offerIncomingUpdate(entry, entrySequenceNumber, value)
            
        else:
            raise BadMessageError("Unknown Network Table Message Type: %s" % (messageType))

class ReadManager:
    """A periodic thread that repeatedly reads from a connection
    """
    def __init__(self, adapter, connection, name=None):
        """create a new monitor thread
        
        :param adapter:
        :type  adapter: :class:`.ServerConncetionAdapter` or :class:`.ClientConnectionAdapter`
        :param connection:
        :type  connection: :class:`NetworkTableConnection`
        """
        self.adapter = adapter
        self.connection = connection
        self.running = True
        
        self.thread = threading.Thread(target=self.run, name=name)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False
        try:
            self.thread.join()
        except RuntimeError:
            pass

    def run(self):
        while self.running:
            try:
                self.connection.read(self.adapter)
            except BadMessageError as e:
                self.adapter.badMessage(e)
            except IOError as e:
                self.adapter.ioError(e)

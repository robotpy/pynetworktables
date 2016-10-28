# validated: 2016-10-21 DS c0ce427 src/ntcore_cpp.cpp

from .dispatcher import Dispatcher
from .notifier import Notifier
from .rpc_server import RpcServer
from .storage import Storage

from .constants import NT_NOTIFY_IMMEDIATE

class NtCoreApi(object):
    '''
        Internal NetworkTables API wrapper
        
        In theory you could create multiple instances of this
        and talk to multiple NT servers or create multiple
        NT servers... though, I don't really know why one
        would want to do this.
    '''
    
    def __init__(self, verbose=False):
        self.notifier = Notifier(verbose=verbose)
        self.rpc_server = RpcServer()
        self.storage = Storage(self.notifier, self.rpc_server)
        self.dispatcher = Dispatcher(self.storage, self.notifier, verbose=verbose)
        
    def stop(self):
        self.dispatcher.stop()
        self.rpc_server.stop()
        self.notifier.stop()
        self.storage.stop()

    #
    # Table functions
    #
    
    def getEntryValue(self, name):
        return self.storage.getEntryValue(name)
    
    def setDefaultEntryValue(self, name, value):
        return self.storage.setDefaultEntryValue(name, value)
    
    def setEntryValue(self, name, value):
        return self.storage.setEntryValue(name, value)
    
    def setEntryTypeValue(self, name, value):
        self.storage.setEntryTypeValue(name, value)
    
    def setEntryFlags(self, name, flags):
        self.storage.setEntryFlags(name, flags)
    
    def getEntryFlags(self, name):
        return self.storage.getEntryFlags(name)
    
    def deleteEntry(self, name):
        self.storage.deleteEntry(name)
    
    def deleteAllEntries(self):
        self.storage.deleteAllEntries()
    
    def getEntryInfo(self, prefix, types):
        return self.storage.getEntryInfo(prefix, types)
    
    def flush(self):
        self.dispatcher.flush()
    
    #
    # Callback creation functions
    #
    
    def setListenerOnStart(self, on_start):
        self.notifier.setOnStart(on_start)
    
    def setListenerOnExit(self, on_exit):
        self.notifier.setOnExit(on_exit)
    
    def addEntryListener(self, prefix, callback, flags):
        uid = self.notifier.addEntryListener(prefix, callback, flags)
        if (flags & NT_NOTIFY_IMMEDIATE) != 0:
            self.storage.notifyEntries(prefix, callback)
    
        return uid
    
    def removeEntryListener(self, entry_listener_uid):
        self.notifier.removeEntryListener(entry_listener_uid)
    
    def addConnectionListener(self, callback, immediate_notify):
        self.notifier.addConnectionListener(callback)
        if immediate_notify:
            self.dispatcher.notifyConnections(callback)
    
    def removeConnectionListener(self, callback):
        self.notifier.removeConnectionListener(callback)

    # Python-specific
    def createAutoValue(self, key, value):
        return self.notifier.createAutoValue(key, value)
    
    #
    # TODO: RPC stuff not currently implemented
    #       .. there's probably a good pythonic way to implement
    #          it, but I don't really want to deal with it now.
    #          If you care, submit a PR.
    #
    #          I would have the caller register the server function
    #          via a docstring.
    #
    
    #
    # Initialization functions
    #
        
    def setNetworkIdentity(self, name):
        self.dispatcher.setIdentity(name)
        
    def startServer(self, persist_filename, listen_address, port):
        self.dispatcher.startServer(persist_filename, listen_address, port)
    
    def stopServer(self):
        self.dispatcher.stop()
        
    def startClient(self, servers):
        self.dispatcher.startClient(servers)
        
    def stopClient(self):
        self.dispatcher.stop()
    
    def setUpdateRate(self, interval):
        self.dispatcher.setUpdateRate(interval)
    
    def getRemoteAddress(self):
        if not self.dispatcher.isServer():
            for conn in self.dispatcher.getConnections():
                return conn.remote_ip
    
    def getIsConnected(self):
        return self.dispatcher.isConnected()
    
    def setVerboseLogging(self, verbose):
        self.dispatcher.setVerboseLogging(verbose)
        self.notifier.setVerboseLogging(verbose)
    
    #
    # Persistence
    #
    
    def savePersistent(self, filename):
        return self.storage.savePersistent(filename, periodic=False)
        
    def loadPersistent(self, filename):
        return self.storage.loadPersistent(filename)
    
    
        
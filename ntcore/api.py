# validated: 2017-10-03 DS 1f18cc54167b cpp/ntcore_cpp.cpp

from .connection_notifier import ConnectionNotifier
from .dispatcher import Dispatcher
from .ds_client import DsClient
from .entry_notifier import EntryNotifier
from .rpc_server import RpcServer
from .storage import Storage

from ntcore.constants import NT_NOTIFY_IMMEDIATE, NT_NOTIFY_NEW
_is_new = NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW

class NtCoreApi(object):
    '''
        Internal NetworkTables API wrapper
        
        In theory you could create multiple instances of this
        and talk to multiple NT servers or create multiple
        NT servers... though, I don't really know why one
        would want to do this.
    '''
    
    def __init__(self, entry_creator, verbose=False):
        self.conn_notifier = ConnectionNotifier(verbose=verbose)
        self.entry_notifier = EntryNotifier(verbose=verbose)
        self.rpc_server = RpcServer(verbose=verbose)
        self.storage = Storage(self.entry_notifier, self.rpc_server, entry_creator)
        self.dispatcher = Dispatcher(self.storage, self.conn_notifier, verbose=verbose)
        self.ds_client = DsClient(self.dispatcher, verbose=verbose)
        
    def stop(self):
        self.ds_client.stop()
        self.dispatcher.stop()
        self.rpc_server.stop()
        self.entry_notifier.stop()
        self.conn_notifier.stop()
        self.storage.stop()
        
    def destroy(self):
        self.ds_client = None
        self.dispatcher = None
        self.rpc_server = None
        self.entry_notifier = None
        self.entry_notifier = None
        self.conn_notifier = None
        self.storage = None

    #
    # Table functions
    #
    
    def getEntry(self, name):
        return self.storage.getEntry(name)
    
    def getEntryId(self, name):
        return self.storage.getEntryId(name)
    
    def getEntries(self, prefix, types):
        return self.storage.getEntries(prefix, types)
    
    def getEntryNameById(self, local_id):
        return self.storage.getEntryNameById(local_id)
    
    def getEntryTypeById(self, local_id):
        return self.storage.getEntryTypeById(local_id)
    
    def getEntryValue(self, name):
        return self.storage.getEntryValue(name)

    def setDefaultEntryValue(self, name, value):
        return self.storage.setDefaultEntryValue(name, value)
    
    def setDefaultEntryValueById(self, local_id, value):
        return self.storage.setDefaultEntryValueById(local_id, value)
    
    def setEntryValue(self, name, value):
        return self.storage.setEntryValue(name, value)
    
    def setEntryValueById(self, local_id, value):
        return self.storage.setEntryValueById(local_id, value)
    
    def setEntryTypeValue(self, name, value):
        self.storage.setEntryTypeValue(name, value)
        
    def setEntryTypeValueById(self, local_id, value):
        self.storage.setEntryTypeValueById(local_id, value)
    
    def setEntryFlags(self, name, flags):
        self.storage.setEntryFlags(name, flags)
        
    def setEntryFlagsById(self, local_id, flags):
        self.storage.setEntryFlagsById(local_id, flags)
    
    def getEntryFlags(self, name):
        return self.storage.getEntryFlags(name)
    
    def getEntryFlagsById(self, local_id):
        return self.storage.getEntryFlagsById(local_id)

    def deleteEntry(self, name):
        self.storage.deleteEntry(name)
    
    def deleteEntryById(self, local_id):
        self.storage.deleteEntryById(local_id)

    def deleteAllEntries(self):
        self.storage.deleteAllEntries()
    
    def getEntryInfo(self, prefix, types):
        return self.storage.getEntryInfo(prefix, types)
    
    def getEntryInfoById(self, local_id):
        return self.storage.getEntryInfoById(local_id)
    
    #
    # Entry notification
    #
    
    def addEntryListener(self, prefix, callback, flags):
        return self.storage.addListener(prefix, callback, flags)
    
    def addEntryListenerById(self, local_id, callback, flags):
        return self.storage.addListenerById(local_id, callback, flags)
    
    def addEntryListenerByIdEx(self, fromobj, key, local_id, callback, flags, paramIsNew):
        if paramIsNew:
            def listener(item):
                key_, value_, flags_, _ = item
                callback(fromobj, key, value_.value, (flags_ & _is_new) != 0)
        else:
            def listener(item):
                key_, value_, flags_, _ = item
                callback(fromobj, key, value_.value, flags_)
        
        return self.storage.addListenerById(local_id, listener, flags)
    
    def createEntryListenerPoller(self):
        return self.entry_notifier.createPoller()
    
    def destroyEntryListenerPoller(self, poller_uid):
        self.entry_notifier.removePoller(poller_uid)
    
    def addPolledEntryListener(self, poller_uid, prefix, flags):
        return self.storage.addPolledListener(poller_uid, prefix, flags)
    
    def addPolledEntryListenerById(self, poller_uid, local_id, flags):
        return self.storage.addPolledListenerById(poller_uid, local_id, flags)
    
    def pollEntryListener(self, poller_uid, timeout=None):
        return self.entry_notifier.poll(poller_uid, timeout=timeout)
    
    def cancelPollEntryListener(self, poller_uid):
        self.entry_notifier.cancelPoll(poller_uid)
    
    def removeEntryListener(self, listener_uid):
        self.entry_notifier.remove(listener_uid)
    
    def waitForEntryListenerQueue(self, timeout):
        return self.entry_notifier.waitForQueue(timeout)
    
    #
    # Connection notifications
    #
    
    def addConnectionListener(self, callback, immediate_notify):
        return self.dispatcher.addListener(callback, immediate_notify)
    
    def createConnectionListenerPoller(self):
        return self.conn_notifier.createPoller()
    
    def destroyConnectionListenerPoller(self, poller_uid):
        self.conn_notifier.removePoller(poller_uid)
    
    def addPolledConnectionListener(self, poller_uid, immediate_notify):
        return self.dispatcher.addPolledListener(poller_uid, immediate_notify)
    
    def pollConnectionListener(self, poller_uid, timeout=None):
        return self.conn_notifier.poll(poller_uid, timeout=timeout)
    
    def cancelPollConnectionListener(self, poller_uid):
        self.conn_notifier.cancelPoll(poller_uid)

    def removeConnectionListener(self, listener_uid):
        self.conn_notifier.remove(listener_uid)
    
    def waitForConnectionListenerQueue(self, timeout):
        return self.conn_notifier.waitForQueue(timeout)

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
    # Client/Server Functions
    #
        
    def setNetworkIdentity(self, name):
        self.dispatcher.setIdentity(name)
    
    def getNetworkMode(self):
        return self.dispatcher.getNetworkMode()
    
    # python-specific
    def startTestMode(self, is_server):
        if self.dispatcher.startTestMode(is_server):
            self.storage.m_server = is_server
            return True
        else:
            return False
        
    def startServer(self, persist_filename, listen_address, port):
        return self.dispatcher.startServer(persist_filename, listen_address, port)
    
    def stopServer(self):
        self.dispatcher.stop()
        
    def startClient(self):
        return self.dispatcher.startClient()
        
    def stopClient(self):
        self.dispatcher.stop()
    
    def setServer(self, server_or_servers):
        self.dispatcher.setServer(server_or_servers)
        
    def setServerTeam(self, teamNumber, port):
        self.dispatcher.setServerTeam(teamNumber, port)
    
    def startDSClient(self, port):
        self.ds_client.start(port)
    
    def stopDSClient(self):
        self.ds_client.stop()
    
    def setUpdateRate(self, interval):
        self.dispatcher.setUpdateRate(interval)
    
    def flush(self):
        self.dispatcher.flush()
    
    def getRemoteAddress(self):
        if not self.dispatcher.isServer():
            for conn in self.dispatcher.getConnections():
                return conn.remote_ip
    
    def getIsConnected(self):
        return self.dispatcher.isConnected()
    
    def setVerboseLogging(self, verbose):
        self.conn_notifier.setVerboseLogging(verbose)
        self.dispatcher.setVerboseLogging(verbose)
        self.entry_notifier.setVerboseLogging(verbose)
        self.rpc_server.setVerboseLogging(verbose)
    
    #
    # Persistence
    #
    
    def savePersistent(self, filename):
        return self.storage.savePersistent(filename, periodic=False)
        
    def loadPersistent(self, filename):
        return self.storage.loadPersistent(filename)
    
    def saveEntries(self, filename, prefix):
        return self.storage.saveEntries(prefix, filename=filename)
    
    def loadEntries(self, filename, prefix):
        return self.storage.loadEntries(filename=filename, prefix=prefix)

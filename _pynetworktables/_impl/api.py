# validated: 2018-11-27 DS 8eafe7f32561 cpp/ntcore_cpp.cpp

from .connection_notifier import ConnectionNotifier
from .dispatcher import Dispatcher
from .ds_client import DsClient
from .entry_notifier import EntryNotifier
from .rpc_server import RpcServer
from .storage import Storage

from .constants import NT_NOTIFY_IMMEDIATE, NT_NOTIFY_NEW

_is_new = NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW


class NtCoreApi(object):
    """
    Internal NetworkTables API wrapper

    In theory you could create multiple instances of this
    and talk to multiple NT servers or create multiple
    NT servers... though, I don't really know why one
    would want to do this.
    """

    def __init__(self, entry_creator, verbose=False):
        self.conn_notifier = ConnectionNotifier(verbose=verbose)
        self.entry_notifier = EntryNotifier(verbose=verbose)
        self.rpc_server = RpcServer(verbose=verbose)
        self.storage = Storage(self.entry_notifier, self.rpc_server, entry_creator)
        self.dispatcher = Dispatcher(self.storage, self.conn_notifier, verbose=verbose)
        self.ds_client = DsClient(self.dispatcher, verbose=verbose)

        self._init_table_functions()

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
    # Table functions (inline because they're called often)
    #

    def _init_table_functions(self):
        self.getEntry = self.storage.getEntry
        self.getEntryId = self.storage.getEntryId
        self.getEntries = self.storage.getEntries
        self.getEntryNameById = self.storage.getEntryNameById
        self.getEntryTypeById = self.storage.getEntryTypeById
        self.getEntryValue = self.storage.getEntryValue
        self.setDefaultEntryValue = self.storage.setDefaultEntryValue
        self.setDefaultEntryValueById = self.storage.setDefaultEntryValueById
        self.setEntryValue = self.storage.setEntryValue
        self.setEntryValueById = self.storage.setEntryValueById
        self.setEntryTypeValue = self.storage.setEntryTypeValue
        self.setEntryTypeValueById = self.storage.setEntryTypeValueById
        self.setEntryFlags = self.storage.setEntryFlags
        self.setEntryFlagsById = self.storage.setEntryFlagsById
        self.getEntryFlags = self.storage.getEntryFlags
        self.getEntryFlagsById = self.storage.getEntryFlagsById
        self.deleteEntry = self.storage.deleteEntry
        self.deleteEntryById = self.storage.deleteEntryById
        self.deleteAllEntries = self.storage.deleteAllEntries
        self.getEntryInfo = self.storage.getEntryInfo
        self.getEntryInfoById = self.storage.getEntryInfoById

    #
    # Entry notification
    #

    def addEntryListener(self, prefix, callback, flags):
        return self.storage.addListener(prefix, callback, flags)

    def addEntryListenerById(self, local_id, callback, flags):
        return self.storage.addListenerById(local_id, callback, flags)

    def addEntryListenerByIdEx(
        self, fromobj, key, local_id, callback, flags, paramIsNew
    ):
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

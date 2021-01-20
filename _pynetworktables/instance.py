# todo: tracks NetworkTablesInstance.java

from typing import Any, Callable, List, Optional, Sequence, Tuple, Union
from weakref import WeakSet

from ._impl import constants
from ._impl.api import NtCoreApi

from .entry import NetworkTableEntry
from .table import NetworkTable

import logging

logger = logging.getLogger("nt")

__all__ = ["NetworkTablesInstance"]

ServerPortPair = Tuple[str, int]


class NetworkTablesInstance:
    """
    The object ``networktables.NetworkTables`` is a global singleton that
    you can use to initialize NetworkTables connections, configure global
    settings and listeners, and to create table objects which can be used
    to send data to/from NetworkTable servers and clients.

    First, you must initialize NetworkTables::

        from networktables import NetworkTables

        # As a client to connect to a robot
        NetworkTables.initialize(server='roborio-XXX-frc.local')

    Then, to interact with the SmartDashboard you get an instance of the
    table, and you can call the various methods::

        sd = NetworkTables.getTable('SmartDashboard')

        sd.putNumber('someNumber', 1234)
        otherNumber = sd.getNumber('otherNumber')

    You can create additional NetworkTablesInstance objects.
    Instances are completely independent from each other.  Table operations on
    one instance will not be visible to other instances unless the instances are
    connected via the network.  The main limitation on instances is that you
    cannot have two servers on the same network port.  The main utility of
    instances is for unit testing, but they can also enable one program to
    connect to two different NetworkTables networks.

    The global "default" instance (as returned by :meth:`.NetworkTablesInstance.getDefault`) is
    always available, and is intended for the common case when there is only
    a single NetworkTables instance being used in the program.

    Additional instances can be created with the :meth:`.create` function.

    .. seealso::
       - The examples in the documentation.
       - :class:`.NetworkTable`
    """

    class EntryTypes:
        """
        NetworkTable value types used in :meth:`.NetworkTable.getKeys`
        """

        #: True or False
        BOOLEAN = constants.NT_BOOLEAN

        #: Floating point number
        DOUBLE = constants.NT_DOUBLE

        #: Strings
        STRING = constants.NT_STRING

        #: Raw bytes
        RAW = constants.NT_RAW

        #: List of booleans
        BOOLEAN_ARRAY = constants.NT_BOOLEAN_ARRAY

        #: List of numbers
        DOUBLE_ARRAY = constants.NT_DOUBLE_ARRAY

        #: List of strings
        STRING_ARRAY = constants.NT_STRING_ARRAY

    class EntryFlags:
        """
        NetworkTables entry flags
        """

        #: Indicates a value that will be persisted on the server
        PERSISTENT = constants.NT_PERSISTENT

    class NotifyFlags:
        """
        Bitflags passed to entry callbacks
        """

        #: Initial listener addition
        IMMEDIATE = constants.NT_NOTIFY_IMMEDIATE

        #: Changed locally
        LOCAL = constants.NT_NOTIFY_LOCAL

        #: Newly created entry
        NEW = constants.NT_NOTIFY_NEW

        #: Key deleted
        DELETE = constants.NT_NOTIFY_DELETE

        #: Value changed
        UPDATE = constants.NT_NOTIFY_UPDATE

        #: Flags changed
        FLAGS = constants.NT_NOTIFY_FLAGS

    class NetworkModes:
        """
        Bitflags returend from :meth:`.getNetworkMode`
        """

        #: Not running
        NONE = constants.NT_NET_MODE_NONE

        #: Running in server mode
        SERVER = constants.NT_NET_MODE_SERVER

        #: Running in client mode
        CLIENT = constants.NT_NET_MODE_CLIENT

        #: Flag for starting (either client or server)
        STARTING = constants.NT_NET_MODE_STARTING

        #: Flag for failure (either client or server)
        FAILURE = constants.NT_NET_MODE_FAILURE

        #: Flag indicating in test mode
        TEST = constants.NT_NET_MODE_TEST

    #: The path separator for sub-tables and keys
    PATH_SEPARATOR = "/"

    #: The default port that network tables operates on
    DEFAULT_PORT = constants.NT_DEFAULT_PORT

    @classmethod
    def create(cls) -> "NetworkTablesInstance":
        """Create an instance.

        :returns: Newly created instance
        """
        return cls()

    @classmethod
    def getDefault(cls) -> "NetworkTablesInstance":
        """Get global default instance."""
        try:
            return cls._defaultInstance
        except AttributeError:
            pass

        cls._defaultInstance = cls()
        return cls._defaultInstance

    def __init__(self):
        self._init()

    def _init(self):
        self._api = NtCoreApi(self.__createEntry)
        self._tables = {}
        self._entry_listeners = {}
        self._conn_listeners = {}

        if not hasattr(self, "_ntproperties"):
            self._ntproperties = WeakSet()
        else:
            for ntprop in self._ntproperties:
                ntprop.reset()

    def __createEntry(self, key, local_id):
        return NetworkTableEntry(self._api, local_id, key)

    def getEntry(self, name: str) -> NetworkTableEntry:
        """Gets the entry for a key.

        :param name: Absolute path of key
        :returns: Network table entry.

        .. versionadded:: 2018.0.0
        """
        assert name.startswith("/")
        return self._api.getEntry(name)

    def getEntries(self, prefix: str, types: int = 0) -> Sequence[NetworkTableEntry]:
        """Get entries starting with the given prefix.
        The results are optionally filtered by string prefix and entry type to
        only return a subset of all entries.

        :param prefix: entry name required prefix; only entries whose name
                       starts with this string are returned
        :param types: bitmask of types; 0 is treated as a "don't care"
        :returns: List of matching entries.
        :rtype: list of :class:`.NetworkTableEntry`

        .. versionadded:: 2018.0.0
        """
        return self._api.getEntries(prefix, types)

    def getEntryInfo(self, prefix: str, types: int = 0) -> Sequence:
        """Get information about entries starting with the given prefix.
        The results are optionally filtered by string prefix and entry type to
        only return a subset of all entries.

        :param prefix: entry name required prefix; only entries whose name
                       starts with this string are returned
        :param types: bitmask of types; 0 is treated as a "don't care"
        :returns: List of entry information.

        .. versionadded:: 2018.0.0
        """
        return self._api.getEntryInfo(prefix, types)

    def getTable(self, key: str) -> NetworkTable:
        """Gets the table with the specified key.

        :param key: the key name

        :returns: the network table requested

        .. versionchanged:: 2018.0.0
           No longer automatically initializes network tables

        """

        # Must start with separator
        if key.startswith(self.PATH_SEPARATOR):
            path = key
        else:
            path = self.PATH_SEPARATOR + key

        # Must not end with separator
        if path.endswith(self.PATH_SEPARATOR):
            path = path[:-1]

        table = self._tables.get(path)
        if table is None:
            table = NetworkTable(path, self._api, self)
            table = self._tables.setdefault(path, table)
        return table

    def deleteAllEntries(self) -> None:
        """Deletes ALL keys in ALL subtables (except persistent values).
        Use with caution!

        .. versionadded:: 2018.0.0
        """
        self._api.deleteAllEntries()

    # Deprecated alias
    globalDeleteAll = deleteAllEntries

    def addEntryListener(
        self,
        listener: Callable[[str, Any, int], None],
        immediateNotify: bool = True,
        localNotify: bool = True,
        paramIsNew: bool = True,
    ) -> None:
        """Adds a listener that will be notified when any key in any
        NetworkTable is changed. The keys that are received using this
        listener will be full NetworkTable keys. Most users will not
        want to use this listener type.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        :param listener: A callable that has this signature: `callable(key, value, isNew)`
        :param immediateNotify: If True, the listener will be called immediately with the current values of the table
        :param localNotify: True if you wish to be notified of changes made locally (default is True)
        :param paramIsNew: If True, the listener third parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags

        .. versionadded:: 2015.2.0

        .. versionchanged:: 2017.0.0
           `paramIsNew` parameter added

        .. versionchanged:: 2018.0.0
           Renamed to addEntryListener, no longer initializes NetworkTables

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        """
        gtable = self.getTable("/")
        gtable.addTableListener(
            listener,
            immediateNotify=immediateNotify,
            key=0xDEADBEEF,
            localNotify=localNotify,
        )

    def addEntryListenerEx(
        self,
        listener: Callable[[str, Any, int], None],
        flags: int,
        paramIsNew: bool = True,
    ) -> None:
        """Adds a listener that will be notified when any key in any
        NetworkTable is changed. The keys that are received using this
        listener will be full NetworkTable keys. Most users will not
        want to use this listener type.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        :param listener: A callable that has this signature: `callable(key, value, isNew)`
        :param flags: Bitmask of flags that indicate the types of notifications you wish to receive
        :type flags: :class:`.NotifyFlags`
        :param paramIsNew: If True, the listener third parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags

        .. versionadded:: 2017.0.0

        .. versionchanged:: 2018.0.0
           Renamed to addEntryListenerEx, no longer initializes NetworkTables

        """
        gtable = self.getTable("/")
        gtable.addTableListenerEx(
            listener, flags, key=0xDEADBEEF, paramIsNew=paramIsNew
        )

    # deprecated aliases
    addGlobalListener = addEntryListener
    addGlobalListenerEx = addEntryListenerEx

    def removeEntryListener(self, listener: Callable[[str, Any, int], None]) -> None:
        """Remove an entry listener.

        :param listener: Listener to remove

        .. versionadded:: 2018.0.0

        """
        self.getTable("/").removeEntryListener(listener)

    # Deprecated alias
    removeGlobalListener = removeEntryListener

    def waitForEntryListenerQueue(self, timeout: float) -> bool:
        """Wait for the entry listener queue to be empty.  This is primarily useful
        for deterministic testing.  This blocks until either the entry listener
        queue is empty (e.g. there are no more events that need to be passed along
        to callbacks or poll queues) or the timeout expires.

        .. warning:: This function is not efficient, so only use it for testing!

        :param timeout: timeout, in seconds.  Set to 0 for non-blocking behavior,
                        or None to block indefinitely
        :returns: False if timed out, otherwise true.
        """
        return self._api.waitForEntryListenerQueue(timeout)

    def addConnectionListener(self, listener: Callable, immediateNotify: bool = False):
        """Adds a listener that will be notified when a new connection to a
        NetworkTables client/server is established.

        The listener is called from a NetworkTables owned thread and should
        return as quickly as possible.

        :param listener: A function that will be called with two parameters
        :type listener: fn(bool, ConnectionInfo)

        :param immediateNotify: If True, the listener will be called immediately
                                with any active connection information

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended.

        .. versionchanged:: 2017.0.0
           The listener is now a function
        """
        assert callable(listener)
        cb = lambda info: listener(info.connected, info.conn_info)
        listener_id = self._api.addConnectionListener(cb, immediateNotify)
        self._conn_listeners.setdefault(listener, []).append(listener_id)

    def removeConnectionListener(self, listener: Callable):
        """Removes a connection listener

        :param listener: The function registered for connection notifications
        """
        for listener_id in self._conn_listeners.pop(listener, []):
            self._api.removeConnectionListener(listener_id)

    def waitForConnectionListenerQueue(self, timeout: float) -> bool:
        """Wait for the connection listener queue to be empty.  This is primarily useful
        for deterministic testing.  This blocks until either the connection listener
        queue is empty (e.g. there are no more events that need to be passed along
        to callbacks or poll queues) or the timeout expires.

        :param timeout: timeout, in seconds.  Set to 0 for non-blocking behavior,
                        or a negative value to block indefinitely
        :returns: False if timed out, otherwise true.

        .. versionadded:: 2018.0.0
        """
        return self._api.waitForConnectionListenerQueue(timeout)

    #
    # Client/Server functions
    #

    def setNetworkIdentity(self, name: str) -> None:
        """Sets the network identity of this node. This is the name used in the
        initial connection handshake, and is provided in the connection info
        on the remote end.

        :param name: A string to communicate to other NetworkTables instances

        .. versionadded:: 2017.0.0
        """
        self._api.setNetworkIdentity(name)

    def getNetworkMode(self):
        """Get the current network mode

        .. versionadded:: 2018.0.0
        """
        return self._api.getNetworkMode()

    def isServer(self) -> bool:
        """:returns: True if configured in server mode"""
        return (self.getNetworkMode() & self.NetworkModes.SERVER) != 0

    def startServer(
        self,
        persistFilename: str = "networktables.ini",
        listenAddress: str = "",
        port: int = constants.NT_DEFAULT_PORT,
    ):
        """Starts a server using the specified filename, listening address, and port.

        :param persistFilename: the name of the persist file to use
        :param listenAddress: the address to listen on, or empty to listen on any
                              address
        :param port: port to communicate over

        .. versionadded:: 2018.0.0
        """
        return self._api.startServer(persistFilename, listenAddress, port)

    def stopServer(self) -> None:
        """Stops the server if it is running.

        .. versionadded:: 2018.0.0
        """
        self._api.stopServer()

    def startClient(
        self,
        server_or_servers: Union[str, ServerPortPair, List[ServerPortPair], List[str]],
    ):
        """Sets server addresses and port for client (without restarting client).
        The client will attempt to connect to each server in round robin fashion.

        :param server_or_servers: a string, a tuple of (server, port), array of
                                  (server, port), or an array of strings

        .. versionadded:: 2018.0.0
        """
        self.setServer(server_or_servers)
        return self._api.startClient()

    def startClientTeam(self, team: int, port: int = constants.NT_DEFAULT_PORT):
        """Starts a client using commonly known robot addresses for the specified
        team.

        :param team: team number
        :param port: port to communicate over

        .. versionadded:: 2018.0.0
        """
        self.setServerTeam(team, port)
        return self._api.startClient()

    def stopClient(self) -> None:
        """Stops the client if it is running.

        .. versionadded:: 2018.0.0
        """
        self._api.stopClient()

    def setServer(
        self,
        server_or_servers: Union[str, ServerPortPair, List[ServerPortPair], List[str]],
    ) -> None:
        """Sets server addresses and port for client (without restarting client).
        The client will attempt to connect to each server in round robin fashion.

        :param server_or_servers: a string, a tuple of (server, port), array of
                                  (server, port), or an array of strings

        .. versionadded:: 2018.0.0
        """
        if isinstance(server_or_servers, list):
            server_or_servers = [
                item if isinstance(item, tuple) else (item, constants.NT_DEFAULT_PORT)
                for item in server_or_servers
            ]
        elif isinstance(server_or_servers, str):
            server_or_servers = [(server_or_servers, constants.NT_DEFAULT_PORT)]

        self._api.setServer(server_or_servers)

    def setServerTeam(self, team: int, port: int = constants.NT_DEFAULT_PORT) -> None:
        """Sets server addresses and port for client based on the team number
        (without restarting client). The client will attempt to connect to each
        server in round robin fashion.

        :param team: Team number
        :param port: Port to communicate over

        .. versionadded:: 2018.0.0
        """
        self._api.setServerTeam(team, port)

    def startDSClient(self, port: int = constants.NT_DEFAULT_PORT) -> None:
        """Starts requesting server address from Driver Station.
        This connects to the Driver Station running on localhost to obtain the
        server IP address.

        :param port: server port to use in combination with IP from DS

        .. versionadded:: 2018.0.0
           Was formerly called setDashboardMode
        """
        self._api.startDSClient(port)

    setDashboardMode = startDSClient

    def setUpdateRate(self, interval: float) -> None:
        """Sets the period of time between writes to the network.

        WPILib's networktables and SmartDashboard default to 100ms, we have
        set it to 50ms instead for quicker response time. You should not set
        this value too low, as it could potentially increase the volume of
        data sent over the network.

        :param interval: Write flush period in seconds (default is 0.050,
                         or 50ms)

        .. warning:: If you don't know what this setting affects, don't mess
                     with it!

        .. versionadded:: 2017.0.0
        """
        self._api.setUpdateRate(interval)

    def flush(self) -> None:
        """Flushes all updated values immediately to the network.

        .. note:: This is rate-limited to protect the network from flooding.
                  This is primarily useful for synchronizing network updates
                  with user code.

        .. versionadded:: 2017.0.0
        """
        self._api.flush()

    def getConnections(self) -> Sequence:
        """Gets information on the currently established network connections.
        If operating as a client, this will return either zero or one values.

        :returns: list of connection information
        :rtype: list

        .. versionadded:: 2018.0.0
        """
        return self._api.getConnections()

    def getRemoteAddress(self) -> Optional[str]:
        """
        Only returns a valid address if connected to the server. If
        this is a server, returns None

        :returns: IP address of server or None

        .. versionadded:: 2015.3.2
        """
        return self._api.getRemoteAddress()

    def isConnected(self) -> bool:
        """
        :returns: True if connected to at least one other NetworkTables
                  instance
        """
        return self._api.getIsConnected()

    def savePersistent(self, filename: str):
        """Saves persistent keys to a file. The server does this automatically.

        :param filename: Name of file to save keys to

        :returns: None if success, or a string describing the error on failure

        .. versionadded:: 2017.0.0
        """
        return self._api.savePersistent(filename)

    def loadPersistent(self, filename: str):
        """Loads persistent keys from a file. WPILib will do this automatically
        on a robot server.

        :param filename: Name of file to load keys from

        :returns: None if success, or a string describing the error on failure

        .. versionadded:: 2017.0.0
        """
        return self._api.loadPersistent(filename)

    def saveEntries(self, filename: str, prefix: str):
        """Save table values to a file.  The file format used is identical to
        that used for SavePersistent.

        :param filename: filename
        :param prefix: save only keys starting with this prefix

        :returns: None if success, or a string describing the error on failure

        .. versionadded:: 2018.0.0
        """
        return self._api.saveEntries(filename, prefix)

    def loadEntries(self, filename: str, prefix: str):
        """Load table values from a file.  The file format used is identical to
        that used for SavePersistent / LoadPersistent.

        :param filename: filename
        :param prefix: load only keys starting with this prefix

        :returns: None if success, or a string describing the error on failure

        .. versionadded:: 2018.0.0
        """
        return self._api.loadEntries(filename, prefix)

    #
    # These methods are unique to pynetworktables
    #

    def initialize(self, server=None):
        """Initializes NetworkTables and begins operations

        :param server: If specified, NetworkTables will be set to client
                       mode and attempt to connect to the specified server.
                       This is equivalent to executing::

                           self.startClient(server)
        :type server: str

        :returns: True if initialized, False if already initialized

        .. versionadded:: 2017.0.0
           The *server* parameter
        """

        if server is not None:
            return self.startClient(server)
        else:
            return self.startServer()

    def shutdown(self) -> None:
        """Stops all NetworkTables activities and unregisters all tables
        and callbacks. You can call :meth:`.initialize` again after
        calling this.

        .. versionadded:: 2017.0.0
        """

        self._api.stop()
        self._api.destroy()

        self._init()

    def startTestMode(self, server: bool = True):
        """Setup network tables to run in unit test mode, and enables verbose
        logging.

        :returns: True if successful

        .. versionadded:: 2018.0.0
        """
        self.enableVerboseLogging()
        return self._api.startTestMode(server)

    def enableVerboseLogging(self) -> None:
        """Enable verbose logging that can be useful when trying to diagnose
        NetworkTables issues.

        .. warning:: Don't enable this in normal use, as it can potentially
                     cause performance issues due to the volume of logging.

        .. versionadded:: 2017.0.0
        """
        self._api.setVerboseLogging(True)

    def getGlobalTable(self) -> NetworkTable:
        """Returns an object that allows you to write values to absolute
        NetworkTable keys (which are paths with / separators).

        .. note:: This is now an alias for ``NetworkTables.getTable('/')``

        .. versionadded:: 2015.2.0
        .. versionchanged:: 2017.0.0
           Returns a NetworkTable instance
        .. versionchanged:: 2018.0.0
           No longer automatically initializes network tables
        """
        return self.getTable("/")

    def getGlobalAutoUpdateValue(
        self, key: str, defaultValue, writeDefault: bool
    ) -> NetworkTableEntry:
        """Global version of getAutoUpdateValue.

        :param key: the full NT path of the value (must start with /)
        :param defaultValue: The default value to return if the key doesn't exist
        :param writeDefault: If True, force the value to the specified default

        :rtype: :class:`.NetworkTableEntry`

        .. seealso:: :func:`.ntproperty` is a read-write alternative to this

        .. versionadded:: 2015.3.0

        .. versionchanged:: 2018.0.0
           This now returns the same as :meth:`NetworkTablesInstance.getEntry`
        """
        assert key.startswith("/")

        entry = self.getEntry(key)
        if writeDefault:
            entry.forceSetValue(defaultValue)
        else:
            entry.setDefaultValue(defaultValue)

        return entry

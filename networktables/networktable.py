
import threading

from networktables2 import (
    DefaultEntryTypes,
    NetworkTableClient,
    NetworkTableServer,
    SocketStreamFactory,
    SocketServerStreamProvider
)

__all__ = ["NetworkTable"]

class NetworkTableConnectionListenerAdapter:
    """An adapter that changes the source of a connection event
    """

    def __init__(self, targetSource, targetListener):
        """
        :param targetSource: the source where the event will appear to come
                             from
        :param targetListener: the listener where events will be forwarded
        """
        self.targetSource = targetSource
        self.targetListener = targetListener
        
        assert callable(self.targetListener.connected)
        assert callable(self.targetListener.disconnected)
    
    def connected(self, remote):
        self.targetListener.connected(self.targetSource)

    def disconnected(self, remote):
        self.targetListener.disconnected(self.targetSource)

class NetworkTableGlobalListenerAdapter:

    def __init__(self, listener):
        self.listener = listener
        assert callable(self.listener)

    def valueChanged(self, source, key, value, isNew):
        self.listener(key, value, isNew)

class NetworkTableKeyListenerAdapter:
    """An adapter that is used to filter value change notifications for a
    specific key
    """

    def __init__(self, relativeKey, fullKey, targetSource, targetListener):
        """Create a new adapter
        
        :param relativeKey: the name of the key relative to the table (this
                            is what the listener will receiver as the key)
        :param fullKey: the full name of the key in the NetworkTableNode
        :param targetSource: the source that events passed to the target
                             listener will appear to come from
        :param targetListener: the callable where events are forwarded to
        """
        assert callable(targetListener)
        self.relativeKey = relativeKey
        self.fullKey = fullKey
        self.targetSource = targetSource
        self.targetListener = targetListener

    def valueChanged(self, source, key, value, isNew):
        if key == self.fullKey:
            self.targetListener(self.targetSource,
                                self.relativeKey, value, isNew)

class NetworkTableListenerAdapter:
    """An adapter that is used to filter value change notifications and make
    the path relative to the NetworkTable
    """

    def __init__(self, prefix, targetSource, targetListener):
        """Create a new adapter
        
        :param prefix: the prefix that will be filtered/removed from the
                       beginning of the key
        :param targetSource: the source that events passed to the target
                             listener will appear to come from
        :param targetListener: the callable where events are forwarded to
        """
        assert callable(targetListener)
        self.prefix = prefix
        self.targetSource = targetSource
        self.targetListener = targetListener

    def valueChanged(self, source, key, value, isNew):
        #TODO use string cache
        if key.startswith(self.prefix):
            relativeKey = key[len(self.prefix):]
            if NetworkTable.PATH_SEPARATOR in relativeKey:
                return
            self.targetListener(self.targetSource, relativeKey,
                                value, isNew)

class NetworkTableSubListenerAdapter:
    """An adapter that is used to filter sub table change notifications and
    make the path relative to the NetworkTable
    """

    def __init__(self, prefix, targetSource, targetListener):
        """Create a new adapter
        
        :param prefix: the prefix of the current table
        :param targetSource: the source that events passed to the target
                             listener will appear to come from
        :param targetListener: the callable where events are forwarded to
        """
        assert callable(targetListener)
        self.prefix = prefix
        self.targetSource = targetSource
        self.targetListener = targetListener
        self.notifiedTables = set()

    def valueChanged(self, source, key, value, isNew):
        #TODO use string cache
        if not key.startswith(self.prefix):
            return

        key = key[len(self.prefix):]

        if key.startswith(NetworkTable.PATH_SEPARATOR):
            key = key[len(NetworkTable.PATH_SEPARATOR):]

        #TODO implement sub table listening better
        keysplit = key.split(NetworkTable.PATH_SEPARATOR)
        if len(keysplit) < 2:
            return

        subTableKey = keysplit[0]

        if subTableKey in self.notifiedTables:
            return

        self.notifiedTables.add(subTableKey)
        self.targetListener(self.targetSource, subTableKey,
                self.targetSource.getSubTable(subTableKey), True)

class AutoUpdateValue:
    """Holds a value from NetworkTables, and changes it as new entries
    come in. Updates to this value are NOT passed on to NetworkTables.
    
    Do not create this object directly, as it only holds the value. 
    Use :meth:`.NetworkTable.getAutoUpdateValue` to obtain an instance
    of this.
    """
    
    __slots__ = ['__value']
    
    def __init__(self, default):
        self.__value = default
        
    def get(self):
        '''Returns the value held by this object'''
        return self.__value
    
    @property
    def value(self):
        return self.__value
    
    # Comparison operators et al
    
    def __lt__(self, other):
        raise TypeError("< not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    def __le__(self, other):
        raise TypeError("<= not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    def __eq__(self, other):
        raise TypeError("== not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    def __ne__(self, other):
        raise TypeError("!= not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    def __gt__(self, other):
        raise TypeError("> not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    def __ge__(self, other):
        raise TypeError(">= not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    
    def __bool__(self):
        raise TypeError("< not allowed on AutoUpdateValue objects. Use the .value attribute instead")
    
    def __hash__(self):
        raise TypeError("__hash__ not allowed on AutoUpdateValue objects")
    
    def __repr__(self):
        return '<AutoUpdateValue: %s>' % (self.__value.__repr__(), )

class AutoUpdateListener:
    
    def __init__(self, table):
        # no lock required if we use atomic operations (setdefault, get) on it
        self.keys = {}
        table.addTableListener(self._valueChanged)
        
    def createAutoValue(self, key, default):
        new_value = AutoUpdateValue(default)
        return self.keys.setdefault(key, new_value)
    
    def _valueChanged(self, table, key, value, isNew):
        auto_value = self.keys.get(key)
        if auto_value is not None:
            auto_value._AutoUpdateValue__value = value


class NetworkTableProvider:
    """Provides a NetworkTable for a given NetworkTableNode
    """

    def __init__(self, node):
        """Create a new NetworkTableProvider for a given NetworkTableNode
        
        :param node: the node that handles the actual network table
        """
        self.node = node
        self.tables = {}
        self.global_listeners = {}

    def getRootTable(self):
        return self.getTable("")

    def getTable(self, key):
        table = self.tables.get(key)
        if table is None:
            table = NetworkTable(key, self)
            self.tables[key] = table
        return table

    def getNode(self):
        """:returns: the Network Table node that backs the Tables returned by
        this provider
        """
        return self.node

    def close(self):
        """close the backing network table node
        """
        self.node.stop()

    def addGlobalListener(self, listener, immediateNotify):
        adapter = self.global_listeners.get(listener)
        if adapter is None:
            adapter = NetworkTableGlobalListenerAdapter(listener)
            self.global_listeners[listener] = adapter
            self.node.addTableListener(adapter, immediateNotify)

    def removeGlobalListener(self, listener):
        adapter = self.global_listeners.get(listener)
        if adapter is not None:
            self.node.removeTableListener(adapter)
            del self.global_listeners[listener]


def _create_server_node(ipAddress, port):
    """Creates a network tables server node
    
    :param ipAddress: the IP address configured by the user
    :param port: the port configured by the user
    :returns: a new node that can back a network table
    """
    return NetworkTableServer(SocketServerStreamProvider(port))

def _create_client_node(ipAddress, port):
    """Creates a network tables client node
    
    :param ipAddress: the IP address configured by the user
    :param port: the port configured by the user
    :returns: a new node that can back a network table
    """
    if ipAddress is None:
        raise ValueError("IP address cannot be None when in client mode")
    client = NetworkTableClient(SocketStreamFactory(ipAddress, port))
    return client
    
def _create_test_node(ipAddress, port):
    
    class NullStreamFactory:
        def createStream(self):
            return None
        
    return NetworkTableClient(NullStreamFactory())
    
    
class NetworkTable:
    """
    This is the primary object that you will use when interacting with
    NetworkTables. You should not directly create a NetworkTable object,
    but instead use the :meth:`getTable` method to create an appropriate
    object instead.

    For example, to interact with the SmartDashboard::

        from networktables import NetworkTable
        sd = NetworkTable.getTable('SmartDashboard')

        sd.putNumber('someNumber', 1234)
        ...

    """

    #: The path separator for sub-tables and keys
    PATH_SEPARATOR = '/'
    #: The default port that network tables operates on
    DEFAULT_PORT = 1735

    _staticProvider = None
    _mode_fn = staticmethod(_create_server_node)
    
    port = DEFAULT_PORT
    ipAddress = None

    _staticMutex = threading.RLock()

    class _defaultValueSentry:
        pass

    @staticmethod
    def checkInit():
        with NetworkTable._staticMutex:
            if NetworkTable._staticProvider is not None:
                raise RuntimeError("Network tables has already been initialized")

    @staticmethod
    def initialize():
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable._staticProvider = NetworkTableProvider(
                    NetworkTable._mode_fn(NetworkTable.ipAddress,
                                          NetworkTable.port))

    @staticmethod
    def setTableProvider(provider):
        """set the table provider for static network tables methods
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable._staticProvider = provider

    @staticmethod
    def setServerMode():
        """set that network tables should be a server (this is the default)
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable._mode_fn = staticmethod(_create_server_node)

    @staticmethod
    def setClientMode():
        """set that network tables should be a client
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable._mode_fn = staticmethod(_create_client_node)
            
    @staticmethod
    def setTestMode():
        """Setup network tables to run in unit test mode
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable._mode_fn = staticmethod(_create_test_node)

    @staticmethod
    def setTeam(team):
        """set the team the robot is configured for (this will set the ip
        address that network tables will connect to in client mode)
        
        :param team: the team number
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        NetworkTable.setIPAddress("10.%d.%d.2" % divmod(team, 100))

    @staticmethod
    def setIPAddress(address):
        """:param address: the adress that network tables will connect to in
            client mode
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with NetworkTable._staticMutex:
            NetworkTable.checkInit()
            NetworkTable.ipAddress = address

    @staticmethod
    def setWriteFlushPeriod(flushPeriod):
        """Sets the period of time between writes to the network. 
        
        WPILib's networktables and SmartDashboard default to 100ms, we have
        set it to 50ms instead for quicker response time. You should not set
        this value too low, as it could potentially increase the volume of
        data sent over the network.
        
        .. warning:: If you don't know what this setting affects, don't mess
                     with it!
        
        :param latency: Write flush period in seconds (default is 0.050,
                        or 50ms)
        """
        from networktables2.client import WriteManager
        WriteManager.SLEEP_TIME = flushPeriod

    @staticmethod
    def getTable(key):
        """Gets the table with the specified key. If the table does not exist,
        a new table will be created.

        This will automatically initialize network tables if it has not been
        already

        :param key: the key name
        :returns: the network table requested
        :rtype: :class:`NetworkTable`
        """
        with NetworkTable._staticMutex:
            if NetworkTable._staticProvider is None:
                NetworkTable.initialize()
            if not key.startswith(NetworkTable.PATH_SEPARATOR):
                key = NetworkTable.PATH_SEPARATOR + key
            return NetworkTable._staticProvider.getTable(key)

    @staticmethod
    def getGlobalTable():
        """Returns an object that allows you to write values to raw network table
        keys (which are paths with / separators).

        This will automatically initialize network tables if it has not been
        already.

        .. warning:: Generally, you should not use this object. Prefer to use
                     :meth:`getTable` instead and do operations on individual
                     NetworkTables.

        .. versionadded:: 2015.2.0

        :rtype: :class:`.NetworkTableNode`
        """
        with NetworkTable._staticMutex:
            if NetworkTable._staticProvider is None:
                NetworkTable.initialize()
            return NetworkTable._staticProvider.getNode()

    @staticmethod
    def addGlobalListener(listener, immediateNotify=True):
        '''Adds a listener that will be notified when any key in any
        NetworkTable is changed. The keys that are received using this
        listener will be full NetworkTable keys. Most users will not
        want to use this listener type.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        This will automatically initialize network tables if it has not been
        already.

        :param listener: A callable that has this signature: `callable(key, value, isNew)`
        :param immediateNotify: If True, the listener will be called immediately with the current values of the table

        .. versionadded:: 2015.2.0

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        '''
        with NetworkTable._staticMutex:
            if NetworkTable._staticProvider is None:
                NetworkTable.initialize()
            NetworkTable._staticProvider.addGlobalListener(listener, immediateNotify)

    @staticmethod
    def removeGlobalListener(listener):
        '''Removes a global listener

        .. versionadded:: 2015.2.0
        '''
        with NetworkTable._staticMutex:
            NetworkTable._staticProvider.removeGlobalListener(listener)

    def __init__(self, path, provider):
        self.path = path
        self.absoluteKeyCache = NetworkTable._KeyCache(path)
        self.provider = provider
        self.node = provider.getNode()
        self.connectionListenerMap = {}
        self.listenerMap = {}
        self.mutex = threading.RLock()
        
        self.autoListener = None

    def __str__(self):
        return "NetworkTable: "+self.path

    def isConnected(self):
        return self.node.isConnected()

    def isServer(self):
        return self.node.isServer()

    class _KeyCache:
        def __init__(self, path):
            if path[-len(NetworkTable.PATH_SEPARATOR):] == NetworkTable.PATH_SEPARATOR:
                path = path[:-len(NetworkTable.PATH_SEPARATOR)]
            self.path = path
            self.cache = {}

        def get(self, key):
            cachedValue = self.cache.get(key)
            if cachedValue is None:
                cachedValue = self.path + NetworkTable.PATH_SEPARATOR + key
                self.cache[key] = cachedValue
            return cachedValue

    def addConnectionListener(self, listener, immediateNotify=False):
        '''Adds a listener that will be notified when a new connection to a 
        NetworkTables client/server is established.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: An object that has a 'connected' function and a
                         'disconnected' function. Each function will be called
                         with this NetworkTable object as the first parameter
        :param immediateNotify: If True, the listener will be called immediately
                                with the current values of the table
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        '''
        adapter = self.connectionListenerMap.get(listener)
        if adapter is not None:
            raise ValueError("Cannot add the same listener twice")
        adapter = NetworkTableConnectionListenerAdapter(self, listener)
        self.connectionListenerMap[listener] = adapter
        self.node.addConnectionListener(adapter, immediateNotify)

    def removeConnectionListener(self, listener):
        '''Removes a connection listener
        
        :param listener: The object registered for connection notifications
        '''
        adapter = self.connectionListenerMap.get(listener)
        if adapter is not None:
            self.node.removeConnectionListener(adapter)
            del self.connectionListenerMap[listener]

    def addTableListener(self, listener, immediateNotify=False, key=None):
        '''Adds a listener that will be notified when any key in this
        NetworkTable is changed, or when a specified key changes.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: A callable that has this signature: `callable(source, key, value, isNew)`
        :param immediateNotify: If True, the listener will be called immediately with the current values of the table
        :param key: If specified, the listener will only be called when this key is changed
        
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        '''
        adapters = self.listenerMap.setdefault(listener, [])
        if key is not None:
            adapter = NetworkTableKeyListenerAdapter(
                    key, self.absoluteKeyCache.get(key), self, listener)
        else:
            adapter = NetworkTableListenerAdapter(
                    self.path+self.PATH_SEPARATOR, self, listener)
        adapters.append(adapter)
        self.node.addTableListener(adapter, immediateNotify)

    def addSubTableListener(self, listener):
        '''Adds a listener that will be notified when any key in a subtable of
        this NetworkTable is changed.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: A callable that has this signature: `callable(source, key, value, isNew)`
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        '''
        adapters = self.listenerMap.setdefault(listener, [])
        adapter = NetworkTableSubListenerAdapter(self.path, self, listener)
        adapters.append(adapter)
        self.node.addTableListener(adapter, True)

    def removeTableListener(self, listener):
        '''Removes a table listener
        
        :param listener: callable that was passed to :meth:`addTableListener`
                         or :meth:`addSubTableListener`
        '''
        adapters = self.listenerMap.get(listener)
        if adapters is not None:
            for adapter in adapters:
                self.node.removeTableListener(adapter)
            del adapters[:]

    def getSubTable(self, key):
        """Returns the table at the specified key. If there is no table at the
        specified key, it will create a new table

        :param key: the key name
        :returns: the networktable to be returned
        :rtype: :class:`NetworkTable`
        """
        with self.mutex:
            return self.provider.getTable(self.absoluteKeyCache.get(key))

    def containsKey(self, key):
        """Checks the table and tells if it contains the specified key

        :param key: the key to be checked
        """
        with self.mutex:
            return self.node.containsKey(self.absoluteKeyCache.get(key))

    def __contains__(self, key):
        return self.containsKey(key)

    def containsSubTable(self, key):
        subtablePrefix = self.absoluteKeyCache.get(key)+self.PATH_SEPARATOR
        for key in self.node.getEntryStore().keys():
            if key.startswith(subtablePrefix):
                return True
        return False

    def putNumber(self, key, value):
        """Maps the specified key to the specified value in this table. The key
        can not be None. The value can be retrieved by calling the get method
        with a key that is equal to the original key.

        :param key: the key
        :param value: the value
        """
        self.node.putValue(self.absoluteKeyCache.get(key), float(value), DefaultEntryTypes.DOUBLE)

    def getNumber(self, key, defaultValue=_defaultValueSentry):
        """Returns the key that the name maps to. If the key is None, it will
        return the default value (or raise KeyError if a default value is not
        provided).

        :param key: the key name
        :param defaultValue: the default value if the key is None.  If not
                             specified, raises KeyError if the key is None.
        :returns: the key
        """
        try:
            return self.node.getDouble(self.absoluteKeyCache.get(key))
        except KeyError:
            if defaultValue is NetworkTable._defaultValueSentry:
                raise
            return defaultValue

    def putString(self, key, value):
        """Maps the specified key to the specified value in this table. The key
        can not be None. The value can be retrieved by calling the get method
        with a key that is equal to the original key.

        :param key: the key
        :param value: the value
        """
        self.node.putValue(self.absoluteKeyCache.get(key), str(value), DefaultEntryTypes.STRING)

    def getString(self, key, defaultValue=_defaultValueSentry):
        """Returns the key that the name maps to. If the key is None, it will
        return the default value (or raise KeyError if a default value is not
        provided).

        :param key: the key name
        :param defaultValue: the default value if the key is None.  If not
                             specified, raises KeyError if the key is None.
        :returns: the key
        """
        try:
            return self.node.getString(self.absoluteKeyCache.get(key))
        except KeyError:
            if defaultValue is NetworkTable._defaultValueSentry:
                raise
            return defaultValue

    def putBoolean(self, key, value):
        """Maps the specified key to the specified value in this table. The key
        can not be None. The value can be retrieved by calling the get method
        with a key that is equal to the original key.

        :param key: the key
        :param value: the value
        """
        self.node.putValue(self.absoluteKeyCache.get(key), bool(value), DefaultEntryTypes.BOOLEAN)

    def getBoolean(self, key, defaultValue=_defaultValueSentry):
        """Returns the key that the name maps to. If the key is None, it will
        return the default value (or raise KeyError if a default value is not
        provided).

        :param key: the key name
        :param defaultValue: the default value if the key is None.  If not
                             specified, raises KeyError if the key is None.
        :returns: the key
        """
        try:
            return self.node.getBoolean(self.absoluteKeyCache.get(key))
        except KeyError:
            if defaultValue is NetworkTable._defaultValueSentry:
                raise
            return defaultValue

    def retrieveValue(self, key, externalValue):
        """Retrieves the data associated with a complex data type (such as
        arrays) and stores it.
        
        For example, to retrieve a type which is an array of strings::
        
            val = networktables.StringArray()
            nt.retrieveValue('some key', val)
            
        :param key: the key name
        :param externalValue: The complex data member
        """
        self.node.retrieveValue(self.absoluteKeyCache.get(key), externalValue)

    def putValue(self, key, value):
        """Maps the specified key to the specified value in this table. The key
        can not be None. The value can be retrieved by calling the get method
        with a key that is equal to the original key.

        :param key: the key name
        :param value: the value to be put
        """
        self.node.putValue(self.absoluteKeyCache.get(key), value)

    def getValue(self, key, defaultValue=_defaultValueSentry):
        """Returns the key that the name maps to. If the key is None, it will
        return the default value (or raise KeyError if a default value is not
        provided).

        :param key: the key name
        :param defaultValue: the default value if the key is None.  If not
                             specified, raises KeyError if the key is None.
        :returns: the key
        """
        try:
            return self.node.getValue(self.absoluteKeyCache.get(key))
        except KeyError:
            if defaultValue is NetworkTable._defaultValueSentry:
                raise
            return defaultValue
    
    def getAutoUpdateValue(self, key, defaultValue, writeDefault=True):
        '''Returns an object that will be automatically updated when the
        value is updated by networktables.
        
        Does not work with complex types. If you modify the returned type,
        the value will NOT be written back to NetworkTables.
        
        :param key: the key name
        :type  key: str
        :param defaultValue: Default value to use if not in the table
        :type  defaultValue: any
        :param writeDefault: If True, put the default value to the table,
                             overwriting existing values
        :type  writeDefault: bool
        
        :rtype: :class:`.AutoUpdateValue`
        
        .. versionadded:: 2015.1.3
        '''
        
        value = defaultValue
        
        if writeDefault:
            self.putValue(key, value)
        else:
            try:
                value = self.getValue(key)
            except KeyError:
                self.putValue(key, value)
        
        with self.mutex:
            if self.autoListener is None:
                self.autoListener = AutoUpdateListener(self)
        
        return self.autoListener.createAutoValue(key, value)

    # Deprecated Methods
    putInt = putNumber
    getInt = getNumber
    putDouble = putNumber
    getDouble = getNumber
    


import threading

from ntcore import constants
from ntcore.api import NtCoreApi
from ntcore.value import Value

from .autovalue import AutoUpdateValue

import logging
logger = logging.getLogger('nt')

__all__ = ["NetworkTables"]


class NetworkTables:
    """
    This is the global singleton that you use to initialize NetworkTables
    connections, configure global settings and listeners, and to create
    NetworkTable instances which can be used to send data to/from
    NetworkTable servers and clients.
    
    First, you must initialize NetworkTables::
    
        from networktables import NetworkTables
        
        # As a client to connect to a robot
        NetworkTables.initialize(server='roborio-XXX-frc.local')
    

    Then, to interact with the SmartDashboard you get an instance of the
    table, and you can call the various methods::

        sd = NetworkTables.getTable('SmartDashboard')
        
        sd.putNumber('someNumber', 1234)
        otherNumber = sd.getNumber('otherNumber')
        ...
        
    .. seealso::
       - The examples in the documentation.
       - :class:`.NetworkTable`
    """
    
    class EntryTypes:
        '''
            NetworkTable value types used in :meth:`.NetworkTable.getKeys`
        '''
        
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
        '''
            NetworkTables entry flags
        '''
        
        #: Indicates a value that will be persisted on the server
        PERSISTENT = constants.NT_PERSISTENT
    
    class NotifyFlags:
        '''
            Bitflags passed to entry callbacks
        '''
        
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
    
    
    
    
    #: The path separator for sub-tables and keys
    PATH_SEPARATOR = '/'
    #: The default port that network tables operates on
    DEFAULT_PORT = 1735
    
    _persistentFilename = None
    
    port = DEFAULT_PORT
    ipAddress = None
    _serverListenAddress = ""
    
    _mode = 'server'
    _running = False
    _tables = {}

    _staticMutex = threading.RLock()

    _api = NtCoreApi()
    _identity = None

    @classmethod
    def _checkInit(cls):
        with cls._staticMutex:
            if cls._running:
                raise RuntimeError("Network tables has already been initialized")

    @classmethod
    def initialize(cls, server=None):
        """Initializes NetworkTables and begins operations
        
        :param server: If specified, NetworkTables will be set to client
                       mode and attempt to connect to the specified server.
                       This is equivalent to executing::
                       
                           cls.setIPAddress(server)
                           cls.setClientMode()
                           cls.initialize()
        :type server: str
        
        .. versionadded:: 2017.0.0
           The *server* parameter
        """
        
        with cls._staticMutex:
            cls._checkInit()
            
            # Circular import issue
            try:
                from .version import __version__
            except ImportError:
                __version__ = '[unknown version]'
            
            identity = cls._identity
            if identity is None:
                identity = 'pynetworktables %s' % __version__
            
            cls._api.setNetworkIdentity(identity)
            
            if server is not None:
                cls._mode = 'client'
                cls.ipAddress = server
            
            if cls._mode == 'server':
                cls._api.startServer(cls._persistentFilename,
                                     cls._serverListenAddress,
                                     cls.port)
            elif cls._mode == 'client':
                cls._api.startClient([(cls.ipAddress, cls.port)])
            elif cls._mode == 'dashboard':
                raise ValueError("Dashboard mode isn't implemented yet")
            elif cls._mode == 'test-server':
                pass
            elif cls._mode == 'test-client':
                cls._api.dispatcher.m_server = False
                cls._api.storage.m_server = False 
            else:
                raise ValueError("Invalid NetworkTables mode '%s'" % cls._mode)

            
            logger.info("NetworkTables %s initialized in %s mode",
                        __version__, cls._mode)

            cls._running = True
    
    @classmethod
    def shutdown(cls):
        """Stops all NetworkTables activities and unregisters all tables
        and callbacks. You can call :meth:`.initialize` again after
        calling this.
        
        .. versionadded:: 2017.0.0
        """
        
        with cls._staticMutex:
            
            try:
                if not cls._running:
                    return
                
                if cls._mode in ['client', 'dashboard']:
                    cls._api.stopClient()
                elif cls._mode == 'server':
                    cls._api.stopServer()
            finally:
                cls._running = False
                cls._persistentFilename = None
                cls._mode = 'server'
                cls._tables = {}
                cls.port = cls.DEFAULT_PORT
                cls.ipAddress = None
                cls._identity = None
                cls._autolistener = None
                cls._api = NtCoreApi()
    
    @classmethod
    def setClientMode(cls):
        """Set that network tables should be a client
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with cls._staticMutex:
            cls._checkInit()
            cls._mode = 'client'
            
    @classmethod
    def setServerMode(cls):
        """set that network tables should be a server (this is the default)
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with cls._staticMutex:
            cls._checkInit()
            cls._mode = 'server'
    
    @classmethod
    def setTeam(cls, team):
        """set the team the robot is configured for (this will set the ip
        address that network tables will connect to in client mode)
        
        :param team: the team number
        :type team: str
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        cls.setIPAddress('roboRIO-%d-FRC.local' % team)

    @classmethod
    def setIPAddress(cls, address):
        """:param address: the adress that network tables will connect to in
            client mode
        :type address: str
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with cls._staticMutex:
            cls._checkInit()
            cls.ipAddress = address
    
    @classmethod
    def setPort(cls, port):
        """Sets the port number that network tables will connect to in
        client mode or listen to in server mode.
        
        :param port: the port number
        :type port: int
        
        .. versionadded:: 2017.0.0
        """
        with cls._staticMutex:
            cls._checkInit()
            cls.port = port
    
    @classmethod
    def setPersistentFilename(cls, filename):
        """Sets the persistent filename. Not used on the client.
         
        :param filename: the filename that the network tables server uses for
                         automatic loading and saving of persistent values
        :type filename: str
                         
        .. versionadded:: 2017.0.0
        """
        
        with cls._staticMutex:
            cls._checkInit()
            cls._persistentFilename = filename
        
    
    @classmethod
    def setNetworkIdentity(cls, name):
        """Sets the network identity. This is provided in the connection info
        on the remote end.
        
        :param name: A string to communicate to other NetworkTables instances
        :type name: str
        
        .. versionadded:: 2017.0.0
        """
        with cls._staticMutex:
            cls._checkInit()
            cls._identity = name
        
    @classmethod
    def globalDeleteAll(cls):
        """Deletes ALL keys in ALL subtables.
        
        .. warning:: Use with caution!
        
        .. versionadded:: 2017.0.0
        """
        cls._api.globalDeleteAll()
    
    @classmethod
    def flush(cls):
        """Flushes all updated values immediately to the network.
     
        .. note:: This is rate-limited to protect the network from flooding.
                  This is primarily useful for synchronizing network updates
                  with user code.
        
        .. versionadded:: 2017.0.0
        """
        cls._api.flush()
    
    @classmethod
    def setUpdateRate(cls, interval):
        """Sets the period of time between writes to the network. 
        
        WPILib's networktables and SmartDashboard default to 100ms, we have
        set it to 50ms instead for quicker response time. You should not set
        this value too low, as it could potentially increase the volume of
        data sent over the network.
        
        :param interval: Write flush period in seconds (default is 0.050,
                         or 50ms)
        :type interval: float
        
        .. warning:: If you don't know what this setting affects, don't mess
                     with it!
                        
        .. versionadded:: 2017.0.0
        """
        cls._api.setUpdateRate(interval)

    # Deprecated alias
    setWriteFlushPeriod = setUpdateRate
    
    @classmethod
    def savePersistent(cls, filename):
        """Saves persistent keys to a file. The server does this automatically.
        
        :param filename: Name of file to save keys to
        :type filename: str
        
        :returns: None if success, or a string describing the error on failure
        
        .. versionadded:: 2017.0.0
        """
        return cls._api.savePersistent(filename)
        
    @classmethod
    def loadPersistent(cls, filename):
        """Loads persistent keys from a file. WPILib will do this automatically
        on a robot server.
        
        :param filename: Name of file to load keys from
        :type filename: str
        
        :returns: None if success, or a string describing the error on failure
        
        .. versionadded:: 2017.0.0
        """
        return cls._api.loadPersistent(filename)
    
    
    @classmethod
    def setDashboardMode(cls):
        """This will allow the driver station to connect to your code and
        receive the IP address of the robot from it. You must not call
        :meth:`setClientMode`, :meth:`setTeam`, or :meth:`setIPAddress`
        
        .. warning:: Only use this if your pynetworktables client is running
                     on the same host as the driver station, or nothing will
                     happen! 
                     
                     This mode will only connect to the robot if the FRC
                     Driver Station is able to connect to the robot and the
                     LabVIEW dashboard has been disabled.
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with cls._staticMutex:
            cls._checkInit()
            cls._mode = 'dashboard'
            
    @classmethod
    def setTestMode(cls, server=True):
        """Setup network tables to run in unit test mode, and enables verbose
        logging.
        
        .. warning:: This must be called before :meth:`initalize` or :meth:`getTable`
        """
        with cls._staticMutex:
            cls._checkInit()
            if server:
                cls._mode = 'test-server'
            else:
                cls._mode = 'test-client'
            cls.enableVerboseLogging()
            
    @classmethod
    def enableVerboseLogging(cls):
        """Enable verbose logging that can be useful when trying to diagnose
        NetworkTables issues.
        
        .. warning:: Don't enable this in normal use, as it can potentially 
                     cause performance issues due to the volume of logging.
                  
        .. versionadded:: 2017.0.0
        """
        with cls._staticMutex:
            cls._checkInit()
            cls._api.setVerboseLogging(True)
    
    @classmethod
    def getTable(cls, key):
        """Gets the table with the specified key. If the table does not exist,
        a new table will be created.

        This will automatically initialize network tables if it has not been
        already initialized.

        :param key: the key name
        :type key: str
        
        :returns: the network table requested
        :rtype: :class:`.NetworkTable`
        """
        
        # Must start with separator
        if key.startswith(cls.PATH_SEPARATOR):
            path = key
        else:
            path = cls.PATH_SEPARATOR + key
        
        # Must not end with separator
        if path.endswith(cls.PATH_SEPARATOR):
            path = path[:-1]
        
        with cls._staticMutex:
            if not cls._running:
                cls.initialize()
            
            table = cls._tables.get(path)
            if table is not None:
                return table
            
            # TODO: circular import problem, fix in 2018
            from .networktable import NetworkTable
                
            table = NetworkTable(path, cls._api)
            
            # global table is special
            if path == '':
                table._path = ''
            
            cls._tables[path] = table
            return table

    @classmethod
    def getGlobalTable(cls):
        """Returns an object that allows you to write values to raw network table
        keys (which are paths with / separators).

        This will automatically initialize network tables if it has not been
        already.

        .. note:: This is now an alias for ``NetworkTables.getTable('/')``
        
        .. versionadded:: 2015.2.0
        .. versionchanged:: 2017.0.0
           Returns a NetworkTable instance

        :rtype: :class:`.NetworkTable`
        """
        return cls.getTable('/')

    @classmethod
    def addGlobalListener(cls, listener, immediateNotify=True,
                          localNotify=True):
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
        :param immediateNotify: bool

        .. versionadded:: 2015.2.0
        
        .. versionchanged:: 2017.0.0
           `paramIsNew` parameter added

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
        '''
        gtable = cls.getTable('/')
        gtable.addTableListener(listener, immediateNotify=immediateNotify,
                                key=0xdeadbeef, localNotify=localNotify)
        
    @classmethod
    def addGlobalListenerEx(cls, listener, flags, paramIsNew=True):
        '''Adds a listener that will be notified when any key in any
        NetworkTable is changed. The keys that are received using this
        listener will be full NetworkTable keys. Most users will not
        want to use this listener type.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        This will automatically initialize network tables if it has not been
        already.
        
        :param listener: A callable that has this signature: `callable(key, value, isNew)`
        :param flags: Bitmask of flags that indicate the types of notifications you wish to receive
        :type flags: :class:`.NotifyFlags`
        :param paramIsNew: If True, the listener third parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags
        :type paramIsNew: bool
        '''
        gtable = cls.getTable('/')
        gtable.addTableListenerEx(listener, flags, key=0xdeadbeef,
                                  paramIsNew=paramIsNew)

    @classmethod
    def removeGlobalListener(cls, listener):
        '''Removes a global listener

        .. versionadded:: 2015.2.0
        '''
        cls.getTable('/').removeTableListener(listener)
            
    @classmethod
    def getGlobalAutoUpdateValue(cls, key, defaultValue, writeDefault):
        '''Global version of getAutoUpdateValue. This function will not initialize
        NetworkTables.
        
        :param key: the full NT path of the value (must start with /)
        :type key: str
        :param defaultValue: The default value to return if the key doesn't exist
        :type defaultValue: any
        :param writeDefault: If True, force the value to the specified default
        :type writeDefault: bool
        
        .. versionadded:: 2015.3.0
        
        .. seealso:: :func:`.ntproperty` is a read-write alternative to this
        '''
        assert key.startswith('/')
        
        # Use raw NT api to avoid having to initialize networktables
        value = None
        valuefn = None # optimization for ntproperty
        
        if not writeDefault:
            value = cls._api.getEntryValue(key)
            
        if value is None:
            valuefn = Value.getFactory(defaultValue)
            cls._api.setEntryValue(key, valuefn(defaultValue))
            value = defaultValue
        elif not writeDefault:
            value = value.value
            valuefn = Value.getFactory(value)
        else:
            valuefn = Value.getFactory(value)
        
        return cls._api.createAutoValue(key,
                                        AutoUpdateValue(key, value, valuefn))

    @classmethod
    def getRemoteAddress(cls):
        '''
            Only returns a valid address if connected to the server. If
            this is a server, returns None
            
            :returns: IP address of server or None
            :rtype: str
            
            .. versionadded:: 2015.3.2
        '''
        return cls._api.getRemoteAddress()

    @classmethod
    def isConnected(cls):
        """
            :returns: True if connected to at least one other NetworkTables
                      instance
            :rtype: bool
        """
        return cls._api.getIsConnected()

    @classmethod
    def isServer(cls):
        """:returns: True if configured in server mode"""
        return 'server' in cls._mode
    
    @classmethod
    def addConnectionListener(cls, listener, immediateNotify=False):
        '''Adds a listener that will be notified when a new connection to a 
        NetworkTables client/server is established.
        
        The listener is called from a NetworkTables owned thread and should
        return as quickly as possible.
        
        :param listener: A function that will be called with two parameters
        :type listener: fn(bool, ConnectionInfo)
        
        :param immediateNotify: If True, the listener will be called immediately
                                with any active connection information
        :type immediateNotify: bool
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended.
                     
        .. versionchanged:: 2017.0.0
           The listener is now a function
        '''
        assert callable(listener)
        cls._api.addConnectionListener(listener, immediateNotify)

    @classmethod
    def removeConnectionListener(cls, listener):
        '''Removes a connection listener
        
        :param listener: The function registered for connection notifications
        '''
        cls._api.removeConnectionListener(listener)


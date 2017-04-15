
__all__ = ["NetworkTable"]

# TODO: in 2018, remove this circular import
from .networktables import NetworkTables as _NT

from ntcore.constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
    
    NT_PERSISTENT,
    
    NT_NOTIFY_IMMEDIATE,
    NT_NOTIFY_LOCAL,
    NT_NOTIFY_NEW,
    NT_NOTIFY_DELETE,
    NT_NOTIFY_UPDATE,
    NT_NOTIFY_FLAGS
)

_is_new = NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW

from ntcore.value import Value

import logging
logger = logging.getLogger('nt')


class _defaultValueSentry:
    pass

class NetworkTable:
    '''
        This is a NetworkTable instance, it allows you to interact with
        NetworkTables in a table-based manner. You should not directly
        create a NetworkTable object, but instead use
        :meth:`.NetworkTables.getTable` to retrieve a NetworkTable instance.
        
        For example, to interact with the SmartDashboard::

            from networktables import NetworkTables
            sd = NetworkTables.getTable('SmartDashboard')
    
            sd.putNumber('someNumber', 1234)
            ...
            
        .. seealso::
           - The examples in the documentation.
           - :class:`.NetworkTables`
    '''
    
    PATH_SEPARATOR = '/'
    
    # These static aliases are deprecated and will be removed in 2018!
    
    initialize = _NT.initialize
    shutdown = _NT.shutdown
    setClientMode = _NT.setClientMode
    setServerMode = _NT.setServerMode
    setTeam = _NT.setTeam
    setIPAddress = _NT.setIPAddress
    setPort = _NT.setPort
    setPersistentFilename = _NT.setPersistentFilename
    setNetworkIdentity = _NT.setNetworkIdentity
    globalDeleteAll = _NT.globalDeleteAll
    flush = _NT.flush
    setUpdateRate = _NT.setUpdateRate
    setWriteFlushPeriod = _NT.setWriteFlushPeriod
    savePersistent = _NT.savePersistent
    loadPersistent = _NT.loadPersistent
    setDashboardMode = _NT.setDashboardMode
    setTestMode = _NT.setTestMode
    getTable = _NT.getTable
    getGlobalTable = _NT.getGlobalTable
    addGlobalListener = _NT.addGlobalListener
    removeGlobalListener = _NT.removeGlobalListener
    getGlobalAutoUpdateValue = _NT.getGlobalAutoUpdateValue
    
    addConnectionListener = _NT.addConnectionListener
    removeConnectionListener = _NT.removeConnectionListener
    
    getRemoteAddress = _NT.getRemoteAddress
    isConnected = _NT.isConnected
    isServer = _NT.isServer
    
    
    def __init__(self, path, api):
        
        #: Path of table without trailing slash
        self.path = path
        self._path = path + self.PATH_SEPARATOR
        self._pathsz = len(self._path)
            
        self._api = api
        
        self._listeners = {}

    def __str__(self):
        return "NetworkTable: "+self._path
    
    def __repr__(self):
        return "<NetworkTable path=%s>" % self._path

    def addTableListener(self, listener, immediateNotify=False, key=None,
                               localNotify=False):
        '''Adds a listener that will be notified when any key in this
        NetworkTable is changed, or when a specified key changes.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: A callable with signature `callable(source, key, value, isNew)`
        :param immediateNotify: If True, the listener will be called immediately with the current values of the table
        :type immediateNotify: bool
        :param key: If specified, the listener will only be called when this key is changed
        :type key: str
        :param localNotify: True if you wish to be notified of changes made locally (default is False)
        :type localNotify: bool
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended
                     
        .. versionchanged:: 2017.0.0
           Added localNotify parameter (defaults to False, which is different from NT2)
        
        '''
        flags = NT_NOTIFY_NEW | NT_NOTIFY_UPDATE
        if immediateNotify:
            flags |= NT_NOTIFY_IMMEDIATE
        if localNotify:
            flags |= NT_NOTIFY_LOCAL
            
        self.addTableListenerEx(listener, flags, key=key)
        
    def addTableListenerEx(self, listener, flags, key=None,
                           paramIsNew=True):
        '''Adds a listener that will be notified when any key in this
        NetworkTable is changed, or when a specified key changes.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: A callable with signature `callable(source, key, value, param)`
        :param flags: Bitmask of flags that indicate the types of notifications you wish to receive
        :type flags: :class:`.NotifyFlags`
        :param key: If specified, the listener will only be called when this key is changed
        :type key: str
        :param paramIsNew: If True, the listener fourth parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags
        :type paramIsNew: bool
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended
        
        .. versionadded:: 2017.0.0
        '''
        
        if key is None:
            _pathsz = self._pathsz
            if paramIsNew:
                def callback(key_, value_, flags_):
                    key_ = key_[_pathsz:]
                    if '/' not in key_:
                        listener(self, key_, value_, (flags_ & _is_new) != 0)
            else:
                def callback(key_, value_, flags_):
                    key_ = key_[_pathsz:]
                    if '/' not in key_:
                        listener(self, key_, value_, flags_)
    
        # Hack: Internal flag used by addGlobalListener*
        elif key == 0xdeadbeef:
            if paramIsNew:
                def callback(key_, value_, flags_):
                    listener(key_, value_, (flags_ & _is_new) != 0)
            else:
                callback = listener
                
        else:
            path = self._path + key
            if paramIsNew:
                def callback(key_, value_, flags_):
                    if path == key_:
                        listener(self, key, value_, (flags_ & _is_new) != 0)
            else:
                def callback(key_, value_, flags_):
                    if path == key_:
                        listener(self, key, value_, flags_)
        
        uid = self._api.addEntryListener(self._path, callback, flags)
        self._listeners.setdefault(listener, []).append(uid)

    def addSubTableListener(self, listener, localNotify=False):
        '''Adds a listener that will be notified when any key in a subtable of
        this NetworkTable is changed.
        
        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.
        
        :param listener: Callable to call when previously unseen table appears.
                         Function signature is `callable(source, key, subtable, True)`
        :param localNotify: True if you wish to be notified when local changes
                            result in a new table
        :type localNotify: bool
        
        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur
                     
        .. versionchanged:: 2017.0.0
           Added localNotify parameter
        '''
        notified_tables = {}
        
        def _callback(key, value, _):
            key = key[self._pathsz:]
            if '/' in key:
                skey = key[:key.index('/')]
                
                o = object()
                if notified_tables.setdefault(skey, o) is o:
                    try:
                        listener(self, skey, self.getSubTable(skey), True)
                    except Exception:
                        logger.warning("Unhandled exception in %s", listener, exc_info=True)
        
        flags = NT_NOTIFY_NEW | NT_NOTIFY_IMMEDIATE
        if localNotify:
            flags |= NT_NOTIFY_LOCAL
        
        uid = self._api.addEntryListener(self._path, _callback, flags)
        self._listeners.setdefault(listener, []).append(uid)
        

    def removeTableListener(self, listener):
        '''Removes a table listener
        
        :param listener: callable that was passed to :meth:`.addTableListener`
                         or :meth:`.addSubTableListener`
        '''
        uids = self._listeners.pop(listener, [])
        for uid in uids:
            self._api.removeEntryListener(uid)

    def getSubTable(self, key):
        """Returns the table at the specified key. If there is no table at the
        specified key, it will create a new table

        :param key: the key name
        :type key: str
        
        :returns: the networktable to be returned
        :rtype: :class:`.NetworkTable`
        """
        path = self._path + key
        return _NT.getTable(path)
        

    def containsKey(self, key):
        """Determines whether the given key is in this table.
        
        :param key: the key to search for
        :type key: str
        
        :returns: True if the table as a value assigned to the given key
        :rtype: bool
        """
        path = self._path + key
        return self._api.getEntryValue(path) is not None

    def __contains__(self, key):
        return self.containsKey(key)

    def containsSubTable(self, key):
        """Determines whether there exists a non-empty subtable for this key
        in this table.
        
        :param key: the key to search for (must not end with path separator)
        :type key: str
        
        :returns: True if there is a subtable with the key which contains at least
                  one key/subtable of its own
        :rtype: bool
        """
        path = self._path + key + self.PATH_SEPARATOR
        return len(self._api.getEntryInfo(path, 0)) > 0
    
    def getKeys(self, types=0):
        """
        :param types: bitmask of types; 0 is treated as a "don't care".
        :type types: :class:`.EntryTypes`
        
        :returns: keys currently in the table
        :rtype: list
        
        .. versionadded:: 2017.0.0
        """
        keys = []
        for entry in self._api.getEntryInfo(self._path, types):
            relative_key = entry.name[len(self._path):]
            if self.PATH_SEPARATOR in relative_key:
                continue
            
            keys.append(relative_key)
        
        return keys
        
    def getSubTables(self):
        """:returns: subtables currently in the table
        :rtype: list
        
        .. versionadded:: 2017.0.0
        """
        keys = set()
        for entry in self._api.getEntryInfo(self._path, 0):
            relative_key = entry.name[len(self._path):]
            subst = relative_key.split(self.PATH_SEPARATOR)
            if len(subst) == 1:
                continue
            
            keys.add(subst[0])
        
        return list(keys)
    
    def setPersistent(self, key):
        """Makes a key's value persistent through program restarts.
        
        :param key: the key to make persistent
        :type key: str
        
        .. versionadded:: 2017.0.0
        """
        self.setFlags(key, NT_PERSISTENT)
        
    def clearPersistent(self, key):
        """Stop making a key's value persistent through program restarts.
        
        :param key: the key name
        :type key: str
        
        .. versionadded:: 2017.0.0
        """
        self.clearFlags(key, NT_PERSISTENT)
    
    def isPersistent(self, key):
        """Returns whether the value is persistent through program restarts.
        
        :param key: the key name
        :type key: str
        
        .. versionadded:: 2017.0.0
        """
        return self.getFlags(key) & NT_PERSISTENT != 0
        
    def delete(self, key):
        """Deletes the specified key in this table.
        
        :param key: the key name
        :type key: str
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.deleteEntry(path)
    
    def setFlags(self, key, flags):
        """Sets entry flags on the specified key in this table.
        
        :param key: the key name
        :type key: str
        :param flags: the flags to set (bitmask)
        :type flags: :class:`.EntryFlags`
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.setEntryFlags(path, self._api.getEntryFlags(path) | flags)
        
    def clearFlags(self, key, flags):
        """Clears entry flags on the specified key in this table.
        
        :param key: the key name
        :type key: str
        :param flags: the flags to clear (bitmask)
        :type flags: :class:`.EntryFlags`
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.setEntryFlags(path, self._api.getEntryFlags(path) & ~flags)
        
    def getFlags(self, key):
        """Returns the entry flags for the specified key.
        
        :param key: the key name
        :type key: str
        :returns: the flags, or 0 if the key is not defined
        :rtype: :class:`.EntryFlags`
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.getEntryFlags(path)

    def putNumber(self, key, value):
        """Put a number in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: int, float
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeDouble(value))

    def setDefaultNumber(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: int, float
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeDouble(defaultValue))

    def getNumber(self, key, defaultValue=_defaultValueSentry):
        """Gets the number associated with the given name.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        :type defaultValue: int, float
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: int, float
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_DOUBLE:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value

    def putString(self, key, value):
        """Put a string in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: str
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeString(value))

    def setDefaultString(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: str
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeString(defaultValue))

    def getString(self, key, defaultValue=_defaultValueSentry):
        """Gets the string associated with the given name. If the key does not
        exist or is of different type, it will return the default value.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        :type defaultValue: str
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: str
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_STRING:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value

    def putBoolean(self, key, value):
        """Put a boolean in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: bool
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeBoolean(value))

    def setDefaultBoolean(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: bool
        
        :returns: False if the table key exists with a different type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeBoolean(defaultValue))

    def getBoolean(self, key, defaultValue=_defaultValueSentry):
        """Gets the boolean associated with the given name. If the key does not
        exist or is of different type, it will return the default value.

        :param key: the key name
        :type key: str
        :param defaultValue: the default value if the key is None.  If not
                             specified, raises KeyError if the key is None.
        :type defaultValue: bool
        
        :returns: the key
        :rtype: bool
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_BOOLEAN:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value

    def putBooleanArray(self, key, value):
        """Put a boolean array in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: iterable(bool)
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeBooleanArray(value))
    
    def setDefaultBooleanArray(self, key, defaultValue=_defaultValueSentry):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: iterable(bool)
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeBooleanArray(defaultValue))
        
    def getBooleanArray(self, key, defaultValue=_defaultValueSentry):
        """Returns the boolean array the key maps to. If the key does not exist or is
        of different type, it will return the default value.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: tuple(bool)
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_BOOLEAN_ARRAY:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value
    
    def putNumberArray(self, key, value):
        """Put a number array in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: iterable(float)
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeDoubleArray(value))
    
    def setDefaultNumberArray(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: iterable(int or float)
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeDoubleArray(defaultValue))
    
    def getNumberArray(self, key, defaultValue=_defaultValueSentry):
        """Returns the number array the key maps to. If the key does not exist or is
        of different type, it will return the default value.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: tuple(int or float)
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_DOUBLE_ARRAY:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value
        
    def putStringArray(self, key, value):
        """Put a string array in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: iterable(str)
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeStringArray(value))
    
    def setDefaultStringArray(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: iterable(str)
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeStringArray(defaultValue))
    
    def getStringArray(self, key, defaultValue=_defaultValueSentry):
        """Returns the string array the key maps to. If the key does not exist or is
        of different type, it will return the default value.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: tuple(str)
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_STRING_ARRAY:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value
        
    def putRaw(self, key, value):
        """Put a raw value (byte array) in the table
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: bytes
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeRaw(value))
        
    def setDefaultRaw(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: bytes
        
        :returns: False if the table key exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeRaw(defaultValue))
    
    def getRaw(self, key, defaultValue=_defaultValueSentry):
        """Returns the raw value (byte array) the key maps to. If the key does not
        exist or is of different type, it will return the default value.
        
        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found
        :type defaultValue: bytes
        
        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        :rtype: bytes
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_RAW:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value
    
    def putValue(self, key, value):
        """Put a value in the table, trying to autodetect the NT type of
        the value. Refer to this table to determine the type mapping:
        
        ======= ============================ =================================
        PyType  NT Type                       Notes
        ======= ============================ =================================
        bool    :attr:`.EntryTypes.BOOLEAN`
        int     :attr:`.EntryTypes.DOUBLE`
        float   :attr:`.EntryTypes.DOUBLE`
        str     :attr:`.EntryTypes.STRING`
        bytes   :attr:`.EntryTypes.RAW`      Doesn't work in Python 2.7
        list    Error                        Use `putXXXArray` methods instead
        tuple   Error                        Use `putXXXArray` methods instead
        ======= ============================ =================================
        
        :param key: the key to be assigned to
        :type key: str
        :param value: the value that will be assigned
        :type value: bool, int, float, str, bytes
        
        :returns: False if the table key already exists with a different type
        :rtype: bool
        
        .. versionadded:: 2017.0.0
        """
        value = Value.getFactory(value)(value)
        path = self._path + key
        return self._api.setEntryValue(path, value)

    def setDefaultValue(self, key, defaultValue):
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.
        
        :param key: the key to be assigned to
        :type key: str
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: bool, int, float, str, bytes
        
        :returns: False if the table key exists with a different type
        
        .. versionadded:: 2017.0.0
        
        .. seealso:: :meth:`.putValue`
        """
        defaultValue = Value.getFactory(defaultValue)(defaultValue)
        path = self._path + key
        return self._api.setDefaultEntryValue(path, defaultValue)

    def getValue(self, key, defaultValue=_defaultValueSentry):
        """Gets the value associated with a key. This supports all
        NetworkTables types (unlike :meth:`putValue`).
        
        :param key: the key of the value to look up
        :type key: str
        :param defaultValue: The default value to return if the key doesn't exist
        :type defaultValue: any
        
        :returns: the value associated with the given key
        :rtype: bool, int, float, str, bytes, tuple
        
        :raises KeyError: If the value doesn't exist and no default is provided, or
                          if it is the wrong type
        
        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value:
            if defaultValue != _defaultValueSentry:
                return defaultValue
            raise KeyError(path)

        return value.value
    
    def getAutoUpdateValue(self, key, defaultValue, writeDefault=True):
        '''Returns an object that will be automatically updated when the
        value is updated by networktables.
        
        :param key: the key name
        :type  key: str
        :param defaultValue: Default value to use if not in the table
        :type  defaultValue: any
        :param writeDefault: If True, put the default value to the table,
                             overwriting existing values
        :type  writeDefault: bool
        
        :rtype: :class:`.AutoUpdateValue`
        
        .. note:: If you modify the returned value, the value will NOT
                  be written back to NetworkTables. See :func:`.ntproperty`
                  if you're looking for that sort of thing.
        
        .. seealso:: :func:`.ntproperty` is a better alternative to use
        
        .. versionadded:: 2015.1.3
        '''
        return _NT.getGlobalAutoUpdateValue(self._path + key, defaultValue, writeDefault)

    

__all__ = ["NetworkTable"]

from typing import Callable, List, Optional, Sequence

from ._impl.constants import (
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
    NT_NOTIFY_FLAGS,
)

from ._impl.value import Value

from .entry import NetworkTableEntry

import logging

logger = logging.getLogger("nt")
_is_new = NT_NOTIFY_IMMEDIATE | NT_NOTIFY_NEW


class NetworkTable:
    """
    This is a NetworkTable object, it allows you to interact with
    NetworkTables in a table-based manner. You should not directly
    create a NetworkTable object, but instead use
    :meth:`.NetworkTables.getTable` to retrieve a NetworkTable instance.

    For example, to interact with the SmartDashboard::

        from networktables import NetworkTables
        sd = NetworkTables.getTable('SmartDashboard')

        someNumberEntry = sd.getEntry('someNumber')
        someNumberEntry.putNumber(1234)
        ...

    .. seealso::
       - The examples in the documentation.
       - :class:`.NetworkTablesInstance`
    """

    PATH_SEPARATOR = "/"

    def __init__(self, path, api, inst):

        #: Path of table without trailing slash
        self.path = path
        self._path = path + self.PATH_SEPARATOR
        self._pathsz = len(self._path)

        self._api = api
        self._inst = inst

        self._listeners = {}

    def __str__(self):
        return "NetworkTable: %s" % self._path

    def __repr__(self):
        return "<NetworkTable path=%s>" % self._path

    def getEntry(self, key: str) -> NetworkTableEntry:
        """Gets the entry for a subkey. This is the preferred API to use
        to access NetworkTable keys.

        :rtype: :class:`.NetworkTableEntry`

        .. versionadded:: 2018.0.0
        """
        return self._inst.getEntry(self._path + key)

    def getPath(self) -> str:
        """Gets the full path of this table.  Does not include the trailing "/".

        :returns: The path (e.g "", "/foo").
        """
        return self._path

    def addEntryListener(
        self,
        listener: Callable,
        immediateNotify: bool = False,
        key: Optional[str] = None,
        localNotify: bool = False,
    ) -> None:
        """Adds a listener that will be notified when any key in this
        NetworkTable is changed, or when a specified key changes.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        :param listener: A callable with signature `callable(source, key, value, isNew)`
        :param immediateNotify: If True, the listener will be called immediately with the current values of the table
        :param key: If specified, the listener will only be called when this key is changed
        :param localNotify: True if you wish to be notified of changes made locally (default is False)

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended

        .. versionchanged:: 2017.0.0
           Added localNotify parameter (defaults to False, which is different from NT2)

        """
        flags = NT_NOTIFY_NEW | NT_NOTIFY_UPDATE
        if immediateNotify:
            flags |= NT_NOTIFY_IMMEDIATE
        if localNotify:
            flags |= NT_NOTIFY_LOCAL

        self.addEntryListenerEx(listener, flags, key=key)

    def addEntryListenerEx(
        self,
        listener: Callable,
        flags: int,
        key: Optional[str] = None,
        paramIsNew: bool = True,
    ) -> None:
        """Adds a listener that will be notified when any key in this
        NetworkTable is changed, or when a specified key changes.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        :param listener: A callable with signature `callable(source, key, value, param)`
        :param flags: Bitmask of flags that indicate the types of notifications you wish to receive
        :type flags: :class:`.NotifyFlags`
        :param key: If specified, the listener will only be called when this key is changed
        :param paramIsNew: If True, the listener fourth parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended

        .. versionadded:: 2017.0.0
        """

        # if key is None:
        # Any key in this table (but not subtables)

        if key is None:

            # Any key in this table (but not subtables)
            _pathsz = self._pathsz
            if paramIsNew:

                def callback(item):
                    key_, value_, flags_, _ = item
                    key_ = key_[_pathsz:]
                    if "/" not in key_:
                        listener(self, key_, value_.value, (flags_ & _is_new) != 0)

            else:

                def callback(item):
                    key_, value_, flags_, _ = item
                    key_ = key_[_pathsz:]
                    if "/" not in key_:
                        listener(self, key_, value_.value, flags_)

            uid = self._api.addEntryListener(self._path, callback, flags)

        # Hack: Internal flag used by addGlobalListener*
        elif key == 0xDEADBEEF:
            if paramIsNew:

                def callback(item):
                    key_, value_, flags_, _ = item
                    listener(key_, value_.value, (flags_ & _is_new) != 0)

            else:
                callback = listener

            uid = self._api.addEntryListener("/", callback, flags)
        else:
            entry_id = self._api.getEntryId(self._path + key)
            uid = self._api.addEntryListenerByIdEx(
                self, key, entry_id, listener, flags, paramIsNew
            )

        self._listeners.setdefault(listener, []).append(uid)

    # deprecated aliases
    addTableListener = addEntryListener
    addTableListenerEx = addEntryListenerEx

    def addSubTableListener(
        self, listener: Callable, localNotify: bool = False
    ) -> None:
        """Adds a listener that will be notified when any key in a subtable of
        this NetworkTable is changed.

        The listener is called from the NetworkTables I/O thread, and should
        return as quickly as possible.

        :param listener: Callable to call when previously unseen table appears.
                         Function signature is `callable(source, key, subtable, True)`
        :param localNotify: True if you wish to be notified when local changes
                            result in a new table

        .. warning:: You may call the NetworkTables API from within the
                     listener, but it is not recommended as we are not
                     currently sure if deadlocks will occur

        .. versionchanged:: 2017.0.0
           Added localNotify parameter
        """
        notified_tables = {}

        def _callback(item):
            key, value_, _1, _2 = item
            key = key[self._pathsz :]
            if "/" in key:
                skey = key[: key.index("/")]

                o = object()
                if notified_tables.setdefault(skey, o) is o:
                    try:
                        listener(self, skey, self.getSubTable(skey), True)
                    except Exception:
                        logger.warning(
                            "Unhandled exception in %s", listener, exc_info=True
                        )

        flags = NT_NOTIFY_NEW | NT_NOTIFY_IMMEDIATE
        if localNotify:
            flags |= NT_NOTIFY_LOCAL

        uid = self._api.addEntryListener(self._path, _callback, flags)
        self._listeners.setdefault(listener, []).append(uid)

    def removeEntryListener(self, listener: Callable) -> None:
        """Removes a table listener

        :param listener: callable that was passed to :meth:`.addTableListener`
                         or :meth:`.addSubTableListener`
        """
        uids = self._listeners.pop(listener, [])
        for uid in uids:
            self._api.removeEntryListener(uid)

    # Deprecated alias
    removeTableListener = removeEntryListener

    def getSubTable(self, key: str) -> "NetworkTable":
        """Returns the table at the specified key. If there is no table at the
        specified key, it will create a new table

        :param key: the key name

        :returns: the networktable to be returned
        """
        path = self._path + key
        return self._inst.getTable(path)

    def containsKey(self, key: str) -> bool:
        """Determines whether the given key is in this table.

        :param key: the key to search for

        :returns: True if the table as a value assigned to the given key
        """
        path = self._path + key
        return self._api.getEntryValue(path) is not None

    def __contains__(self, key: str) -> bool:
        return self.containsKey(key)

    def containsSubTable(self, key: str) -> bool:
        """Determines whether there exists a non-empty subtable for this key
        in this table.

        :param key: the key to search for (must not end with path separator)

        :returns: True if there is a subtable with the key which contains at least
                  one key/subtable of its own
        """
        path = self._path + key + self.PATH_SEPARATOR
        return len(self._api.getEntryInfo(path, 0)) > 0

    def getKeys(self, types: int = 0) -> List[str]:
        """
        :param types: bitmask of types; 0 is treated as a "don't care".
        :type types: :class:`.EntryTypes`

        :returns: keys currently in the table

        .. versionadded:: 2017.0.0
        """
        keys = []
        for entry in self._api.getEntryInfo(self._path, types):
            relative_key = entry.name[len(self._path) :]
            if self.PATH_SEPARATOR in relative_key:
                continue

            keys.append(relative_key)

        return keys

    def getSubTables(self) -> List[str]:
        """:returns: subtables currently in the table

        .. versionadded:: 2017.0.0
        """
        keys = set()
        for entry in self._api.getEntryInfo(self._path, 0):
            relative_key = entry.name[len(self._path) :]
            subst = relative_key.split(self.PATH_SEPARATOR)
            if len(subst) == 1:
                continue

            keys.add(subst[0])

        return list(keys)

    def setPersistent(self, key: str) -> None:
        """Makes a key's value persistent through program restarts.

        :param key: the key to make persistent

        .. versionadded:: 2017.0.0
        """
        self.setFlags(key, NT_PERSISTENT)

    def clearPersistent(self, key: str) -> None:
        """Stop making a key's value persistent through program restarts.

        :param key: the key name

        .. versionadded:: 2017.0.0
        """
        self.clearFlags(key, NT_PERSISTENT)

    def isPersistent(self, key: str) -> bool:
        """Returns whether the value is persistent through program restarts.

        :param key: the key name

        .. versionadded:: 2017.0.0
        """
        return self.getFlags(key) & NT_PERSISTENT != 0

    def delete(self, key: str) -> None:
        """Deletes the specified key in this table.

        :param key: the key name

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.deleteEntry(path)

    def setFlags(self, key: str, flags: int) -> None:
        """Sets entry flags on the specified key in this table.

        :param key: the key name
        :param flags: the flags to set (bitmask)
        :type flags: :class:`.EntryFlags`

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.setEntryFlags(path, self._api.getEntryFlags(path) | flags)

    def clearFlags(self, key: str, flags: int) -> None:
        """Clears entry flags on the specified key in this table.

        :param key: the key name
        :param flags: the flags to clear (bitmask)
        :type flags: :class:`.EntryFlags`

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        self._api.setEntryFlags(path, self._api.getEntryFlags(path) & ~flags)

    def getFlags(self, key: str):
        """Returns the entry flags for the specified key.

        :param key: the key name
        :returns: the flags, or 0 if the key is not defined
        :rtype: :class:`.EntryFlags`

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.getEntryFlags(path)

    def putNumber(self, key: str, value: float) -> bool:
        """Put a number in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeDouble(value))

    def setDefaultNumber(self, key: str, defaultValue: float) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: int, float

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeDouble(defaultValue))

    def getNumber(self, key: str, defaultValue: float) -> float:
        """Gets the number associated with the given name.

        :param key: the key to look up
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_DOUBLE:
            return defaultValue

        return value.value

    def putString(self, key: str, value: str) -> bool:
        """Put a string in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeString(value))

    def setDefaultString(self, key: str, defaultValue: str) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeString(defaultValue))

    def getString(self, key: str, defaultValue: str) -> str:
        """Gets the string associated with the given name. If the key does not
        exist or is of different type, it will return the default value.

        :param key: the key to look up
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_STRING:
            return defaultValue

        return value.value

    def putBoolean(self, key: str, value: bool) -> bool:
        """Put a boolean in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeBoolean(value))

    def setDefaultBoolean(self, key: str, defaultValue: bool) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeBoolean(defaultValue))

    def getBoolean(self, key: str, defaultValue: bool) -> bool:
        """Gets the boolean associated with the given name. If the key does not
        exist or is of different type, it will return the default value.

        :param key: the key name
        :param defaultValue: the default value if no value is found

        :returns: the key
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_BOOLEAN:
            return defaultValue

        return value.value

    def putBooleanArray(self, key: str, value: Sequence[bool]) -> bool:
        """Put a boolean array in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeBooleanArray(value))

    def setDefaultBooleanArray(self, key: str, defaultValue: Sequence[bool]) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(
            path, Value.makeBooleanArray(defaultValue)
        )

    def getBooleanArray(self, key: str, defaultValue) -> Sequence[bool]:
        """Returns the boolean array the key maps to. If the key does not exist or is
        of different type, it will return the default value.

        :param key: the key to look up
        :type key: str
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_BOOLEAN_ARRAY:
            return defaultValue

        return value.value

    def putNumberArray(self, key: str, value: Sequence[float]) -> bool:
        """Put a number array in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeDoubleArray(value))

    def setDefaultNumberArray(self, key: str, defaultValue: Sequence[float]) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeDoubleArray(defaultValue))

    def getNumberArray(self, key: str, defaultValue) -> Sequence[float]:
        """Returns the number array the key maps to. If the key does not exist or is
        of different type, it will return the default value.

        :param key: the key to look up
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_DOUBLE_ARRAY:
            return defaultValue

        return value.value

    def putStringArray(self, key: str, value: Sequence[str]) -> bool:
        """Put a string array in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeStringArray(value))

    def setDefaultStringArray(self, key: str, defaultValue: Sequence[str]) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeStringArray(defaultValue))

    def getStringArray(self, key: str, defaultValue) -> Sequence[str]:
        """Returns the string array the key maps to. If the key does not exist or is
        of different type, it will return the default value.

        :param key: the key to look up
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_STRING_ARRAY:
            return defaultValue

        return value.value

    def putRaw(self, key: str, value: bytes) -> bool:
        """Put a raw value (byte array) in the table

        :param key: the key to be assigned to
        :param value: the value that will be assigned

        :returns: False if the table key already exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setEntryValue(path, Value.makeRaw(value))

    def setDefaultRaw(self, key: str, defaultValue: bytes) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        return self._api.setDefaultEntryValue(path, Value.makeRaw(defaultValue))

    def getRaw(self, key: str, defaultValue: bytes) -> bytes:
        """Returns the raw value (byte array) the key maps to. If the key does not
        exist or is of different type, it will return the default value.

        :param key: the key to look up
        :param defaultValue: the value to be returned if no value is found

        :returns: the value associated with the given key or the given default value
                  if there is no value associated with the key

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value or value.type != NT_RAW:
            return defaultValue

        return value.value

    def putValue(self, key: str, value) -> bool:
        """Put a value in the table, trying to autodetect the NT type of
        the value. Refer to this table to determine the type mapping:

        ======= ============================ =================================
        PyType  NT Type                       Notes
        ======= ============================ =================================
        bool    :attr:`.EntryTypes.BOOLEAN`
        int     :attr:`.EntryTypes.DOUBLE`
        float   :attr:`.EntryTypes.DOUBLE`
        str     :attr:`.EntryTypes.STRING`
        bytes   :attr:`.EntryTypes.RAW`
        list    Error                        Use `putXXXArray` methods instead
        tuple   Error                        Use `putXXXArray` methods instead
        ======= ============================ =================================

        :param key: the key to be assigned to
        :param value: the value that will be assigned
        :type value: bool, int, float, str, bytes

        :returns: False if the table key already exists with a different type

        .. versionadded:: 2017.0.0
        """
        value = Value.getFactory(value)(value)
        path = self._path + key
        return self._api.setEntryValue(path, value)

    def setDefaultValue(self, key: str, defaultValue) -> bool:
        """If the key doesn't currently exist, then the specified value will
        be assigned to the key.

        :param key: the key to be assigned to
        :param defaultValue: the default value to set if key doesn't exist.
        :type defaultValue: bool, int, float, str, bytes

        :returns: False if the table key exists with a different type

        .. versionadded:: 2017.0.0

        .. seealso:: :meth:`.putValue`
        """
        defaultValue = Value.getFactory(defaultValue)(defaultValue)
        path = self._path + key
        return self._api.setDefaultEntryValue(path, defaultValue)

    def getValue(self, key: str, defaultValue):
        """Gets the value associated with a key. This supports all
        NetworkTables types (unlike :meth:`putValue`).

        :param key: the key of the value to look up
        :param defaultValue: The default value to return if the key doesn't exist
        :type defaultValue: any

        :returns: the value associated with the given key
        :rtype: bool, int, float, str, bytes, tuple

        .. versionadded:: 2017.0.0
        """
        path = self._path + key
        value = self._api.getEntryValue(path)
        if not value:
            return defaultValue

        return value.value

    def getAutoUpdateValue(
        self, key: str, defaultValue, writeDefault: bool = True
    ) -> NetworkTableEntry:
        """Returns an object that will be automatically updated when the
        value is updated by networktables.

        :param key: the key name
        :param defaultValue: Default value to use if not in the table
        :type  defaultValue: any
        :param writeDefault: If True, put the default value to the table,
                             overwriting existing values

        :rtype: :class:`.NetworkTableEntry`

        .. note:: If you modify the returned value, the value will NOT
                  be written back to NetworkTables (though now there are functions
                  you can use to write values). See :func:`.ntproperty` if
                  you're looking for that sort of thing.

        .. seealso:: :func:`.ntproperty` is a better alternative to use

        .. versionadded:: 2015.1.3

        .. versionchanged:: 2018.0.0
           This now returns the same as :meth:`.NetworkTable.getEntry`

        """
        return self._inst.getGlobalAutoUpdateValue(
            self._path + key, defaultValue, writeDefault
        )

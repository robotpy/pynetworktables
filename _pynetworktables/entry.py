from typing import Any, Callable, Sequence, TypeVar, Union

from ._impl.constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
    NT_PERSISTENT,
)

from ._impl.value import Value

__all__ = ["NetworkTableEntry"]

D = TypeVar("D")


class NetworkTableEntry:
    """
    Holds a value from NetworkTables, and changes it as new entries
    come in. Do not create this object directly, use
    :func:`.NetworkTablesInstance.getEntry` or :meth:`.NetworkTable.getEntry`
    to obtain an instance of this class.

    Using NetworkTableEntry objects to access/change NT values is more
    efficient than the getX/putX methods of :class:`.NetworkTable`.

    .. versionadded:: 2018.0.0
    """

    __slots__ = ["__api", "_local_id", "key", "_value"]

    def __init__(self, api, local_id, key):
        self.__api = api
        self._local_id = local_id

        self.key = key
        self._value = None

    def getHandle(self):
        """Gets the native handle for the entry"""
        return self._local_id

    def exists(self) -> bool:
        """Determines if the entry currently exists"""
        return self.__api.getEntryTypeById(self._local_id) != 0

    def getName(self) -> str:
        """Gets the name of the entry (the key)"""
        return self.key

    def getType(self):
        """Gets the type of the entry

        :rtype: :class:`.NetworkTablesInstance.EntryTypes`
        """
        return self.__api.getEntryTypeById(self._local_id)

    def getFlags(self) -> int:
        """Returns the flags.

        :returns: the flags (bitmask)
        """
        return self.__api.getEntryFlagsById(self._local_id)

    def getInfo(self) -> tuple:
        """Gets combined information about the entry.

        :returns: Entry information
        :rtype: tuple of (name, type, flags)
        """
        return self.__api.getEntryInfoById(self._local_id)

    @property
    def value(self):
        """Property to access the value of this entry, or None if the entry
        hasn't been initialized yet (use setXXX or forceXXX)
        """
        try:
            return self._value[1]
        except TypeError:
            return None

    # deprecated, from autoUpdateValue
    def get(self):
        try:
            return self._value[1]
        except TypeError:
            return None

    def getBoolean(self, defaultValue: D) -> Union[bool, D]:
        """Gets the entry's value as a boolean. If the entry does not exist or is of
        different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_BOOLEAN:
            return defaultValue
        return value[1]

    def getDouble(self, defaultValue: D) -> Union[float, D]:
        """Gets the entry's value as a double. If the entry does not exist or is of
        different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_DOUBLE:
            return defaultValue
        return value[1]

    getNumber = getDouble

    def getString(self, defaultValue: D) -> Union[str, D]:
        """Gets the entry's value as a string. If the entry does not exist or is of
        different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_STRING:
            return defaultValue
        return value[1]

    def getRaw(self, defaultValue: D) -> Union[bytes, D]:
        """Gets the entry's value as a raw value (byte array). If the entry does not
        exist or is of different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_RAW:
            return defaultValue
        return value[1]

    def getBooleanArray(self, defaultValue: D) -> Union[Sequence[bool], D]:
        """Gets the entry's value as a boolean array. If the entry does not
        exist or is of different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_BOOLEAN_ARRAY:
            return defaultValue
        return value[1]

    def getDoubleArray(self, defaultValue: D) -> Union[Sequence[float], D]:
        """Gets the entry's value as a double array. If the entry does not
        exist or is of different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        """
        value = self._value
        if not value or value[0] != NT_DOUBLE_ARRAY:
            return defaultValue
        return value[1]

    def getStringArray(self, defaultValue: D) -> Union[Sequence[str], D]:
        """Gets the entry's value as a string array. If the entry does not
        exist or is of different type, it will return the default value.

        :param defaultValue: the value to be returned if no value is found
        :returns: the entry's value or the given default value
        :rtype: list(float)
        """
        value = self._value
        if not value or value[0] != NT_STRING_ARRAY:
            return defaultValue
        return value[1]

    @classmethod
    def isValidDataType(cls, data):
        if isinstance(data, (bytes, bytearray)):
            return True
        if isinstance(data, (list, tuple)):
            if len(data) == 0:
                raise ValueError("If you use a list here, cannot be empty")
            data = data[0]

        return isinstance(data, (int, float, str, bool))

    def setDefaultValue(self, defaultValue) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type

        .. warning:: Do not set an empty list, it will fail
        """
        value = Value.getFactory(defaultValue)(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setDefaultBoolean(self, defaultValue: bool) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeBoolean(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setDefaultDouble(self, defaultValue: float) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeDouble(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    setDefaultNumber = setDefaultDouble

    def setDefaultString(self, defaultValue: str) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeString(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setDefaultRaw(self, defaultValue: bytes) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeRaw(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setDefaultBooleanArray(self, defaultValue: Sequence[bool]) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeBooleanArray(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setDefaultDoubleArray(self, defaultValue: Sequence[float]) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeDoubleArray(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    setDefaultNumberArray = setDefaultDoubleArray

    def setDefaultStringArray(self, defaultValue: Sequence[str]) -> bool:
        """Sets the entry's value if it does not exist.

        :param defaultValue: the default value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeStringArray(defaultValue)
        return self.__api.setDefaultEntryValueById(self._local_id, value)

    def setValue(self, value) -> bool:
        """Sets the entry's value

        :param value: the value that will be assigned
        :returns: False if the table key already exists with a different type

        .. warning:: Empty lists will fail
        """
        value = Value.getFactory(value)(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def setBoolean(self, value: bool) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeBoolean(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def setDouble(self, value: float) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeDouble(value)
        return self.__api.setEntryValueById(self._local_id, value)

    setNumber = setDouble

    def setString(self, value: str) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeString(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def setRaw(self, value: bytes) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeRaw(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def setBooleanArray(self, value: Sequence[bool]) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeBooleanArray(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def setDoubleArray(self, value: Sequence[float]) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeDoubleArray(value)
        return self.__api.setEntryValueById(self._local_id, value)

    setNumberArray = setDoubleArray

    def setStringArray(self, value: Sequence[str]) -> bool:
        """Sets the entry's value.

        :param value: the value to set
        :returns: False if the entry exists with a different type
        """
        value = Value.makeStringArray(value)
        return self.__api.setEntryValueById(self._local_id, value)

    def forceSetValue(self, value):
        """Sets the entry's value

        :param value: the value that will be assigned

        .. warning:: Empty lists will fail
        """
        value = Value.getFactory(value)(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def forceSetBoolean(self, value: bool):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeBoolean(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def forceSetDouble(self, value: float):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeDouble(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    forceSetNumber = forceSetDouble

    def forceSetString(self, value: str):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeString(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def forceSetRaw(self, value: bytes):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeRaw(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def forceSetBooleanArray(self, value: Sequence[bool]):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeBooleanArray(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def forceSetDoubleArray(self, value: Sequence[float]):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeDoubleArray(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    forceSetNumberArray = forceSetDoubleArray

    def forceSetStringArray(self, value: Sequence[str]):
        """Sets the entry's value.

        :param value: the value to set
        """
        value = Value.makeStringArray(value)
        return self.__api.setEntryTypeValueById(self._local_id, value)

    def setFlags(self, flags: int) -> None:
        """Sets flags.

        :param flags: the flags to set (bitmask)
        """
        flags = self.getFlags() | flags
        self.__api.setEntryFlagsById(self._local_id, flags)

    def clearFlags(self, flags: int) -> None:
        """Clears flags

        :param flags: the flags to clear (bitmask)
        """
        flags = self.getFlags() & ~flags
        self.__api.setEntryFlagsById(self._local_id, flags)

    def setPersistent(self) -> None:
        """Make value persistent through program restarts."""
        self.setFlags(NT_PERSISTENT)

    def clearPersistent(self) -> None:
        """Stop making value persistent through program restarts."""
        self.clearFlags(NT_PERSISTENT)

    def isPersistent(self) -> bool:
        """Returns whether the value is persistent through program restarts.

        :returns: True if the value is persistent.
        """
        return (self.getFlags() & NT_PERSISTENT) != 0

    def delete(self) -> bool:
        """Deletes the entry."""
        return self.__api.deleteEntryById(self._local_id)

    #
    # TODO: RPC entry stuff not implemented
    #

    def addListener(
        self,
        listener: Callable[["NetworkTableEntry", str, Any, int], None],
        flags: int,
        paramIsNew: bool = True,
    ):
        """Add a listener for changes to the entry

        :param listener: the listener to add
        :type listener: `callable(entry, key, value, param)`
        :param flags: bitmask specifying desired notifications
        :type flags: :class:`.NetworkTablesInstance.NotifyFlags`
        :param paramIsNew: If True, the listener fourth parameter is a boolean set to True
                           if the listener is being called because of a new value in the
                           table. Otherwise, the parameter is an integer of the raw
                           `NT_NOTIFY_*` flags

        :returns: listener handle
        """
        return self.__api.addEntryListenerByIdEx(
            self, self.key, self._local_id, listener, flags, paramIsNew
        )

    def removeListener(self, listener_id) -> None:
        """Remove a listener from receiving entry events

        :param listener: the callable that was passed to addListener
        """
        self.__api.removeEntryListener(listener_id)

    # Comparison operators et al

    def __lt__(self, other):
        raise TypeError(
            "< not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __le__(self, other):
        raise TypeError(
            "<= not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __eq__(self, other):
        raise TypeError(
            "== not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __ne__(self, other):
        raise TypeError(
            "!= not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __gt__(self, other):
        raise TypeError(
            "> not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __ge__(self, other):
        raise TypeError(
            ">= not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __bool__(self):
        raise TypeError(
            "< not allowed on NetworkTableEntry objects. Use the .value attribute instead"
        )

    def __repr__(self):
        return "<NetworkTableEntry: %s>" % (self._value.__repr__(),)

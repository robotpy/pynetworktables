import struct as _struct

from .connection import BadMessageError

class ComplexData:
    def __init__(self, type):
        self.type = type

    def getType(self):
        return self.type

class ArrayData(ComplexData, list):
    def __init__(self, type):
        ComplexData.__init__(self, type)
        list.__init__(self)

class NetworkTableEntryType:
    """A class defining the types supported by NetworkTables as well as
    support for serialization of those types to and from DataStreams
    """

    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        return "NetworkTable type: %s" % self.name

    def writeBytes(self, b, value):
        """Append a sequence of bytes to the array suitable for writing to a stream
        :param b: bytearray to append bytes to
        :param value: the value to send
        """
        raise NotImplementedError

    def readValue(self, rstream):
        """read a value from a data input stream
        :param rstream: the stream to read a value from
        :returns: the value read from the stream
        """
        raise NotImplementedError

class BasicEntryType(NetworkTableEntryType):
    def __init__(self, id, name, STRUCT):
        NetworkTableEntryType.__init__(self, id, name)
        self.STRUCT = _struct.Struct(STRUCT)

    def writeBytes(self, b, value):
        b.extend(self.STRUCT.pack(value))

    def readValue(self, rstream):
        return rstream.readStruct(self.STRUCT)[0]

class StringEntryType(NetworkTableEntryType):
    """a string type
    """
    LEN = _struct.Struct('>H')

    def __init__(self, id, name):
        NetworkTableEntryType.__init__(self, id, name)

    def writeBytes(self, b, value):
        s = value.encode('utf-8')
        b.extend(self.LEN.pack(len(s)))
        b.extend(s)

    def readValue(self, rstream):
        sLen = rstream.readStruct(self.LEN)[0]
        try:
            return rstream.read(sLen).decode('utf-8')
        except UnicodeDecodeError as e:
            raise BadMessageError(e)

class DefaultEntryTypes:
    BOOLEAN_RAW_ID = 0x00
    DOUBLE_RAW_ID = 0x01
    STRING_RAW_ID = 0x02

    BOOLEAN = BasicEntryType(BOOLEAN_RAW_ID, "Boolean", '?')
    DOUBLE = BasicEntryType(DOUBLE_RAW_ID, "Double", '>d')
    STRING = StringEntryType(STRING_RAW_ID, "String")

class ComplexEntryType(NetworkTableEntryType):
    def __init__(self, id, name):
        NetworkTableEntryType.__init__(self, id, name)

    def internalizeValue(self, key, externalRepresentation, currentInteralValue):
        raise NotImplementedError

    def exportValue(self, key, internalData, externalRepresentation):
        raise NotImplementedError

class ArrayEntryType(ComplexEntryType):
    
    LEN = _struct.Struct('>B')
    
    #TODO allow for array of complex type
    def __init__(self, id, elementType, externalArrayType):
        ComplexEntryType.__init__(self, id, "Array of [%s]" % elementType.name)
        if not issubclass(externalArrayType, ArrayData):
            raise TypeError("External Array Data Type must extend ArrayData")
        self.externalArrayType = externalArrayType
        self.elementType = elementType

    def writeBytes(self, b, value):
        if len(value) > 255:
            raise IOError("Cannot write %s as %s. Arrays have a max length of 255 values" % (value, self.name))
        b.extend(self.LEN.pack(len(value)))
        for v in value:
            self.elementType.writeBytes(b, v)

    def readValue(self, rstream):
        sLen = rstream.readStruct(self.LEN)[0]
        dataArray = [] #TODO cache object arrays
        for _ in range(sLen):
            dataArray.append(self.elementType.readValue(rstream))
        return dataArray

    def internalizeValue(self, key, externalRepresentation, currentInternalValue):
        if not isinstance(externalRepresentation, self.externalArrayType):
            raise TypeError("%s is not a %s" % (externalRepresentation, self.externalArrayType))

        if currentInternalValue is not None and \
           len(currentInternalValue) == len(externalRepresentation):
            internalArray = currentInternalValue
            del internalArray[:]
        else:
            internalArray = []
        internalArray.extend(externalRepresentation)
        return internalArray

    def exportValue(self, key, internalData, externalRepresentation):
        if not isinstance(externalRepresentation, self.externalArrayType):
            raise TypeError("%s is not a %s" % (externalRepresentation, self.externalArrayType))

        del externalRepresentation[:]
        externalRepresentation.extend(internalData)

class BooleanArray(ArrayData):
    '''
        A list of boolean values, can be used like a python list. Use
        ``putValue`` and ``retrieveValue`` to get/store this on a particular
        key in a :class:`.NetworkTable`.
    '''
    
    BOOLEAN_ARRAY_RAW_ID = 0x10
    
    @staticmethod
    def from_list(iterable):
        '''Convenience method to construct a BooleanArray from a list'''
        a = BooleanArray()
        a.extend(iterable)
        return a

    def __init__(self):
        ArrayData.__init__(self, BooleanArray.TYPE)

    def __contains__(self, key):
        return ArrayData.__contains__(self, bool(key))

    def __setitem__(self, key, value):
        ArrayData.__setitem__(self, key, bool(value))

    def append(self, obj):
        ArrayData.append(self, bool(obj))

    def extend(self, iterable):
        ArrayData.extend(self, (bool(x) for x in iterable))

    def insert(self, index, obj):
        ArrayData.insert(self, index, bool(obj))

    def remove(self, value):
        ArrayData.remove(self, bool(value))

BooleanArray.TYPE = ArrayEntryType(BooleanArray.BOOLEAN_ARRAY_RAW_ID,
                                   DefaultEntryTypes.BOOLEAN,
                                   BooleanArray)

class NumberArray(ArrayData):
    '''
        A list of number values, can be used like a python list. Use
        ``putValue`` and ``retrieveValue`` to get/store this on a particular
        key in a :class:`.NetworkTable`.
    '''
    
    NUMBER_ARRAY_RAW_ID = 0x11
    
    @staticmethod
    def from_list(iterable):
        '''Convenience method to construct a NumberArray from a list'''
        a = NumberArray()
        a.extend(iterable)
        return a

    def __init__(self):
        ArrayData.__init__(self, NumberArray.TYPE)

    def __contains__(self, key):
        return ArrayData.__contains__(self, float(key))

    def __setitem__(self, key, value):
        ArrayData.__setitem__(self, key, float(value))

    def append(self, obj):
        ArrayData.append(self, float(obj))

    def extend(self, iterable):
        ArrayData.extend(self, (float(x) for x in iterable))

    def insert(self, index, obj):
        ArrayData.insert(self, index, float(obj))

    def remove(self, value):
        ArrayData.remove(self, float(value))

NumberArray.TYPE = ArrayEntryType(NumberArray.NUMBER_ARRAY_RAW_ID,
                                  DefaultEntryTypes.DOUBLE,
                                  NumberArray)

class StringArray(ArrayData):
    '''
        A list of string values, can be used like a python list. Use
        ``putValue`` and ``retrieveValue`` to get/store this on a particular
        key in a :class:`.NetworkTable`.
    '''
    
    STRING_ARRAY_RAW_ID = 0x12
    
    @staticmethod
    def from_list(iterable):
        '''Convenience method to construct a StringArray from a list'''
        a = StringArray()
        a.extend(iterable)
        return a

    def __init__(self):
        ArrayData.__init__(self, StringArray.TYPE)

    def __contains__(self, key):
        return ArrayData.__contains__(self, str(key))

    def __setitem__(self, key, value):
        ArrayData.__setitem__(self, key, str(value))

    def append(self, obj):
        ArrayData.append(self, str(obj))

    def extend(self, iterable):
        ArrayData.extend(self, (str(x) for x in iterable))

    def insert(self, index, obj):
        ArrayData.insert(self, index, str(obj))

    def remove(self, value):
        ArrayData.remove(self, str(value))

StringArray.TYPE = ArrayEntryType(StringArray.STRING_ARRAY_RAW_ID,
                                  DefaultEntryTypes.STRING,
                                  StringArray)

class NetworkTableEntryTypeManager:
    def __init__(self):
        self.typeMap = {}
        self.registerType(DefaultEntryTypes.BOOLEAN)
        self.registerType(DefaultEntryTypes.DOUBLE)
        self.registerType(DefaultEntryTypes.STRING)
        self.registerType(BooleanArray.TYPE)
        self.registerType(NumberArray.TYPE)
        self.registerType(StringArray.TYPE)

    def getType(self, id):
        return self.typeMap.get(id)

    def registerType(self, type):
        self.typeMap[type.id] = type

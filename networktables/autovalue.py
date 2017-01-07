

class AutoUpdateValue:
    """Holds a value from NetworkTables, and changes it as new entries
    come in. Updates to this value are NOT passed on to NetworkTables.
    
    Do not create this object directly, as it only holds the value. 
    Use :meth:`.NetworkTables.getAutoUpdateValue` to obtain an instance
    of this.
    """
    
    __slots__ = ['key', '__value', '_valuefn']
    
    def __init__(self, key, default, valuefn):
        self.key = key
        self.__value = default
        self._valuefn = valuefn
        
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


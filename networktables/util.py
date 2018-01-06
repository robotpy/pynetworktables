
from .networktables import NetworkTables

from ntcore.value import Value

__all__ = [
    'ntproperty',
    'ChooserControl'
]


class _NtProperty:
    def __init__(self, key, defaultValue, writeDefault, persistent):
        self.key = key
        self.defaultValue = defaultValue
        self.writeDefault = writeDefault
        self.persistent = persistent
        # never overwrite persistent values with defaults
        if persistent:
            self.writeDefault = False
        
        self.reset()
    
    def reset(self):
        self.ntvalue = NetworkTables.getGlobalAutoUpdateValue(
            self.key, self.defaultValue, self.writeDefault)
        if self.persistent:
            self.ntvalue.setPersistent()
        
        # this is an optimization, but presumes the value type never changes
        self.mkv = Value.getFactoryByType(self.ntvalue._value[0])
    
    def get(self, _):
        return self.ntvalue.value
    
    def set(self, _, value):
        NetworkTables._api.setEntryValueById(self.ntvalue._local_id, self.mkv(value))


def ntproperty(key, defaultValue, writeDefault=True, doc=None, persistent=False):
    '''
        A property that you can add to your classes to access NetworkTables
        variables like a normal variable.
        
        :param key: A full NetworkTables key (eg ``/SmartDashboard/foo``)
        :type  key: str
        :param defaultValue: Default value to use if not in the table
        :type  defaultValue: any
        :param writeDefault: If True, put the default value to the table,
                             overwriting existing values
        :type  writeDefault: bool
        :param doc: If given, will be the docstring of the property.
        :type  doc: str
        :param persistent: If True, persist set values across restarts.
                           *writeDefault* is ignored if this is True.
        :type  persistent: bool
        
        Example usage::
        
            class Foo(object):
            
                something = ntproperty('/SmartDashboard/something', True)
                
                ...
                
                def do_thing(self):
                    if self.something:    # reads from value
                        ...
                        
                        self.something = False # writes value
        
        .. note:: Does not work with empty lists/tuples.
        
                  Getting the value of this property should be reasonably
                  fast, but setting the value will have just as much overhead
                  as :meth:`.NetworkTable.putValue`
                  
        .. warning:: When using python 2.x, the property must be assigned to
                     a new-style class or it won't work!
                     
                     Additionally, this function assumes that the value's type
                     never changes. If it does, you'll get really strange
                     errors... so don't do that.
                  
        .. versionadded:: 2015.3.0

        .. versionchanged:: 2017.0.6
            The *doc* parameter.

        .. versionchanged:: 2018.0.0
            The *persistent* parameter.
    '''
    ntprop = _NtProperty(key, defaultValue, writeDefault, persistent)
    NetworkTables._ntproperties.add(ntprop)
    
    return property(fget=ntprop.get, fset=ntprop.set, doc=doc)



class ChooserControl(object):
    '''
        Interacts with a :class:`wpilib.sendablechooser.SendableChooser`
        object over NetworkTables.
    '''
    
    def __init__(self, key, on_choices=None, on_selected=None):
        '''
            :param key: NetworkTables key
            :type  key: str
            :param on_choices: A function that will be called when the
                               choices change. Signature: fn(value)
            :param on_selection: A function that will be called when the
                                 selection changes. Signature: fn(value)
        '''
        
        self.subtable = NetworkTables.getTable('SmartDashboard').getSubTable(key)

        self.on_choices = on_choices
        self.on_selected = on_selected
        
        if on_choices or on_selected:
            self.subtable.addTableListener(self._on_change, True)

    def close(self):
        '''Stops listening for changes to the ``SendableChooser``'''
        if self.on_choices or self.on_selected:
            self.subtable.removeTableListener(self._on_change)
    
    def getChoices(self):
        '''
            Returns the current choices. If the chooser doesn't exist, this
            will return an empty tuple.
        
            :rtype: tuple
        '''
        return self.subtable.getStringArray('options', ())
    
    def getSelected(self):
        '''
            Returns the current selection or None
        
            :rtype: str
        '''
        selected = self.subtable.getString('selected', None)
        if selected is None:
            selected = self.subtable.getString('default', None)
        return selected
    
    def setSelected(self, selection):
        '''
            Sets the active selection on the chooser
            
            :param selection: Active selection name
        '''
        self.subtable.putString('selected', selection)
    
    def _on_change(self, table, key, value, isNew):
        if key == 'options':
            if self.on_choices is not None:
                self.on_choices(value)
        elif key == 'selected':
            if self.on_selected is not None:
                self.on_selected(value)
        elif key == 'default':
            if self.on_selected is not None and self.subtable.getString('selected', None) is None:
                self.on_selected(value)

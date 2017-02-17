
from .networktables import NetworkTables

from ntcore.value import Value

__all__ = [
    'ntproperty',
    'ChooserControl'
]


def ntproperty(key, defaultValue, writeDefault=True, doc=None):
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
                  
        .. versionadded:: 2015.3.0
    '''
    
    nt = NetworkTables
    
    ntvalue = nt.getGlobalAutoUpdateValue(key, defaultValue, writeDefault)
    mkv = ntvalue._valuefn
    
    def _get(_):
        return ntvalue.value
    
    def _set(_, value):
        nt._api.setEntryValue(key, mkv(value))
    
    return property(fget=_get, fset=_set, doc=doc)



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

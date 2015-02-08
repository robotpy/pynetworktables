
from networktables2 import StringArray
from .networktable import NetworkTable

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
        
        self.subtable = NetworkTable.getTable('SmartDashboard').getSubTable(key)

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
            will return an empty array.
        
            :rtype: :class:`.StringArray`
        '''
        choices = StringArray()
        try:
            self.subtable.retrieveValue('options', choices)
        except KeyError:
            pass
        return choices
    
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

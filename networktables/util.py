from typing import Callable, Optional, Sequence

from . import NetworkTablesInstance

__all__ = ["ntproperty", "ChooserControl"]

NetworkTables = NetworkTablesInstance.getDefault()


class _NtProperty:
    def __init__(
        self,
        key: str,
        defaultValue,
        writeDefault: bool,
        persistent: bool,
        inst: NetworkTablesInstance,
    ) -> None:
        self.key = key
        self.defaultValue = defaultValue
        self.writeDefault = writeDefault
        self.persistent = persistent
        # never overwrite persistent values with defaults
        if persistent:
            self.writeDefault = False
        self.inst = inst
        if hasattr(self.inst, "_api"):
            self.set = self._set_pynetworktables
        else:
            self.set = self._set_pyntcore

        self.reset()

    def reset(self):
        self.ntvalue = self.inst.getGlobalAutoUpdateValue(
            self.key, self.defaultValue, self.writeDefault
        )
        if self.persistent:
            self.ntvalue.setPersistent()

        if hasattr(self.inst, "_api"):
            from _pynetworktables import Value
        else:
            from . import Value

        # this is an optimization, but presumes the value type never changes
        self.mkv = Value.getFactoryByType(self.ntvalue.getType())

    def get(self, _):
        return self.ntvalue.value

    def _set_pynetworktables(self, _, value):
        self.inst._api.setEntryValueById(self.ntvalue._local_id, self.mkv(value))

    def _set_pyntcore(self, _, value):
        self.ntvalue.setValue(self.mkv(value))


def ntproperty(
    key: str,
    defaultValue,
    writeDefault: bool = True,
    doc: str = None,
    persistent: bool = False,
    *,
    inst: NetworkTablesInstance = NetworkTables
) -> property:
    """
    A property that you can add to your classes to access NetworkTables
    variables like a normal variable.

    :param key: A full NetworkTables key (eg ``/SmartDashboard/foo``)
    :param defaultValue: Default value to use if not in the table
    :type  defaultValue: any
    :param writeDefault: If True, put the default value to the table,
                         overwriting existing values
    :param doc: If given, will be the docstring of the property.
    :param persistent: If True, persist set values across restarts.
                       *writeDefault* is ignored if this is True.
    :param inst: The NetworkTables instance to use.

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

    .. warning::

       This function assumes that the value's type
       never changes. If it does, you'll get really strange
       errors... so don't do that.

    .. versionadded:: 2015.3.0

    .. versionchanged:: 2017.0.6
        The *doc* parameter.

    .. versionchanged:: 2018.0.0
        The *persistent* parameter.
    """
    ntprop = _NtProperty(key, defaultValue, writeDefault, persistent, inst)
    try:
        inst._ntproperties.add(ntprop)
    except AttributeError:
        pass  # pyntcore compat

    return property(fget=ntprop.get, fset=ntprop.set, doc=doc)


class ChooserControl(object):
    """
    Interacts with a :class:`wpilib.SendableChooser`
    object over NetworkTables.
    """

    def __init__(
        self,
        key: str,
        on_choices: Optional[Callable[[Sequence[str]], None]] = None,
        on_selected: Optional[Callable[[str], None]] = None,
        *,
        inst: NetworkTablesInstance = NetworkTables
    ) -> None:
        """
        :param key: NetworkTables key
        :param on_choices: A function that will be called when the
                           choices change.
        :param on_selection: A function that will be called when the
                             selection changes.
        :param inst: The NetworkTables instance to use.
        """
        self.subtable = inst.getTable("SmartDashboard").getSubTable(key)

        self.on_choices = on_choices
        self.on_selected = on_selected

        if on_choices or on_selected:
            self.subtable.addTableListener(self._on_change, True)

    def close(self) -> None:
        """Stops listening for changes to the ``SendableChooser``"""
        if self.on_choices or self.on_selected:
            self.subtable.removeTableListener(self._on_change)

    def getChoices(self) -> Sequence[str]:
        """
        Returns the current choices. If the chooser doesn't exist, this
        will return an empty tuple.
        """
        return self.subtable.getStringArray("options", ())

    def getSelected(self) -> Optional[str]:
        """
        Returns the current selection or None
        """
        selected = self.subtable.getString("selected", None)
        if selected is None:
            selected = self.subtable.getString("default", None)
        return selected

    def setSelected(self, selection: str) -> None:
        """
        Sets the active selection on the chooser

        :param selection: Active selection name
        """
        self.subtable.putString("selected", selection)

    def _on_change(self, table, key, value, isNew):
        if key == "options":
            if self.on_choices is not None:
                self.on_choices(value)
        elif key == "selected":
            if self.on_selected is not None:
                self.on_selected(value)
        elif key == "default":
            if (
                self.on_selected is not None
                and self.subtable.getString("selected", None) is None
            ):
                self.on_selected(value)

#
# Ensure that the NetworkTableEntry objects work
#


def test_entry_value(nt):
    e = nt.getEntry("/k1")
    assert e.getString(None) is None
    e.setString("value")
    assert e.getString(None) == "value"
    e.delete()
    assert e.getString(None) is None
    e.setString("value")
    assert e.getString(None) == "value"


def test_entry_persistence(nt):
    e = nt.getEntry("/k2")

    for _ in range(2):

        assert not e.isPersistent()
        # persistent flag cannot be set unless the entry has a value
        e.setString("value")

        assert not e.isPersistent()
        e.setPersistent()
        assert e.isPersistent()
        e.clearPersistent()
        assert not e.isPersistent()

        e.delete()

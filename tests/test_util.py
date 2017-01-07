
from networktables.util import ntproperty, ChooserControl
import pytest


def test_autoupdatevalue(nt):

    # tricksy: make sure that this works *before* initialization
    # of network tables happens!
    nt.shutdown()
    
    foo = nt.getGlobalAutoUpdateValue('/SmartDashboard/foo', True, True)
    assert foo.value == True
    assert foo.get() == True
    
    nt.setTestMode()
    nt.initialize()
    
    assert foo.value == True
    assert foo.get() == True
    
    t = nt.getTable('/SmartDashboard')
    assert t.getBoolean('foo') == True
    t.putBoolean('foo', False)
    
    assert foo.value == False


def test_ntproperty(nt, nt_flush):
    
    class Foo(object):
        robotTime = ntproperty('/SmartDashboard/robotTime', 0, writeDefault=False)
        dsTime = ntproperty('/SmartDashboard/dsTime', 0, writeDefault=True)
        testArray = ntproperty('/SmartDashboard/testArray', [1,2,3], writeDefault=True)
        
    f = Foo()
    
    t = nt.getTable('/SmartDashboard')
        
    assert f.robotTime == 0
    assert t.getNumber('robotTime') == 0
    
    f.robotTime = 2
    assert t.getNumber('robotTime') == 2 
    
    t.putNumber('robotTime', 4)
    assert f.robotTime == 4
    
    assert f.testArray == [1,2,3]
    f.testArray = [4,5,6]
    assert f.testArray == (4,5,6)

def test_ntproperty_emptyarray(nt):
    with pytest.raises(TypeError):
        class Foo1(object):
            testArray = ntproperty('/SmartDashboard/testArray', [], writeDefault=True)
            
    with pytest.raises(TypeError):
        class Foo2(object):
            testArray = ntproperty('/SmartDashboard/testArray', [], writeDefault=False)

def test_chooser_control(nt):
    
    c = ChooserControl('Autonomous Mode')
    
    assert c.getChoices() == ()
    assert c.getSelected() is None
    
    c.setSelected("foo")
    assert c.getSelected() == 'foo'
    
    t = nt.getTable('/SmartDashboard/Autonomous Mode')
    assert t.getString('selected') == 'foo'
    
    t.putStringArray('options', ('option1', 'option2'))
    assert c.getChoices() == ('option1', 'option2')
    
    
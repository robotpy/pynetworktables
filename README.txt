
What is this?
=============

This is a python wrapper for NetworkTables (and SmartDashboard) found in 
the WPILib for FIRST Robotics. This can be run on any PC running python.

You can use this library to be either a client or a server.

    robot code is a server
    dashboard code is a client
    
This is not a reimplementation of NetworkTables, but leverages the exact
same code (mostly) that your robot code uses to do NetworkTables. These
are just simple Python bindings on top of those. 

Our team has successfully used this in FRC competitions to communicate
with our robot from the Driver Station.
    
    
Supported platforms
===================
    
pynetworktables makes WPILib's NetworkTables truly cross-platform, and
has been used and tested in the following configurations:
    
    Windows 7 x64
        - Python 3.2 x64, MSVC
        - Python 2.7 x86, MSVC
    
    It is not currently recommended to use MinGW to build pynetworktables.
    
    Linux x64 (Ubuntu 12.10+, Fedora 20)
        - Python 3.2

    OSX 10.8.5
        - Python 2.7 & 3.2

Build Requirements
==================

You must have a compiler installed that is supported by python distutils.

Additionally, SIP 4.15.3 or above must be installed. You can get SIP at:

    http://www.riverbankcomputing.com/software/sip/

You must get the source code for RobotPy to somewhere on your computer.
You can do this using git:

    git clone https://github.com/robotpy/robotpy.git robotpy
    cd robotpy
    git checkout 2014
    git submodule init
    git submodule update

WARNINGS: 
    - RobotPy uses submodules, and if you do not check them out you will
    get build failures when building pynetworktables
    - pynetworktables is generally tested against the very latest build
    of RobotPy, and will not work correctly against older versions!
    - Note that the version of pynetworktables corresponds to the branch
    of the RobotPy code. So, 2014.1 works with RobotPy 2014 branch, 2013.4
    works with RobotPy 2013 branch, etc.  


Build Instructions
==================

Use the following commands to build & install pynetworktables. Do the following
on Windows:

    set ROBOTPY=c:\path\to\robotpy
    c:\python33\python.exe setup.py build install
    
Do the following on Linux or OSX:

    ROBOTPY="/path/to/robotpy" python setup.py build
    sudo ROBOTPY="/path/to/robotpy" python setup.py install

    ROBOTPY="/path/to/robotpy" python3 setup.py build
    sudo ROBOTPY="/path/to/robotpy" python3 setup.py install

Usage
=====

See the 'samples' directory for sample programs. The object and method names
should all match the C++ API.


Differences between pynetworktables and the C++ API
===================================================

Something like 99% of the LiveWindow, NetworkTables, networktables2, and 
SmartDashboard API's are wrapped and implemented. However, unless you really
like pain you will usually only want to use NetworkTable and the SmartDashboard
objects.

SmartDashboard does not support the RetrieveValue or GetData functions.

NetworkTable::GetValue does not return an EntryValue object, but instead
returns a python object of the correct type for float, booleans, and strings.

Anything that uses an EntryValue object is probably not supported, or may
not actually work the way you might expect.


Bugs
====

If you get an 'unknown' exception, please file a bug report on the github 
tracker and report what function you called that threw that exception. The
API does not explicitly call out which functions will throw exceptions, so
they may pop up in unexpected places. 

If you find additional bugs, please report them on the github tracker. 



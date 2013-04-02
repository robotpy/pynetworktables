
What is this?
=============

This is a python wrapper for NetworkTables (and SmartDashboard) found in 
the WPILib for FIRST Robotics. This can be run on any PC running python.

You can use this library to be either a client or a server.

    robot code is a server
    dashboard code is a client

Build Requirements
==================

pynetworktables has been found to work on Windows and Linux, on x86 and
x64 platforms, in python 2.7 and 3.x. 

You must have a compiler installed that is supported by python distutils.

Additionally, SIP must be installed. You can get SIP at:

    http://www.riverbankcomputing.com/software/sip/

You must get the source code for RobotPy to somewhere on your computer.
You can do this using git:

    git clone https://github.com/robotpy/robotpy.git robotpy
    cd robotpy
    git submodule init
    git submodule update

WARNINGS: 
    - RobotPy uses submodules, and if you do not check them out you will
    get build failures when building pynetworktables
    - pynetworktables is generally tested against the very latest build
    of RobotPy, and may not work correctly against older versions! 


Build Instructions
==================

Use the following commands to build pynetworktables. Do the following on 
Windows:

    set ROBOTPY=c:\path\to\robotpy
    c:\python33\python.exe setup.py build
    
Do the following on Linux:

    ROBOTPY="/path/to/robotpy" python3 setup.py build
    
To install to your site-packages, you can just run the following command:

    python3 setup.py install

Usage
=====

See the 'samples' directory for sample programs. 

- Python 2.7 Note

    NOTE: This is no longer true as of RobotPy sip bindings after 4/1/2013

    pynetworktables will compile and run on Python 2.7 and 3.x, but the SIP
    bindings it uses treats all strings as unicode, so on python 2.7 you 
    need to pass strings to it in the form of u'String' instead of 'String', 
    otherwise you will get errors complaining about invalid parameter types. 
    
Tested Platforms
================
    
    Windows 7 x64
        - Python 3.2 x64, MSVC
        - Python 2.7 x86, MSVC
    
    It is not currently recommended to use MinGW to build pynetworktables
    
    Linux x64 (Ubuntu 12.10)
        - Python 3.2

    


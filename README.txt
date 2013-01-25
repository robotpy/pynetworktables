
What is this?
=============

This is a python wrapper for NetworkTables (and SmartDashboard) found in 
the WPILib for FIRST Robotics. This can be run on any PC running python.

You can use this library to be either a client or a server.

    robot code is a server
    dashboard code is a client

Build Requirements
==================

You must have a compiler installed that is supported by python distutils.

Additionally, SIP must be installed. You can get SIP at:

    http://www.riverbankcomputing.com/software/sip/

You must get the source code for RobotPy to somewhere on your computer.
You can do this using git:

    git clone https://github.com/robotpy/robotpy.git


Build Instructions
==================

Use the following commands to build pynetworktables. Do the following on 
Windows:

    set ROBOTPY=c:\path\to\robotpy\src
    c:\python33\python.exe setup.py build
    
Do the following on Linux:

    ROBOTPY="/path/to/robotpy" python3 setup.py build
    
To install to your site-packages, you can just run the following command:

    python3 setup.py install

Usage
=====

See the 'samples' directory for sample programs. 
    
    
Tested Platforms
================
    
    Windows 7 x64
        - Python 3.2, MSVC
    
    Linux x64
        - Python 3.2




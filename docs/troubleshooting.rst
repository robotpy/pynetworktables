Troubleshooting
===============

Ensure you're using the correct mode
------------------------------------

If you're running pynetworktables as part of RobotPy -- relax, pynetworktables
is setup automatically for you. 

If you're trying to connect to the robot from a coprocessor (such as a
Raspberry Pi) or from the driver station, then you will need to ensure that
you:

* Enable client mode
* Tell pynetworktables to connect to the correct hostname

Code to do that looks like this::

    from networktables import NetworkTable

    NetworkTable.setIPAddress(hostname)
    NetworkTable.setClientMode()
    NetworkTable.initialize()


Yes, I know it says `setIPAddress`... it will accept a hostname also. If you
are team 1234, then the hostname would be 'roborio-1234-frc.local'. Make sure you
have an mDNS client installed on the coprocessor (like avahi)!

How to tell if a connection is made
-----------------------------------

If you have enabled python logging, look for messages that look like this::

    INFO:nt:Client 0x1018afa90 entered connection state: CONNECTED_TO_SERVER
    INFO:nt:Client 0x1018afa90 entered connection state: IN_SYNC_WITH_SERVER

If you see those messages, it means that your client has connected to the
robot successfully. If you don't see it, that means there's still a problem.

External tools
--------------

WPI's TableViewer is a great tool for connecting to networktables and seeing
what's being transmitted.

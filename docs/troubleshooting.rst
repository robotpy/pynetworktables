Troubleshooting
===============

Ensure you're using the correct mode
------------------------------------

If you're running pynetworktables as part of a RobotPy robot -- relax,
pynetworktables is setup as a server automatically for you, just like in
WPILib!

If you're trying to connect to the robot from a coprocessor (such as a
Raspberry Pi) or from the driver station, then you will need to ensure that
you initialize pynetworktables correctly. 

Thankfully, this is super easy as of 2017. Here's the code::

    from networktables import NetworkTables

    NetworkTables.initialize(server='10.xx.xx.2')

Don't know what the right hostname is? That's what the next section is for...

Use static IPs when using pynetworktables
-----------------------------------------

FIRST introduced the mDNS based addressing for the RoboRIO in 2015, and
generally teams that use additional devices have found that while it works at
home and sometimes in the pits, it tends to not work correctly on the field at
events. For this reason, if you use pynetworktables on the field, you should
`ensure every device has a static IP address`.

To connect to your RoboRIO, use the following addresses:

* Static IPs are ``10.XX.XX.2`` 
* mDNS Hostnames are ``roborio-XXXX-frc.local`` (don't use these!)

For example, if your team number was 1234, then the static IP to connect to
would be  ``10.12.34.2``. 

For information on configuring your RoboRIO and other devices to use static IPs, see the 
`WPILib screensteps documentation <https://wpilib.screenstepslive.com/s/4485/m/24193/l/319135-ip-networking-at-the-event>`_.

How to tell if a connection is made
-----------------------------------

If you have enabled python logging (each of the pynetworktables examples have
basic logging enabled), look for messages that look like this::

    INFO:nt:CONNECTED 10.14.18.2 port 40162 (...)

If you see a message like this, it means that your client has connected to the
robot successfully. If you don't see it, that means there's still a problem.

External tools
--------------

WPILib's TableViewer is a great tool for connecting to networktables and seeing
what's being transmitted.

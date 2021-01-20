RobotPy NetworkTables Project
=============================

This is a pure python implementation of the NetworkTables protocol, derived
from the wpilib ntcore C++ implementation. In FRC, the NetworkTables protocol
is used to pass non-Driver Station data to and from the robot across the network.

This implementation is intended to be compatible with python 3.5 and later.
All commits to the repository are automatically tested on all supported python
versions using github actions.

.. note:: NetworkTables is a protocol used for robot communication in the
          FIRST Robotics Competition, and can be used to talk to
          SmartDashboard/SFX. It does not have any security, and should never
          be used on untrusted networks.

.. note:: If you require support for Python 2.7, use pynetworktables 2018.2.0

Documentation
-------------

For usage, detailed installation information, and other notes, please see
our documentation at http://pynetworktables.readthedocs.io

Don't understand this NetworkTables thing? Check out our `basic overview of
NetworkTables <http://robotpy.readthedocs.io/en/stable/guide/nt.html>`_.

Installation
------------

On the RoboRIO, you don't install this directly, but use the RobotPy installer
to install it on your RoboRIO, or it is installed by pip as part of the
pyfrc setup process.

On something like a coprocessor, driver station, or laptop, make sure pip is
installed, connect to the internet, and install like so:

::

    pip install pynetworktables

Support
-------

The RobotPy project has a mailing list that you can send emails to for
support: robotpy@googlegroups.com. Keep in mind that the maintainers of
RobotPy projects are also members of FRC Teams and do this in their free
time.

If you find a bug, please file a bug report using github
https://github.com/robotpy/pynetworktables/issues/new

Contributing new changes
------------------------

RobotPy is an open project that all members of the FIRST community can
easily and quickly contribute to. If you find a bug, or have an idea that you
think others can use:

1. `Fork this git repository <https://github.com/robotpy/pynetworktables/fork>`_ to your github account
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push -u origin my-new-feature`)
5. Create new Pull Request on github

Authors & Contributors
======================

* Dustin Spicuzza, FRC Team 1418/2423
* Peter Johnson, FRC Team 294

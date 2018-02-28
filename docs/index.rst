pynetworktables documentation
=============================

This is a pure python implementation of the NetworkTables protocol, derived
from the wpilib ntcore C++ implementation. In FRC, the NetworkTables protocol
is used to pass non-Driver Station data to and from the robot across the network.

Don't understand this NetworkTables thing? Check out our :ref:`basic overview of
NetworkTables <networktables_guide>`.

This implementation is intended to be compatible with python 2.7 and python 3.3+.
All commits to the repository are automatically tested on all supported python
versions using Travis-CI.

.. note:: NetworkTables is a protocol used for robot communication in the
          FIRST Robotics Competition, and can be used to talk to
          SmartDashboard/SFX. It does not have any security, and should never
          be used on untrusted networks.

.. include:: _sidebar.rst.inc

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

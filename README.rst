RobotPy NetworkTables
=====================

.. image:: https://travis-ci.org/robotpy/pynetworktables.svg
    :target: https://travis-ci.org/robotpy/pynetworktables

A pure python implementation of NetworkTables, originally derived from the
java implementation.  NetworkTables are used to pass non-Driver
Station data to and from the robot across the network.

This implementation is intended to be compatible with python 2.7 and 3.4.

Installation
============

On the RoboRIO, you don't install this directly, but use the RobotPy installer
to install it on your RoboRIO, or it is installed by pip as part of the
pyfrc setup process.

On something like a coprocessor, driver station, or laptop, make sure pip is
installed, connect to the internet, and install like so:

    pip install pynetworktables


Usage
=====

pynetworktables comes with a number of samples that show very basic use
cases for NetworkTables, look in the samples directory.

Implementation differences as of 2015
=====================================

* Implementation is pure python, no SIP compilation required!
* API is now based on the Java implementation, methods are
  now camelCase, instead of CapsCase
* NetworkTables objects are found in the networktables package, and
  not in the pynetworktables package

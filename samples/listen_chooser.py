#!/usr/bin/env python3
#
# This is a NetworkTables client (eg, the DriverStation/coprocessor side).
# You need to tell it the IP address of the NetworkTables server (the
# robot or simulator).
#
# This shows how to use a listener to listen for changes to a SendableChooser
# object.
#

from __future__ import print_function

import sys
import time
from networktables import NetworkTables
from networktables.util import ChooserControl

# To see messages from networktables, you must setup logging
import logging
logging.basicConfig(level=logging.DEBUG)

if len(sys.argv) != 2:
    print("Error: specify an IP to connect to!")
    exit(0)

ip = sys.argv[1]

NetworkTables.initialize(server=ip)


def on_choices(value):
    print('OnChoices', value)

def on_selected(value):
    print('OnSelected', value)


cc = ChooserControl('Autonomous Mode',
                    on_choices,
                    on_selected)

while True:
    time.sleep(1)

 

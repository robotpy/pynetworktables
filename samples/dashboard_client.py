#!/usr/bin/env python3
#
# Does the same thing as the SmartDashboard. Sorta. 
#

import sys
import time
from pynetworktables import *

if len(sys.argv) != 2:
    print("Error: specify an IP to connect to!")
    exit(0)

ip = sys.argv[1]

NetworkTable.SetIPAddress(ip)
NetworkTable.SetClientMode()
NetworkTable.Initialize()

table = NetworkTable.GetTable("SmartDashboard")

while True:
    try:
        print("SmartDashboard::test: %s" % table.GetNumber('test'))
    except:
        print("No value yet")
    time.sleep(1)


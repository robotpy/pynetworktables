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

class Listener(ITableListener):
    def __init__(self):
        ITableListener.__init__(self)
        
    def ValueChanged(self, table, key, value, isNew):
        print('Value changed: key %s, isNew: %s: %s' % (key, isNew, table.GetValue(key)))

listener = Listener()
        
table = NetworkTable.GetTable("SmartDashboard")
table.AddTableListener(listener)

while True:
    time.sleep(1)

 

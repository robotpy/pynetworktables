#!/usr/bin/env python3
#
# Simple benchmark script that tests NetworkTables throughput.
#
# To run the server
#
#     python3 benchmark.py
#
# To run the client:
#
#    python3 benchmark.py 127.0.0.1
#
# In theory, the limiting factor is internal buffering and not network
# bandwidth, so running this test on a local machine should be mostly
# valid.
#
# On OSX with default write flush period, I average ~18hz
#

from __future__ import print_function

from argparse import ArgumentParser
import time

import logging
logging.basicConfig(level=logging.DEBUG)

from networktables import NetworkTables

class Benchmark(object):

    def __init__(self):
        
        parser = ArgumentParser()
        parser.add_argument('client', nargs='?', default=None)
        parser.add_argument('-r', '--rate', default=None, type=float)
        parser.add_argument('--send', default=False, action='store_true')
        
        args = parser.parse_args()
        
        if args.client:
            NetworkTables.initialize(server=args.client)
        else:
            NetworkTables.initialize()
         
        # Default write flush is 0.05, could adjust for less latency
        if args.rate is not None:
            print("Setting rate to %s" % args.rate)
            NetworkTables.setUpdateRate(args.rate)
        
        self.nt = NetworkTables.getTable('/benchmark')
        self.updates = 0
        
        self.nt.addTableListener(self.on_update)
        
        if args.send:
            self.send_benchmark()
        else:
            self.recv_benchmark()

    def on_update(self, *args):
        self.updates += 1

    def recv_benchmark(self):
        
        print("Starting to receive")
        
        last = None
        last_updates = 0
        
        while True:
            
            now = time.time()
            updates = self.updates
            
            if last is not None:
                rate = (updates - last_updates) / (now - last)
                print('Update rate:', rate)
            
            last = now
            last_updates = updates
            time.sleep(1)
            
    def send_benchmark(self):
        
        print("Sending")
        
        i = 0
        
        while True:
            i += 1
            self.nt.putNumber('key', i)
            time.sleep(0.0001)
    
if __name__ == '__main__':
    Benchmark()

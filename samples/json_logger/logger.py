#!/usr/bin/env python3
#
# This is a simple working example of how to use pynetworktables to log data
# to a JSON file. The file is stored in the current working directory, and
# the filename is the current time combined with the event name and match number
#
# The data really can be anything, but this logs a single key. The way it's
# intended to be used is gather your data together, stick it in an array
# along with the current timestamp, then send it all over networktables
# as a number array.
#
# One example way to send the data on the robot is via something like
# wpilib.SmartDashboard.putNumberArray([time, data1, data2, ...])
#
# The reason this example uses that method is to ensure that all of the data
# received is transmitted at the same time. If you used multiple keys to send
# this data instead, the data could be slightly out of sync with each other.
#

from networktables import NetworkTables
from networktables.util import ntproperty

import json
import os.path
import queue
import sys
import time
import threading

import logging

logger = logging.getLogger("logger")

# FMSControlData bitfields
ENABLED_FIELD = 1 << 0
AUTO_FIELD = 1 << 1
TEST_FIELD = 1 << 2
EMERGENCY_STOP_FIELD = 1 << 3
FMS_ATTACHED_FIELD = 1 << 4
DS_ATTACHED_FIELD = 1 << 5


def translate_control_word(value):
    value = int(value)
    if value & ENABLED_FIELD == 0:
        return "disabled"
    if value & AUTO_FIELD:
        return "auto"
    if value & TEST_FIELD:
        return "test"
    else:
        return "teleop"


class DataLogger:

    # Change this key to whatever NT key you want to log
    log_key = "/SmartDashboard/log_data"

    # Data file where robot IP is stored so you don't have to keep typing it
    cache_file = ".robot"

    matchNumber = ntproperty("/FMSInfo/MatchNumber", 0, False)
    eventName = ntproperty("/FMSInfo/EventName", "unknown", False)

    def __init__(self):
        self.queue = queue.Queue()
        self.mode = "disabled"
        self.data = []
        self.lock = threading.Lock()

    def connectionListener(self, connected, info):
        # set our robot to 'disabled' if the connection drops so that we can
        # guarantee the data gets written to disk
        if not connected:
            self.valueChanged("/FMSInfo/FMSControlData", 0, False)

    def valueChanged(self, key, value, isNew):

        if key == "/FMSInfo/FMSControlData":

            mode = translate_control_word(value)

            with self.lock:
                last = self.mode
                self.mode = mode

                data = self.data
                self.data = []

            logger.info("Robot mode: %s -> %s", last, mode)

            # This example only stores on auto -> disabled transition. Change it
            # to whatever it is that you need for logging
            if last == "auto":

                tm = time.strftime("%Y%m%d-%H%M-%S")
                name = "%s-%s-%s.json" % (tm, self.eventName, int(self.matchNumber))
                logger.info("New file: %s (%d items received)", name, len(data))

                # We don't write the file from within the NetworkTables callback,
                # because we don't want to block the thread. Instead, write it
                # to a queue along with the filename so it can be written
                # from somewhere else
                self.queue.put((name, data))

        elif key == self.log_key:
            if self.mode != "disabled":
                with self.lock:
                    self.data.append(value)

    def run(self):

        # Determine what IP to connect to
        try:
            server = sys.argv[1]

            # Save the robot ip
            if not os.path.exists(self.cache_file):
                with open(self.cache_file, "w") as fp:
                    fp.write(server)
        except IndexError:
            try:
                with open(self.cache_file) as fp:
                    server = fp.read().strip()
            except IOError:
                print("Usage: logger.py [10.xx.yy.2]")
                return

        logger.info("NT server set to %s", server)
        NetworkTables.initialize(server=server)

        # Use listeners to receive the data
        NetworkTables.addConnectionListener(
            self.connectionListener, immediateNotify=True
        )
        NetworkTables.addEntryListener(self.valueChanged)

        # When new data is queued, write it to disk
        while True:
            name, data = self.queue.get()
            with open(name, "w") as fp:
                json.dump(data, fp)


if __name__ == "__main__":

    log_datefmt = "%H:%M:%S"
    log_format = "%(asctime)s:%(msecs)03d %(levelname)-8s: %(name)-20s: %(message)s"

    logging.basicConfig(level=logging.DEBUG, datefmt=log_datefmt, format=log_format)

    dl = DataLogger()
    dl.run()

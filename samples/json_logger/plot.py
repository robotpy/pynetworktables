#!/usr/bin/env python3
#
# This example uses matplotlib to graph data received from the logger example.
# It is assumed that the key being logged is a number array, and the first
# item of that array is the Timer.getFPGATimestamp() on the robot.
#
# One example way to send the data on the robot is via something like
# wpilib.SmartDashboard.putNumberArray([time, data1, data2, ...])
#

import json
import sys

import matplotlib.pyplot as plt
import numpy as np

if __name__ == "__main__":
    with open(sys.argv[1]) as fp:
        data = json.load(fp)

    if len(data) == 0:
        print("No data received")
        exit(0)

    # Change the time to
    offset = data[0][0]
    for d in data:
        d[0] -= offset

    print("Received", len(data), "rows of data, total time was %.3f seconds" % d[0])

    # Transform the data into a numpy array to make it easier to use
    data = np.array(data)

    # This allows you to use data[N] to refer to each column of data individually
    data = data.transpose()

    # This silly plot graphs
    # - x: data[0]: this is time
    # - y: data[1]: column1
    #
    # - x2: data[0]: Time yet again
    # - y2: data[1] - data[2]: subtracts columns from each other (something numpy allows)
    plt.plot(data[0], data[1], data[0], data[1] - data[2])
    plt.title("Encoder error")

    plt.show()

#!/usr/bin/env python3
#
# Sample RobotPy program that demonstrates how to send data to the logger
# example program
#
# This is NOT REQUIRED to use the example, any robot language can be used!
# Translate the necessary bits into your own robot code.s
#

import wpilib


class MyRobot(wpilib.IterativeRobot):
    """Main robot class"""

    def robotInit(self):
        """Robot-wide initialization code should go here"""

    def autonomousInit(self):
        """Called only at the beginning of autonomous mode"""
        self.useless = 1

    def autonomousPeriodic(self):
        """Called every 20ms in autonomous mode"""
        self.useless += 1

        # Obviously, this is fabricated... do something more useful!
        data1 = self.useless
        data2 = self.useless * 2

        # Only write once per loop
        wpilib.SmartDashboard.putNumberArray(
            "log_data", [wpilib.Timer.getFPGATimestamp(), data1, data2]
        )

    def disabledInit(self):
        """Called only at the beginning of disabled mode"""
        pass

    def disabledPeriodic(self):
        """Called every 20ms in disabled mode"""
        pass

    def teleopInit(self):
        """Called only at the beginning of teleoperated mode"""
        pass

    def teleopPeriodic(self):
        """Called every 20ms in teleoperated mode"""


if __name__ == "__main__":
    wpilib.run(MyRobot)

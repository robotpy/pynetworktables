# validated: 2018-11-27 DS ac751d32247e cpp/ConnectionNotifier.cpp cpp/ConnectionNotifier.h cpp/IConnectionNotifier.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

from collections import namedtuple

from .callback_manager import CallbackManager, CallbackThread

_ConnectionCallback = namedtuple("ConnectionCallback", ["callback", "poller_uid"])

_ConnectionNotification = namedtuple(
    "ConnectionNotification", ["connected", "conn_info"]
)


class ConnectionNotifierThread(CallbackThread):
    def __init__(self):
        CallbackThread.__init__(self, "connection-notifier")

    def matches(self, listener, data):
        return True

    def setListener(self, data, listener_uid):
        pass

    def doCallback(self, callback, data):
        callback(data)


class ConnectionNotifier(CallbackManager):

    THREAD_CLASS = ConnectionNotifierThread

    def add(self, callback):
        return self.doAdd(_ConnectionCallback(callback, None))

    def addPolled(self, poller_uid):
        return self.doAdd(_ConnectionCallback(None, poller_uid))

    def notifyConnection(self, connected, conn_info, only_listener=None):
        self.send(only_listener, _ConnectionNotification(connected, conn_info))

    def start(self):
        CallbackManager.start(self)

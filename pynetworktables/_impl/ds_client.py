# validated: 2018-11-27 DS 18c8cce6a78d cpp/DsClient.cpp cpp/DsClient.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

import json
import threading

from .support.safe_thread import SafeThread
from .tcpsockets.tcp_connector import TcpConnector

import logging

logger = logging.getLogger("nt")


class DsClient(object):
    def __init__(self, dispatcher, verbose=False):
        self.m_dispatcher = dispatcher
        self.verbose = verbose

        self.m_active = False
        self.m_owner = None  # type: SafeThread

        self.m_mutex = threading.Lock()
        self.m_cond = threading.Condition(self.m_mutex)

        self.m_port = None  # type: int
        self.m_stream = None

    def start(self, port):
        with self.m_mutex:
            self.m_port = port
            if not self.m_active:
                self.m_active = True
                self.m_owner = SafeThread(target=self._thread_main, name="nt-dsclient")

    def stop(self):
        with self.m_mutex:
            # Close the stream so the read (if any) terminates.
            self.m_active = False
            if self.m_stream:
                self.m_stream.close()
            self.m_cond.notify()

    def _thread_main(self):
        oldip = 0
        connector = TcpConnector(verbose=False, timeout=1)

        while self.m_active:
            # wait for periodic reconnect or termination
            with self.m_mutex:
                self.m_cond.wait_for(lambda: not self.m_active, timeout=0.5)
                port = self.m_port

            if not self.m_active:
                break

            self.m_stream = connector.connect(("127.0.0.1", 1742))
            if not self.m_active:
                break
            if not self.m_stream:
                continue

            while self.m_active and self.m_stream:
                json_blob = self.m_stream.readline()
                if not json_blob:
                    # We've reached EOF.
                    with self.m_mutex:
                        self.m_stream.close()
                        self.m_stream = None

                if not self.m_active:
                    break

                try:
                    obj = json.loads(json_blob.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                try:
                    ip = int(obj["robotIP"])
                except (KeyError, ValueError):
                    continue

                # If zero, clear the server override
                if ip == 0:
                    self.m_dispatcher.clearServerOverride()
                    oldip = 0
                    continue

                # If unchanged, don't reconnect
                if ip == oldip:
                    continue
                oldip = ip

                # Convert number into dotted quad
                ip_str = "%d.%d.%d.%d" % (
                    (ip >> 24) & 0xFF,
                    (ip >> 16) & 0xFF,
                    (ip >> 8) & 0xFF,
                    ip & 0xFF,
                )
                if self.verbose:
                    logger.info("client: DS overriding server IP to %s", ip_str)
                self.m_dispatcher.setServerOverride(ip_str, port)

            # We disconnected from the DS, clear the server override
            self.m_dispatcher.clearServerOverride()
            oldip = 0

        # Python note: we don't call Dispatcher.clearServerOverride() again.
        # Either it was already called, or we were never active.

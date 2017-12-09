# validated: 2017-12-09 DV 5ab20bb27c97 cpp/DsClient.cpp cpp/DsClient.h
#----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
#----------------------------------------------------------------------------

import json
import threading

from .support.compat import Condition
from .tcpsockets.tcp_connector import TcpConnector

import logging
logger = logging.getLogger('nt')


class DsClient(object):
    
    def __init__(self, dispatcher, verbose=False):
        self.m_dispatcher = dispatcher
        self.verbose = verbose

        self.m_active = False
        self.m_owner = None  # type: threading.Thread

        self.m_mutex = threading.Lock()
        self.m_cond = Condition(self.m_mutex)

        self.m_port = None  # type: int
        self.m_stream = None

    def start(self, port):
        with self.m_mutex:
            self.m_port = port
            if not self.m_active:
                self.m_active = True
                self.m_owner = threading.Thread(target=self._thread_main,
                                                name='nt-dsclient-thread')
                self.m_owner.daemon = True
                self.m_owner.start()

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

            self.m_stream = connector.connect(('127.0.0.1', 1742))
            if not self.m_active:
                break
            if not self.m_stream:
                continue

            while self.m_active and self.m_stream:
                # Read JSON "{...}".  This is very limited, does not handle
                # quoted "}" or nested {}, but is sufficient for this purpose.
                json_blob = bytearray()

                try:
                    # Throw away characters until {
                    while self.m_active:
                        ch = self.m_stream.read(1)
                        if ch == b'{':
                            break
                    json_blob.extend(b'{')

                    # Read characters until }
                    while self.m_active:
                        ch = self.m_stream.read(1)
                        json_blob.extend(ch)
                        if ch == b'}':
                            break

                except IOError:
                    # I think this should be protected to avoid stop() from throwing?
                    with self.m_mutex:
                        self.m_stream = None
                    break

                if not self.m_active:
                    break

                try:
                    obj = json.loads(json_blob.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                try:
                    ip = obj['robotIP']
                except KeyError:
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
                ip_str = '%d.%d.%d.%d' % ((ip >> 24) & 0xff, (ip >> 16) & 0xff,
                                          (ip >> 8) & 0xff, ip & 0xff)
                if self.verbose:
                    logger.info('client: DS overriding server IP to %s', ip_str)
                self.m_dispatcher.setServerOverride(ip_str, port)

            # We disconnected from the DS, clear the server override
            self.m_dispatcher.clearServerOverride()
            oldip = 0

        # Python note: we don't call Dispatcher.clearServerOverride() again.
        # Either it was already called, or we were never active.

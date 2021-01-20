# novalidate

import socket
import threading

from .tcp_stream import TCPStream

import logging

logger = logging.getLogger("nt.net")


class TcpConnector(object):
    def __init__(self, timeout, verbose):
        self.cond = threading.Condition()
        self.threads = {}
        self.active = False
        self.result = None
        self.timeout = timeout
        self.verbose = verbose

    def setVerbose(self, verbose):
        self.verbose = verbose

    def connect(self, server_or_servers):
        if isinstance(server_or_servers, tuple):
            server, port = server_or_servers
            return self._connect(server, port)

        # parallel connect
        # -> only connect to servers that aren't currently being connected to
        with self.cond:
            self.active = True
            for item in server_or_servers:
                if item not in self.threads:
                    th = threading.Thread(
                        target=self._thread, args=item, name="TcpConnector"
                    )
                    th.daemon = True
                    th.start()
                    self.threads[item] = th

            self.cond.wait(2 * self.timeout)
            self.active = False

            result = self.result
            self.result = None
            return result

    def _thread(self, server, port):
        stream = self._connect(server, port)
        with self.cond:
            self.threads.pop((server, port), None)
            if self.active and self.result is None:
                self.result = stream
                self.cond.notify()

    def _connect(self, server, port):
        try:
            if self.verbose:
                logger.debug("Trying connection to %s:%s", server, port)

            if self.timeout is None:
                sd = socket.create_connection((server, port))
            else:
                sd = socket.create_connection((server, port), timeout=self.timeout)
                sd.settimeout(None)

            return TCPStream(sd, server, port, "client")
        except IOError:
            if self.verbose:
                logger.debug("Connection to %s:%s failed", server, port)
            return

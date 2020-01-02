# novalidate

import select
import socket
import threading


class StreamEOF(IOError):
    pass


class TCPStream(object):
    def __init__(self, sd, peer_ip, peer_port, sock_type):

        self.m_sd = sd
        self.m_peerIP = peer_ip
        self.m_peerPort = peer_port

        self.m_rdsock = sd.makefile("rb")
        self.m_wrsock = sd.makefile("wb")

        self.close_lock = threading.Lock()

        # Python-specific for debugging
        self.sock_type = sock_type

    def read(self, size):

        # TODO: ntcore does a select to wait for read to be available. Necessary?

        data = self.m_rdsock.read(size)
        if size > 0 and len(data) != size:
            raise StreamEOF("end of file")
        return data

    def readline(self):
        return self.m_rdsock.readline()

    def readStruct(self, s):
        sz = s.size
        data = self.m_rdsock.read(sz)
        if len(data) != sz:
            raise StreamEOF("end of file")
        return s.unpack(data)

    def send(self, contents):
        self.m_wrsock.write(contents)
        self.m_wrsock.flush()

    def close(self):
        with self.close_lock:
            if self.m_sd:
                try:
                    self.m_sd.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

                self.m_sd.close()
                # self.m_sd = None

    def getPeerIP(self):
        return self.m_peerIP

    def getPeerPort(self):
        return self.m_peerPort

    def setNoDelay(self):
        self.m_sd.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _waitForReadEvent(self, timeout):
        r, _, _ = select.select((self.m_sd,), (), (), timeout)
        return len(r) > 0

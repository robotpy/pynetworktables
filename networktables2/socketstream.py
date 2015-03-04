
import socket
import sys

from . import _impl

__all__ = ["SocketStreamFactory", "SocketServerStreamProvider"]


class SocketStream:
    def __init__(self, conn):
        self.conn = conn

    def getInputStream(self):
        return _impl.sock_makefile(self.conn, 'rb')

    def getOutputStream(self):
        return _impl.sock_makefile(self.conn, 'wb')

    def close(self):
        self.conn.close()

class SocketStreamFactory:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def createStream(self):
        return SocketStream(_impl.sock_create_connection((self.host, self.port)))

class SocketServerStreamProvider:
    def __init__(self, port):
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('', port))
        self.server.listen(50)
        
        # this fails in 2.7... need a better way of dealing with this
        # -> However, robot servers are only running python 3, so it doesn't
        #    really matter at the moment..
        if sys.version_info[0] > 2:
            self.server.settimeout(1.0)

    def accept(self):
        return SocketStream(self.server.accept()[0])

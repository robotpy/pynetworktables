# notrack
'''
    This implements an undocumented protocol that the LabVIEW dashboard
    uses to receive information from the driver station. In particular,
    it sends data about what IP the robot is at.
    
    To use this, call NetworkTable.setDashboardMode()
'''

import socket
import struct
import threading

try:
    import SocketServer as socketserver
except ImportError:
    import socketserver

from .socketstream import SocketStreamFactory

import logging
logger = logging.getLogger('nt.dashboard')

_tagdata = struct.Struct('!hb')
_u32 = struct.Struct('!i')


class DsDataHandler(socketserver.StreamRequestHandler):
    '''
        Handler that receives data from the driver station
    
        Data is received as a stream of the following:
        
        * 2 bytes big endian: length to follow
        * 1 byte: tag
        * n-1 bytes: content
        
        Tag number 8 is the roborio IP address, and there should
        be 4 bytes received, transmitted in network order.
    '''
    
    def setup(self):
        socketserver.StreamRequestHandler.setup(self)
        logger.info("Driver Station connected! Waiting for robot...")
    
    def handle(self):
        while True:
            data = self.rfile.read(3)
            if not data:
                break
            
            data_len, tag = _tagdata.unpack(data)
            
            data = self.rfile.read(data_len-1)
            if not data:
                break
            
            if tag == 8:
                address = socket.inet_ntoa(data)
                self.server.notifyConnection(address)
    
    def finish(self):
        socketserver.StreamRequestHandler.finish(self)
        logger.info("Driver Station disconnected!")

class DsDataServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    
    daemon_threads = True
    allow_reuse_address = True
    
    def __init__(self, f):
        socketserver.TCPServer.__init__(self, ('0.0.0.0', 1741), DsDataHandler)
        self.notifyConnection = f.notifyConnection
        
class DashboardSocketStreamFactory(SocketStreamFactory):
    
    def __init__(self, ipAddress, port):
        self.server = DsDataServer(self)
        
        self.host = None
        self.port = port
        
        self.lock = threading.Condition()
        self.thread = threading.Thread(target=self._run, name="DashboardListener")
        self.thread.daemon = True
        self.thread.start()
        
        logger.info("Dashboard mode enabled, listening for DS comms")
    
    def _run(self):
        self.server.serve_forever()
    
    def createStream(self):
        with self.lock:
            while self.host is None:
                self.lock.wait()
        
            return SocketStreamFactory.createStream(self)
    
    def notifyConnection(self, address):
        if address == '0.0.0.0':
            address = None
            self.host = None
            
        elif self.host != address:
            logger.info("Driver Station says robot IP is %s", address)
            
            with self.lock:
                self.host = address
                self.lock.notify()

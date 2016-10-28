# validated: 2016-10-27 DS a7eca7d src/RpcServer.cpp src/RpcServer.h
'''----------------------------------------------------------------------------'''
''' Copyright (c) FIRST 2015. All Rights Reserved.                             '''
''' Open Source Software - may be modified and shared by FRC teams. The code   '''
''' must be accompanied by the FIRST BSD license file in the root directory of '''
''' the project.                                                               '''
'''----------------------------------------------------------------------------'''

from collections import namedtuple

import threading

from .message import Message
from .support.compat import Queue, Empty

import logging
logger = logging.getLogger('nt')


RpcCall = namedtuple('RpcCall', [
    'name',
    'msg',
    'func',
    'conn_id',
    'send_response',
    'conn_info'
])


class RpcServer(object):
    
    def __init__(self):
        
        self.m_call_thread = None
        
        self.m_mutex = threading.Lock()
        
        self.m_poll_queue = Queue()
        self.m_response_map = {}
        
        self.m_terminating = False
        self.m_on_start = None
        self.m_on_exit = None
        
        self.m_call_queue = Queue()

    def setOnStart(self, on_start):
        self.m_on_start = on_start
        
    def setOnExit(self, on_exit):
        self.m_on_exit = on_exit
   
    def start(self):
        if not self.m_call_thread:
            self.m_call_thread = threading.Thread(target=self._callThread,
                                                  name='nt-rpc-thread')
            self.m_call_thread.daemon = True
            self.m_call_thread.start()
             
    def stop(self):
        if self.m_call_thread:
            self.m_terminating = True
            self.m_call_queue.put(None)
            
            self.m_call_thread.join(1)
            if self.m_call_thread.is_alive():
                logger.warn("%s did not die", self.m_call_thread.name)
    
    def processRpc(self, name, msg, func, conn_id, send_response, conn_info):
        call = RpcCall(name, msg, func, conn_id, send_response, conn_info)
        if func:
            if self.m_call_thread:   
                self.m_call_queue.put(call)
        else:
            self.m_poll_queue.put(call)
            self.m_poll_cond.notify_one()
    
    def pollRpc(self, blocking, call_info, time_out=None):
        
        item = None
        while item is None:
            if self.m_terminating:
                return False
            
            try:
                item = self.m_poll_queue.get(blocking, time_out)
            except Empty:
                return False
    
        # do not include conn id if the result came from the server
        if item.conn_id != 0xffff:
            call_uid = (item.conn_id << 16) | item.msg.seq_num_uid()
        else:
            call_uid = item.msg.seq_num_uid()
    
        call_info.rpc_id = item.msg.id()
        call_info.call_uid = call_uid
        call_info.name = item.name
        call_info.params = item.msg.str()
        self.m_response_map[(item.msg.id(), call_uid)] = item.send_response
        
        return True
    
    def postRpcResponse(self, rpc_id, call_uid, result):
        send_response = self.m_response_map.pop((rpc_id, call_uid), None)
        if send_response is None:
            logger.warn("posting RPC response to nonexistent call (or duplicate response)")
            return
    
        send_response(Message.rpcResponse(rpc_id, call_uid, result))
    
    def _callThread(self):
        if self.m_on_start:
            self.m_on_start()
        
        while not self.m_terminating:
            
            item = self.m_call_queue.get()
            if not item:
                continue
            
            logger.debug("rpc calling %s", item.name)

            if not item.name or not item.msg or not item.func or not item.send_response:
                continue
            
            try:
                result = item.func(item.name, item.msg.str(), item.conn_info)
            except Exception:
                logger.warn("Exception while executing callback", exc_info=1)
            else:
                item.send_response(Message.rpcResponse(item.msg.id(),
                                                        item.msg.seq_num_uid(), result))
        
        if self.m_on_exit:
            self.m_on_exit()

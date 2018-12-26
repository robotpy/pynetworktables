# validated: 2018-11-27 DS ac751d32247e cpp/RpcServer.cpp cpp/RpcServer.h cpp/IRpcServer.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

from collections import namedtuple

from .callback_manager import CallbackManager, CallbackThread
from .message import Message

import logging

logger = logging.getLogger("nt")

_RpcListenerData = namedtuple("RpcListenerData", ["callback", "poller_uid"])

_RpcCall = namedtuple(
    "RpcCall", ["local_id", "call_uid", "name", "params", "conn_info", "send_response"]
)


class RpcServerThread(CallbackThread):
    def __init__(self):
        CallbackThread.__init__(self, "rpc-server")
        self.m_response_map = {}

    def matches(self, listener, data):
        return data.name and data.send_response

    def setListener(self, data, listener_uid):
        lookup_id = (data.local_id, data.call_uid)
        self.m_response_map[lookup_id] = data.send_response

    def doCallback(self, callback, data):
        local_id = data.local_id
        call_uid = data.call_uid
        lookup_id = (data.local_id, data.call_uid)
        callback(data)

        # send empty response
        send_response = self.m_response_map.get(lookup_id)
        if send_response:
            send_response(Message.rpcResponse(local_id, call_uid, ""))


class RpcServer(CallbackManager):

    THREAD_CLASS = RpcServerThread

    def add(self, callback):
        return self.doAdd(_RpcListenerData(callback, None))

    def addPolled(self, poller_uid):
        return self.doAdd(_RpcListenerData(None, poller_uid))

    def removeRpc(self, rpc_uid):
        return self.remove(rpc_uid)

    def processRpc(
        self, local_id, call_uid, name, params, conn_info, send_response, rpc_uid
    ):
        call = _RpcCall(local_id, call_uid, name, params, conn_info, send_response)
        self.send(rpc_uid, call)

    def postRpcResponse(self, local_id, call_uid, result):
        thr = self.m_owner
        response = thr.m_response_map.pop((local_id, call_uid), None)
        if response is None:
            logger.warning(
                "Posting RPC response to nonexistent call (or duplicate response)"
            )
            return False
        else:
            response(Message.rpcResponse(local_id, call_uid, result))
            return True

    def start(self):
        CallbackManager.start(self)

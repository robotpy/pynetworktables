# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

#
# These tests are adapted from ntcore's test suite
#

import threading


def test_Polled(nt_server, nt_client):
    nt_server_api = nt_server._api

    if nt_server.proto_rev == 0x0200 or nt_client.proto_rev == 0x0200:
        # this is annoying to test because of the reconnect
        return

    # set up the poller
    poller = nt_server_api.createConnectionListenerPoller()
    handle = nt_server_api.addPolledConnectionListener(poller, False)

    # trigger a connect event
    nt_server.start_test()
    nt_client.start_test()

    # get the event
    assert nt_server_api.waitForConnectionListenerQueue(1.0)

    result, timed_out = nt_server_api.pollConnectionListener(poller, 1.0)
    assert not timed_out
    assert len(result) == 1
    assert handle == result[0][0]
    assert result[0][1].connected
    del result[:]

    # trigger a disconnect event
    nt_client.shutdown()

    # get the event
    assert nt_server_api.waitForConnectionListenerQueue(1.0)

    result, timed_out = nt_server_api.pollConnectionListener(poller, 0.1)
    assert not timed_out
    assert len(result) == 1
    assert handle == result[0][0]
    assert not result[0][1].connected


def test_Threaded(nt_server, nt_client):
    nt_server_api = nt_server._api

    if nt_server.proto_rev == 0x0200 or nt_client.proto_rev == 0x0200:
        # this is annoying to test because of the reconnect
        return

    result_cond = threading.Condition()
    result = []

    def _server_cb(event):
        with result_cond:
            result.append(event)
            result_cond.notify()

    nt_server_api.addConnectionListener(_server_cb, False)

    # trigger a connect event
    nt_server.start_test()
    nt_client.start_test()

    with result_cond:
        result_cond.wait(0.5)

    # get the event
    assert len(result) == 1
    # assert handle == result[0].listener
    assert result[0].connected
    del result[:]

    # trigger a disconnect event
    nt_client.shutdown()

    with result_cond:
        result_cond.wait(0.5)

    # get the event
    assert len(result) == 1
    # assert handle == result[0].listener
    assert not result[0].connected

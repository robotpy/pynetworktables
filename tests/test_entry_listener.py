# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

#
# These tests are adapted from ntcore's test suite
#

import pytest

from threading import Condition

from _pynetworktables._impl.constants import NT_NOTIFY_LOCAL, NT_NOTIFY_NEW

from _pynetworktables._impl.value import Value


class SC(object):
    def __init__(self):
        self.events = []
        self.event_cond = Condition()

    def __call__(self, event):
        with self.event_cond:
            self.events.append(event)
            self.event_cond.notify()

    def wait(self, count):
        with self.event_cond:
            result = self.event_cond.wait_for(lambda: len(self.events) == count, 2)
            assert result, "expected %s events, got %s" % (count, len(self.events))
            return self.events[:]


@pytest.fixture
def server_cb():
    return SC()


def test_EntryNewLocal(nt_live, server_cb):
    nt_server, nt_client = nt_live
    nt_server_api = nt_server._api

    nt_server_api.addEntryListenerById(
        nt_server_api.getEntryId("/foo"), server_cb, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL
    )

    # Trigger an event
    nt_server_api.setEntryValueById(
        nt_server_api.getEntryId("/foo/bar"), Value.makeDouble(2.0)
    )
    nt_server_api.setEntryValueById(
        nt_server_api.getEntryId("/foo"), Value.makeDouble(1.0)
    )

    assert nt_server_api.waitForEntryListenerQueue(1.0)

    # Check the event
    events = server_cb.wait(1)

    # assert events[0].listener == handle
    assert events[0].local_id == nt_server_api.getEntryId("/foo")
    assert events[0].name == "/foo"
    assert events[0].value == Value.makeDouble(1.0)
    assert events[0].flags == NT_NOTIFY_NEW | NT_NOTIFY_LOCAL


def test_EntryNewRemote(nt_live, server_cb):
    nt_server, nt_client = nt_live
    nt_server_api = nt_server._api
    nt_client_api = nt_client._api

    nt_server_api.addEntryListenerById(
        nt_server_api.getEntryId("/foo"), server_cb, NT_NOTIFY_NEW
    )

    # Trigger an event
    nt_client_api.setEntryValueById(
        nt_client_api.getEntryId("/foo/bar"), Value.makeDouble(2.0)
    )
    nt_client_api.setEntryValueById(
        nt_client_api.getEntryId("/foo"), Value.makeDouble(1.0)
    )

    nt_client_api.flush()

    assert nt_server_api.waitForEntryListenerQueue(1.0)

    # Check the event
    events = server_cb.wait(1)

    # assert events[0].listener == handle
    assert events[0].local_id == nt_server_api.getEntryId("/foo")
    assert events[0].name == "/foo"
    assert events[0].value == Value.makeDouble(1.0)
    assert events[0].flags == NT_NOTIFY_NEW


def test_PrefixNewLocal(nt_live, server_cb):
    nt_server, nt_client = nt_live
    nt_server_api = nt_server._api

    nt_server_api.addEntryListener("/foo", server_cb, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)

    # Trigger an event
    nt_server_api.setEntryValueById(
        nt_server_api.getEntryId("/foo/bar"), Value.makeDouble(1.0)
    )
    nt_server_api.setEntryValueById(
        nt_server_api.getEntryId("/baz"), Value.makeDouble(1.0)
    )

    assert nt_server_api.waitForEntryListenerQueue(1.0)

    events = server_cb.wait(1)

    # assert events[0].listener == handle
    assert events[0].local_id == nt_server_api.getEntryId("/foo/bar")
    assert events[0].name == "/foo/bar"
    assert events[0].value == Value.makeDouble(1.0)
    assert events[0].flags == NT_NOTIFY_NEW | NT_NOTIFY_LOCAL


def test_PrefixNewRemote(nt_live, server_cb):
    nt_server, nt_client = nt_live
    nt_server_api = nt_server._api
    nt_client_api = nt_client._api

    nt_server_api.addEntryListener("/foo", server_cb, NT_NOTIFY_NEW | NT_NOTIFY_LOCAL)

    # Trigger an event
    nt_client_api.setEntryValueById(
        nt_client_api.getEntryId("/foo/bar"), Value.makeDouble(1.0)
    )
    nt_client_api.setEntryValueById(
        nt_client_api.getEntryId("/baz"), Value.makeDouble(1.0)
    )

    assert nt_server_api.waitForEntryListenerQueue(1.0)

    # Check the event
    events = server_cb.wait(1)

    # assert events[0].listener == handle
    assert events[0].local_id == nt_server_api.getEntryId("/foo/bar")
    assert events[0].name == "/foo/bar"
    assert events[0].value == Value.makeDouble(1.0)
    assert events[0].flags == NT_NOTIFY_NEW

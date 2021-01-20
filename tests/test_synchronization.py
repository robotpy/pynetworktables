#
# These tests stand up a separate client and server instance of
# networktables and tests the 'real' user API to ensure that it
# works correctly
#

from __future__ import print_function

import logging

logger = logging.getLogger("test")


#
# Distinction between the following test cases:
# -> instance.shutdown clears the storage for the nt instance
# -> instance.disconnect only shuts down the network connection, storage is retained
#

#
# Writes before connection
#


def test_sync_pre_client_writes_value(nt_server, nt_client):
    """
    Client writes value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | client foo=1     |
    | connected        | foo=1
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    ct.putString("foo", "1")

    with nt_server.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_pre_server_writes_value(nt_server, nt_client):
    """
    Server writes value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | server foo=1     |
    | connected        | foo=1
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    st.putString("foo", "1")

    with nt_client.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_pre_both_write_values(nt_server, nt_client):
    """
    Both write values

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | server foo=1     |
    | client foo=2     |
    | connected        | foo=2           | client wins
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    st.putString("foo", "1")
    ct.putString("foo", "2")

    with nt_server.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"


def test_sync_srestart_client_writes(nt_server, nt_client):
    """
    Server restart; Client wrote value locally

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | client foo=1     |
    | connected        | foo=1
    | server restart   |
    | connected        | foo=1
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    ct.putString("foo", "1")

    with nt_server.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_server.shutdown()

    st = nt_server.getTable("table")
    assert st.getString("foo", None) == None

    with nt_server.expect_changes(1):
        nt_server.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_srestart_server_writes(nt_server, nt_client):
    """
    Server restart; Server wrote value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | server foo=1     |
    | connected        | foo=1
    | server restart   |
    | connected        | foo deleted     | Not an intuitive result
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    st.putString("foo", "1")

    with nt_client.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_server.shutdown()

    st = nt_server.getTable("table")
    assert st.getString("foo", None) == None

    # Required otherwise we don't have anything to wait for...
    ct.putNumber("ignored", 1)

    with nt_server.expect_changes(1):
        nt_server.start_test()

    assert ct.getString("foo", None) == None
    assert st.getString("foo", None) == None


def test_sync_srestart_both_writes(nt_server, nt_client):
    """
    Server restart; Both write value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | server foo=2     | foo=2
    | server restart   |
    | connected        | foo=2
    """

    nt_server.start_test()
    nt_client.start_test()

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    with nt_client.expect_changes(1):
        st.putString("foo", "2")

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"

    nt_server.shutdown()

    st = nt_server.getTable("table")
    assert st.getString("foo", None) == None

    with nt_server.expect_changes(1):
        nt_server.start_test()

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"


def test_sync_crestart_client_writes(nt_server, nt_client):
    """
    Client restart

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | client foo=1     |
    | connected        | foo=1
    | client restart   |
    | connected        | foo=1
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    ct.putString("foo", "1")

    with nt_server.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.shutdown()
    ct = nt_client.getTable("table")

    assert ct.getString("foo", None) == None

    with nt_client.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_crestart_server_writes(nt_server, nt_client):
    """
    Client restart

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | server foo=1     |
    | connected        | foo=1
    | client restart   |
    | connected        | foo=1
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    st.putString("foo", "1")

    with nt_client.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.shutdown()
    ct = nt_client.getTable("table")

    assert ct.getString("foo", None) == None

    with nt_client.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_crestart_server_writes_late(nt_server, nt_client):
    """
    Client restart

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | server foo=1     |
    | connected        | foo=1
    | client restart   |
    | server foo=2     |
    | connected        | foo=2
    """

    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    st.putString("foo", "1")

    with nt_client.expect_changes(1):
        nt_server.start_test()
        nt_client.start_test()

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.shutdown()
    ct = nt_client.getTable("table")

    assert ct.getString("foo", None) == None
    st.putString("foo", "2")

    with nt_client.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"


def test_sync_disconnect_write_by_server(nt_server, nt_client):
    """
    Server update during disconnect - server initiated value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | server foo=1     | foo=1
    | disconnect
    | server foo=2
    | connected        | foo=2
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_client.expect_changes(1):
        st.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.disconnect()
    st.putString("foo", "2")

    with nt_client.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"


def test_sync_disconnect_write_by_client(nt_server, nt_client):
    """
    Server update during disconnect - client initiated value

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | disconnect
    | server foo=2
    | connected        | foo=1           | client wins
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.disconnect()
    st.putString("foo", "2")

    with nt_server.expect_changes(1):
        nt_client.start_test()

    # client wins
    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"


def test_sync_disconnect_write_by_client2(nt_server, nt_client):
    """
    Client update during disconnect

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | disconnect
    | client foo=2
    | connected        | foo=2
    | client foo=3     | foo=3
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.disconnect()
    ct.putString("foo", "2")

    with nt_server.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"

    with nt_server.expect_changes(1):
        ct.putString("foo", "3")

    # more writes succeed
    assert ct.getString("foo", None) == "3"
    assert st.getString("foo", None) == "3"


def test_sync_disconnect_write_by_both(nt_server, nt_client):
    """
    Both update during disconnect

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | disconnect
    | client foo=2
    | server foo=3
    | connected        | foo=2
    | client foo=4     | foo=4
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    nt_client.disconnect()
    ct.putString("foo", "2")
    st.putString("foo", "3")

    with nt_server.expect_changes(1):
        nt_client.start_test()

    # client wins
    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"

    with nt_server.expect_changes(1):
        ct.putString("foo", "4")

    # more writes succeed
    assert ct.getString("foo", None) == "4"
    assert st.getString("foo", None) == "4"


def test_sync_disconnect_write_by_both_prev(nt_server, nt_client):
    """
    Client and server updates during disconnect (both previously written)

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | server foo=2     | foo=2
    | disconnect
    | client foo=3
    | connected        | foo=3           | issue #270?
    | client foo=4     | foo=4
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    with nt_client.expect_changes(1):
        st.putString("foo", "2")

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"

    nt_client.disconnect()
    ct.putString("foo", "3")

    with nt_server.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "3"
    assert st.getString("foo", None) == "3"

    with nt_server.expect_changes(1):
        ct.putString("foo", "4")

    # more writes succeed
    assert ct.getString("foo", None) == "4"
    assert st.getString("foo", None) == "4"


def test_sync_disconnect_write_by_both_both_prev(nt_server, nt_client):
    """
    Client and server updates during disconnect (both previously written)

    | Action           | Global NT state | Notes
    | ---------------- | --------------- | -----
    | connected
    | client foo=1     | foo=1
    | server foo=2     | foo=2
    | disconnect
    | server foo=3
    | client foo=4
    | connected        | foo=4           | issue #270?
    | client foo=5     | foo=5
    """
    ct = nt_client.getTable("table")
    st = nt_server.getTable("table")

    nt_server.start_test()
    nt_client.start_test()

    with nt_server.expect_changes(1):
        ct.putString("foo", "1")

    assert ct.getString("foo", None) == "1"
    assert st.getString("foo", None) == "1"

    with nt_client.expect_changes(1):
        st.putString("foo", "2")

    assert ct.getString("foo", None) == "2"
    assert st.getString("foo", None) == "2"

    nt_client.disconnect()
    st.putString("foo", "3")
    ct.putString("foo", "4")

    with nt_server.expect_changes(1):
        nt_client.start_test()

    assert ct.getString("foo", None) == "4"
    assert st.getString("foo", None) == "4"

    with nt_server.expect_changes(1):
        ct.putString("foo", "5")

    # more writes succeed
    assert ct.getString("foo", None) == "5"
    assert st.getString("foo", None) == "5"

#
# Synchronization analysis scenarios
#

import pytest


@pytest.fixture
def scenario(nt_server, nt_client, nt_client2):
    st = nt_server.getTable("table")
    ct1 = nt_client.getTable("table")
    ct2 = nt_client2.getTable("table")

    nt_server.start_test()

    st.putString("ServerOnly", "0")

    ct1.putString("Client1Only", "1")
    ct1.putString("SC1Shared", "1")
    ct1.putString("ClientShared", "1")

    ct2.putString("Client2Only", "2")
    ct2.putString("SC2Shared", "2")

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(4):  # receives own updates
            nt_client.start_test()

    with nt_server.expect_changes(2):
        with nt_client2.expect_changes(6):  # receives own updates
            with nt_client.expect_changes(2):
                nt_client2.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=0,
        Client1Only=1,
        SC1Shared=1,
        ClientShared=1,
        Client2Only=2,
        SC2Shared=2,
    )

    return nt_server, nt_client, nt_client2, st, ct1, ct2


def check_results(st, ct1, ct2, **kwargs):
    for k, v in kwargs.items():
        if v is not None:
            v = str(v)
        assert st.getString(k, None) == v
        assert ct1.getString(k, None) == v
        assert ct2.getString(k, None) == v


def test_scenario_1(scenario):
    """
    Single client network drop (disconnect + reconnect)

    Client1 disconnects from Server
    Client1 updates Client1Only=11, SC1Shared=11, ClientShared=11
    Server updates ServerOnly=10, SC1Shared=10, SC2Shared=10
    Client2 updates Client2Only=12, SC2Shared=12, ClientShared=12
    Client1 reconnects to server
    """
    nt_server, nt_client, nt_client2, st, ct1, ct2 = scenario

    nt_client.disconnect()

    ct1.putString("Client1Only", "11")
    ct1.putString("SC1Shared", "11")
    ct1.putString("ClientShared", "11")

    with nt_client2.expect_changes(3):
        st.putString("ServerOnly", "10")
        st.putString("SC1Shared", "10")
        st.putString("SC2Shared", "10")

    with nt_server.expect_changes(3):
        ct2.putString("Client2Only", "12")
        ct2.putString("SC2Shared", "12")
        ct2.putString("ClientShared", "12")

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            with nt_client2.expect_changes(3):
                nt_client.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=10,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=11,
        SC2Shared=12,
        ClientShared=11,
    )


def test_scenario_2(scenario):
    """
    Server network drop (both clients disconnect + reconnect)

    Client1 disconnects from Server
    Client2 disconnects from Server
    Client1 updates Client1Only=11, SC1Shared=11, ClientShared=11
    Client2 updates Client2Only=12, SC2Shared=12, ClientShared=12
    Server updates ServerOnly=10, SC1Shared=10, SC2Shared=10
    Client1 reconnects to server
    Client2 reconnects to server
    """
    nt_server, nt_client, nt_client2, st, ct1, ct2 = scenario

    nt_client.disconnect()
    nt_client2.disconnect()

    ct1.putString("Client1Only", "11")
    ct1.putString("SC1Shared", "11")
    ct1.putString("ClientShared", "11")

    ct2.putString("Client2Only", "12")
    ct2.putString("SC2Shared", "12")
    ct2.putString("ClientShared", "12")

    st.putString("ServerOnly", "10")
    st.putString("SC1Shared", "10")
    st.putString("SC2Shared", "10")

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            nt_client.start_test()

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            with nt_client2.expect_changes(3):
                nt_client2.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=10,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=11,
        SC2Shared=12,
        ClientShared=12,
    )


def test_scenario_3(scenario):
    """
    Server reboot, reconnect before server-local code makes changes

    Server restarts (disconnecting both Client1 and Client2)
    Client1 updates Client1Only=11, SC1Shared=11, ClientShared=11
    Client2 updates Client2Only=12, SC2Shared=12, ClientShared=12
    Client1 reconnects to Server
    Client2 reconnects to Server
    Server updates ServerOnly=10, SC1Shared=10, SC2Shared=10
    """
    nt_server, nt_client, nt_client2, st, ct1, ct2 = scenario

    nt_server.shutdown()
    st = nt_server.getTable("table")

    ct1.putString("Client1Only", "11")
    ct1.putString("SC1Shared", "11")
    ct1.putString("ClientShared", "11")

    ct2.putString("Client2Only", "12")
    ct2.putString("SC2Shared", "12")
    ct2.putString("ClientShared", "12")

    # needed to assure reconnection order
    nt_client2.disconnect()

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(6):
            nt_server.start_test()

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            with nt_client2.expect_changes(5):
                nt_client2.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=None,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=11,
        SC2Shared=12,
        ClientShared=12,
    )

    with nt_client.expect_changes(3):
        with nt_client2.expect_changes(3):
            st.putString("ServerOnly", "10")
            st.putString("SC1Shared", "10")
            st.putString("SC2Shared", "10")

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=10,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=10,
        SC2Shared=10,
        ClientShared=12,
    )


def test_scenario_4(scenario):
    """
    Server reboot, reconnect after server-local code makes changes

    Server restarts (disconnecting both Client1 and Client2)
    Server updates ServerOnly=10, SC1Shared=10, SC2Shared=10
    Client1 updates Client1Only=11, SC1Shared=11, ClientShared=11
    Client2 updates Client2Only=12, SC2Shared=12, ClientShared=12
    Client1 reconnects to Server
    Client2 reconnects to Server
    """
    nt_server, nt_client, nt_client2, st, ct1, ct2 = scenario

    nt_server.shutdown()
    st = nt_server.getTable("table")

    st.putString("ServerOnly", "10")
    st.putString("SC1Shared", "10")
    st.putString("SC2Shared", "10")

    ct1.putString("Client1Only", "11")
    ct1.putString("SC1Shared", "11")
    ct1.putString("ClientShared", "11")

    ct2.putString("Client2Only", "12")
    ct2.putString("SC2Shared", "12")
    ct2.putString("ClientShared", "12")

    # needed to assure reconnection order
    nt_client2.disconnect()

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(5):
            nt_server.start_test()

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            with nt_client2.expect_changes(4):
                nt_client2.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=10,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=11,
        SC2Shared=12,
        ClientShared=12,
    )


def test_scenario_5(scenario):
    """
    Single client reboot

    Client1 restarts (disconnecting from Server)
    Client1 updates Client1Only=11, SC1Shared=11, ClientShared=11
    Server updates ServerOnly=10, SC1Shared=10, SC2Shared=10
    Client2 updates Client2Only=12, SC2Shared=12, ClientShared=12
    Client1 reconnects to Server
    """
    nt_server, nt_client, nt_client2, st, ct1, ct2 = scenario

    nt_client.shutdown()
    ct1 = nt_client.getTable("table")

    ct1.putString("Client1Only", "11")
    ct1.putString("SC1Shared", "11")
    ct1.putString("ClientShared", "11")

    with nt_client2.expect_changes(3):
        st.putString("ServerOnly", "10")
        st.putString("SC1Shared", "10")
        st.putString("SC2Shared", "10")

    with nt_server.expect_changes(3):
        ct2.putString("Client2Only", "12")
        ct2.putString("SC2Shared", "12")
        ct2.putString("ClientShared", "12")

    with nt_server.expect_changes(3):
        with nt_client.expect_changes(3):
            with nt_client2.expect_changes(3):
                nt_client.start_test()

    check_results(
        st,
        ct1,
        ct2,
        ServerOnly=10,
        Client1Only=11,
        Client2Only=12,
        SC1Shared=11,
        SC2Shared=12,
        ClientShared=11,
    )

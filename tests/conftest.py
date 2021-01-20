#
# Useful fixtures
#

from contextlib import contextmanager
from threading import Condition

log_datefmt = "%H:%M:%S"
log_format = "%(asctime)s:%(msecs)03d %(levelname)-8s: %(name)-8s: %(message)s"

import logging

logging.basicConfig(level=logging.DEBUG, format=log_format, datefmt=log_datefmt)


logger = logging.getLogger("conftest")

import pytest

from _pynetworktables import NetworkTables, NetworkTablesInstance

#
# Fixtures for a usable in-memory version of networktables
#


@pytest.fixture(scope="function", params=[True, False])
def verbose_logging(request):
    return request.param


@pytest.fixture(scope="function", params=[True, False])
def nt(request):
    """Starts/stops global networktables instance for testing"""
    NetworkTables.startTestMode(server=request.param)

    yield NetworkTables

    NetworkTables.shutdown()


@pytest.fixture(scope="function")
def entry_notifier(nt):
    return nt._api.entry_notifier


@pytest.fixture(scope="function")
def conn_notifier(nt):
    return nt._api.conn_notifier


@pytest.fixture(scope="function")
def nt_flush(nt):
    """Flushes NT key notifications"""

    def _flush():
        assert nt._api.waitForEntryListenerQueue(1.0)
        assert nt._api.waitForConnectionListenerQueue(1.0)

    return _flush


#
# Live NT instance fixtures
#


class NtTestBase(NetworkTablesInstance):
    """
    Object for managing a live pair of NT server/client
    """

    _wait_lock = None
    _testing_verbose_logging = True

    def shutdown(self):
        logger.info("shutting down %s", self.__class__.__name__)
        NetworkTablesInstance.shutdown(self)
        if self._wait_lock is not None:
            self._wait_init_listener()

    def disconnect(self):
        self._api.dispatcher.stop()

    def _init_common(self, proto_rev):
        # This resets the instance to be independent
        self.shutdown()
        self._api.dispatcher.setDefaultProtoRev(proto_rev)
        self.proto_rev = proto_rev

        if self._testing_verbose_logging:
            self.enableVerboseLogging()
        # self._wait_init()

    def _init_server(self, proto_rev, server_port=0):
        self._init_common(proto_rev)

        self.port = server_port

    def _init_client(self, proto_rev):
        self._init_common(proto_rev)

    def _wait_init(self):
        self._wait_lock = Condition()
        self._wait = 0
        self._wait_init_listener()

    def _wait_init_listener(self):
        self._api.addEntryListener(
            "",
            self._wait_cb,
            NetworkTablesInstance.NotifyFlags.NEW
            | NetworkTablesInstance.NotifyFlags.UPDATE
            | NetworkTablesInstance.NotifyFlags.DELETE
            | NetworkTablesInstance.NotifyFlags.FLAGS,
        )

    def _wait_cb(self, *args):
        with self._wait_lock:
            self._wait += 1
            # logger.info('Wait callback, got: %s', args)
            self._wait_lock.notify()

    @contextmanager
    def expect_changes(self, count):
        """Use this on the *other* instance that you're making
        changes on, to wait for the changes to propagate to the
        other instance"""

        if self._wait_lock is None:
            self._wait_init()

        with self._wait_lock:
            self._wait = 0

        logger.info("Begin actions")
        yield
        logger.info("Waiting for %s changes", count)

        with self._wait_lock:
            result, msg = (
                self._wait_lock.wait_for(lambda: self._wait == count, 4),
                "Timeout waiting for %s changes (got %s)" % (count, self._wait),
            )
            logger.info("expect_changes: %s %s", result, msg)
            assert result, msg


# Each test should cover each NT version combination
# 0x0200 -> 0x0300
# 0x0300 -> 0x0200
# 0x0300 -> 0x0300


@pytest.fixture(params=[0x0200, 0x0300])
def nt_server(request, verbose_logging):
    class NtServer(NtTestBase):

        _test_saved_port = None
        _testing_verbose_logging = verbose_logging

        def start_test(self):
            logger.info("NtServer::start_test")

            # Restore server port on restart
            if self._test_saved_port is not None:
                self.port = self._test_saved_port
                self._api.dispatcher.setDefaultProtoRev(request.param)

            if verbose_logging:
                self.enableVerboseLogging()

            self.startServer(listenAddress="127.0.0.1", port=self.port)

            assert self._api.dispatcher.m_server_acceptor.waitForStart(timeout=1)
            self.port = self._api.dispatcher.m_server_acceptor.m_port
            self._test_saved_port = self.port

    server = NtServer()
    server._init_server(request.param)
    yield server
    server.shutdown()


@pytest.fixture(params=[0x0200, 0x0300])
def nt_client(request, nt_server, verbose_logging):
    class NtClient(NtTestBase):

        _testing_verbose_logging = verbose_logging

        def start_test(self):
            if verbose_logging:
                self.enableVerboseLogging()
            self.setNetworkIdentity("C1")
            self._api.dispatcher.setDefaultProtoRev(request.param)
            self.startClient(("127.0.0.1", nt_server.port))

    client = NtClient()
    client._init_client(request.param)
    yield client
    client.shutdown()


@pytest.fixture(params=[0x0300])  # don't bother with other proto versions
def nt_client2(request, nt_server, verbose_logging):
    class NtClient(NtTestBase):

        _testing_verbose_logging = verbose_logging

        def start_test(self):
            if verbose_logging:
                self.enableVerboseLogging()
            self._api.dispatcher.setDefaultProtoRev(request.param)
            self.setNetworkIdentity("C2")
            self.startClient(("127.0.0.1", nt_server.port))

    client = NtClient()
    client._init_client(request.param)
    yield client
    client.shutdown()


@pytest.fixture
def nt_live(nt_server, nt_client):
    """This fixture automatically starts the client and server"""

    nt_server.start_test()
    nt_client.start_test()

    return nt_server, nt_client

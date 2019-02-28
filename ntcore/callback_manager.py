# validated: 2018-11-27 DS 18c8cce6a78d cpp/CallbackManager.h
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

from collections import deque, namedtuple
from threading import Condition
import time

try:
    # Python 3.7 only, should be more efficient
    from queue import SimpleQueue as Queue, Empty
except ImportError:
    from queue import Queue, Empty

from .support.safe_thread import SafeThread
from .support.uidvector import UidVector

import logging

logger = logging.getLogger("nt")

_ListenerData = namedtuple("ListenerData", ["callback", "poller_uid"])


class Poller(object):
    def __init__(self):
        # Note: this is really close to the python queue, but we really have to
        # mess with its internals to get the same semantics as WPILib, so we are
        # rolling our own :(
        self.poll_queue = deque()
        self.poll_cond = Condition()
        self.terminating = False
        self.cancelling = False

    def terminate(self):
        with self.poll_cond:
            self.terminating = True
            self.poll_cond.notify_all()


class CallbackThread(object):
    def __init__(self, name):
        # Don't need this in python, queue already has one
        # self.m_mutex = threading.Lock()

        self.m_listeners = UidVector()
        self.m_queue = Queue()
        self.m_pollers = UidVector()

        self.m_active = False
        self.name = name

    #
    # derived must implement the following
    #

    def matches(self, listener, data):
        raise NotImplementedError

    def setListener(self, data, listener_uid):
        raise NotImplementedError

    def doCallback(self, callback, data):
        raise NotImplementedError

    #
    # Impl
    #

    def start(self):
        self.m_active = True
        self._thread = SafeThread(target=self.main, name=self.name)

    def stop(self):
        self.m_active = False
        self.m_queue.put(None)

    def sendPoller(self, poller_uid, *args):
        # args are (listener_uid, item)
        poller = self.m_pollers.get(poller_uid)
        if poller:
            with poller.poll_cond:
                poller.poll_queue.append(args)
                poller.poll_cond.notify()

    def main(self):
        # micro-optimization: lift these out of the loop
        doCallback = self.doCallback
        matches = self.matches
        queue_get = self.m_queue.get
        setListener = self.setListener
        listeners_get = self.m_listeners.get
        listeners_items = self.m_listeners.items

        while True:
            item = queue_get()
            if not item:
                logger.debug("%s thread no longer active", self.name)
                break

            listener_uid, item = item
            if listener_uid is not None:
                listener = listeners_get(listener_uid)
                if listener and matches(listener, item):
                    setListener(item, listener_uid)
                    cb = listener.callback
                    if cb:
                        try:
                            doCallback(cb, item)
                        except Exception:
                            logger.warning(
                                "Unhandled exception processing %s callback",
                                self.name,
                                exc_info=True,
                            )
                    elif listener.poller_uid is not None:
                        self.sendPoller(listener.poller_uid, listener_uid, item)
            else:
                # Use copy because iterator might get invalidated
                for listener_uid, listener in list(listeners_items()):
                    if matches(listener, item):
                        setListener(item, listener_uid)
                        cb = listener.callback
                        if cb:
                            try:
                                doCallback(cb, item)
                            except Exception:
                                logger.warning(
                                    "Unhandled exception processing %s callback",
                                    self.name,
                                    exc_info=True,
                                )
                        elif listener.poller_uid is not None:
                            self.sendPoller(listener.poller_uid, listener_uid, item)

        # Wake any blocked pollers
        for poller in self.m_pollers.values():
            poller.terminate()


class CallbackManager(object):

    # Derived classes should declare this attribute at class level:
    # THREAD_CLASS = Something

    def __init__(self, verbose):
        self.m_verbose = verbose
        self.m_owner = None

    def setVerboseLogging(self, verbose):
        self.m_verbose = verbose

    def stop(self):
        if self.m_owner:
            self.m_owner.stop()

    def remove(self, listener_uid):
        thr = self.m_owner
        if thr:
            thr.m_listeners.pop(listener_uid, None)

    def createPoller(self):
        self.start()
        thr = self.m_owner
        return thr.m_pollers.add(Poller())

    def removePoller(self, poller_uid):
        thr = self.m_owner
        if not thr:
            return

        # Remove any listeners that are associated with this poller
        listeners = list(thr.m_listeners.items())
        for lid, listener in listeners:
            if listener.poller_uid == poller_uid:
                thr.m_listeners.pop(lid)

        # Wake up any blocked pollers
        poller = thr.m_pollers.pop(poller_uid, None)
        if not poller:
            return

        poller.terminate()

    def waitForQueue(self, timeout):
        thr = self.m_owner
        if not thr:
            return True

        # This function is intended for unit testing purposes only, so it's
        # not as efficient as it could be
        q = thr.m_queue

        if timeout is None:
            while not q.empty() and thr.m_active:
                time.sleep(0.005)
        else:
            wait_until = time.monotonic() + timeout
            while not q.empty() and thr.m_active:
                time.sleep(0.005)
                if time.monotonic() > wait_until:
                    return q.empty()

        return True

    def poll(self, poller_uid, timeout=None):
        # returns infos, timed_out
        # -> infos is a list of (listener_uid, item)
        infos = []
        timed_out = False

        thr = self.m_owner
        if not thr:
            return infos, timed_out

        poller = thr.m_pollers.get(poller_uid)
        if not poller:
            return infos, timed_out

        def _poll_fn():
            if poller.poll_queue:
                return 1
            if poller.cancelling:
                # Note: this only works if there's a single thread calling this
                # function for any particular poller, but that's the intended use.
                poller.cancelling = False
                return 2

        with poller.poll_cond:
            result = poller.poll_cond.wait_for(_poll_fn, timeout)
            if result is None:  # timeout
                timed_out = True
            elif result == 1:  # success
                infos.extend(poller.poll_queue)
                poller.poll_queue.clear()

        return infos, timed_out

    def cancelPoll(self, poller_uid):
        thr = self.m_owner.getThread()
        if not thr:
            return

        poller = thr.m_pollers.get(poller_uid)
        if not poller:
            return

        with poller.poll_cond:
            poller.cancelling = True
            poller.poll_cond.notify()

    # doStart in ntcore
    def start(self, *args):
        if not self.m_owner:
            self.m_owner = self.THREAD_CLASS(*args)
            self.m_owner.start()

    # Unlike ntcore, only a single argument is supported here. This is
    # to ensure that it's more clear what struct is being passed through

    def doAdd(self, item):
        self.start()
        thr = self.m_owner
        return thr.m_listeners.add(item)

    def send(self, only_listener, item):
        thr = self.m_owner
        if not thr or not thr.m_listeners:
            return

        thr.m_queue.put((only_listener, item))

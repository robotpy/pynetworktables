import threading

import logging

logger = logging.getLogger("nt.th")


class SafeThread(object):
    """
    Not exactly the same as wpiutil SafeThread... exists so we don't have
    to duplicate functionality in a lot of places
    """

    # Name each thread uniquely to make debugging easier
    _global_indices_lock = threading.Lock()
    _global_indices = {}

    def __init__(self, target, name, args=()):
        """
        Note: thread is automatically started and daemonized
        """

        with SafeThread._global_indices_lock:
            idx = SafeThread._global_indices.setdefault(name, -1) + 1
            SafeThread._global_indices[name] = idx
            name = "%s-%s" % (name, idx)

        self.name = name

        self._thread = threading.Thread(
            target=self._run, name=name, args=(target, args)
        )
        self._thread.daemon = True

        self.is_alive = self._thread.is_alive
        self.join = self._thread.join

        self._thread.start()

    def join(self, timeout=1):
        self._thread.join(timeout=timeout)
        if not self._thread.is_alive():
            logger.warning("Thread %s did not stop!", self.name)

    def _run(self, target, args):
        logger.debug("Started thread %s", self.name)
        try:
            target(*args)
        except Exception:
            logger.warning("Thread %s died unexpectedly", self.name, exc_info=True)
        else:
            logger.debug("Thread %s exited", self.name)

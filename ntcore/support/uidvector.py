# novalidate

import threading


class UidVector(dict):
    def __init__(self):
        self.idx = 0
        self.lock = threading.Lock()

    def add(self, item):
        """Only use this method to add to the UidVector"""
        with self.lock:
            idx = self.idx
            self.idx += 1

        self[idx] = item
        return idx

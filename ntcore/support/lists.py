# notrack

from collections import namedtuple

Pair = namedtuple("Pair", ["first", "second"])


def ensure_id_exists(lst, msg_id, default=None):
    if msg_id >= len(lst):
        lst += [default] * (msg_id - len(lst) + 1)

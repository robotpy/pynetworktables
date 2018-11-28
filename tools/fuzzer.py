#!/usr/bin/env python3
#
# A simplified fuzzer that can be used to try and discover errors in the
# NetworkTables implementation.
#
# DON'T USE THIS ON A ROBOT CONNECTED TO REAL THINGS! Not all NetworkTables
# implementations are robust, and may crash or malfunction when subjected
# to this fuzzer
#

#
# TODO: Do more evil things to tease out deadlock/other bugs
#

ip = "127.0.0.1"
port = 1735

import errno
import threading
import socket
import os
from random import choice, randint

import time


def random_bytes(n):
    return bytes(os.urandom(n))


def sendbytes(s, a):
    s.send(bytes(a))


# valid message types
message_types = [0x00, 0x01, 0x02, 0x03, 0x10, 0x11]

num_threads = 16


def fuzz_any():
    ret = [choice(message_types)]

    ret += os.urandom(128)
    return ret


def fuzz_singlebyte():
    ret = [choice(message_types)]
    return ret


def fuzz_assign():

    ret = [0x10]

    # string:
    # 2 bytes len
    # n bytes content

    l = randint(0, 255)
    ret += [0, l]

    ret += os.urandom(l)

    # byte of type id
    ret += [randint(0, 20)]

    # two bytes, entry id
    ret += [0, randint(0, 255)]

    # two bytes, sequence
    ret += [randint(0, 255), randint(0, 255)]

    # some value
    ret += [0, 0]

    return ret


def fuzz_update():

    ret = [0x11]

    # entry id
    ret += [0x00, randint(0, 10)]

    # data type
    ret += [randint(0, 5)]

    # data
    ret += os.urandom(128)
    return ret


def fuzz_gibberish():
    return os.urandom(128)


def fuzz_dumb():
    return [
        randint(0, 5),
        randint(0, 5),
        randint(0, 5),
        randint(0, 5),
        randint(0, 5),
        randint(0, 5),
        randint(0, 5),
    ]


fuzz_routines = [fuzz_assign, fuzz_singlebyte, fuzz_update, fuzz_gibberish, fuzz_dumb]


def fuzz_thread():

    i = 0

    while True:

        print("Iteration", i)
        i += 1

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)

        try:
            print("Opening socket")
            s.connect((ip, port))

            sendbytes(s, choice(fuzz_routines)())
            s.recv(1)

        except socket.timeout:
            print("Socket timed out, try again")

        except socket.error as e:
            if e.errno != errno.ECONNRESET:
                raise
        finally:
            print("Closing socket")
            s.close()


threads = [threading.Thread(target=fuzz_thread) for i in range(0, num_threads)]

for t in threads:
    t.start()

    time.sleep(0.2)

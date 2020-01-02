# validated: 2018-11-27 DS a2ecb1027a62 cpp/Storage_save.cpp
# ----------------------------------------------------------------------------
# Copyright (c) FIRST 2017. All Rights Reserved.
# Open Source Software - may be modified and shared by FRC teams. The code
# must be accompanied by the FIRST BSD license file in the root directory of
# the project.
# ----------------------------------------------------------------------------

import ast
import base64
import re
from configparser import RawConfigParser

from .constants import (
    NT_BOOLEAN,
    NT_DOUBLE,
    NT_STRING,
    NT_RAW,
    NT_BOOLEAN_ARRAY,
    NT_DOUBLE_ARRAY,
    NT_STRING_ARRAY,
)

import logging

logger = logging.getLogger("nt")


PERSISTENT_SECTION = "NetworkTables Storage 3.0"

_key_bool = re.compile('boolean "(.+)"')
_key_double = re.compile('double "(.+)"')
_key_string = re.compile('string "(.+)"')
_key_raw = re.compile('raw "(.+)"')
_key_bool_array = re.compile('array boolean "(.+)"')
_key_double_array = re.compile('array double "(.+)"')
_key_string_array = re.compile('array string "(.+)"')

_value_string = re.compile(r'"((?:\\.|[^"\\])*)",?')

# TODO: these escape functions almost certainly don't deal with unicode
#       correctly

# TODO: strictly speaking, this isn't 100% compatible with ntcore... but


def _unescape_string(s):
    # shortcut if no escapes present
    if "\\" not in s:
        return s

    # let python do the hard work
    return ast.literal_eval('"%s"' % s)


# This is mostly what we want... unicode strings won't work properly though
_table = {i: chr(i) if i >= 32 and i < 127 else "\\x%02x" % i for i in range(256)}
_table[ord('"')] = '\\"'
_table[ord("\\")] = "\\\\"
_table[ord("\n")] = "\\n"
_table[ord("\t")] = "\\t"
_table[ord("\r")] = "\\r"


def _escape_string(s):
    return s.translate(_table)


def save_entries(fp, entries):

    parser = RawConfigParser()
    parser.optionxform = str
    parser.add_section(PERSISTENT_SECTION)

    for name, value in entries:
        if not value:
            continue

        t = value.type
        v = value.value

        if t == NT_BOOLEAN:
            name = 'boolean "%s"' % _escape_string(name)
            vrepr = "true" if v else "false"
        elif t == NT_DOUBLE:
            name = 'double "%s"' % _escape_string(name)
            vrepr = str(v)
        elif t == NT_STRING:
            name = 'string "%s"' % _escape_string(name)
            vrepr = '"%s"' % _escape_string(v)
        elif t == NT_RAW:
            name = 'raw "%s"' % _escape_string(name)
            vrepr = base64.b64encode(v).decode("ascii")
        elif t == NT_BOOLEAN_ARRAY:
            name = 'array boolean "%s"' % _escape_string(name)
            vrepr = ",".join(["true" if vv else "false" for vv in v])
        elif t == NT_DOUBLE_ARRAY:
            name = 'array double "%s"' % _escape_string(name)
            vrepr = ",".join([str(vv) for vv in v])
        elif t == NT_STRING_ARRAY:
            name = 'array string "%s"' % _escape_string(name)
            vrepr = '","'.join([_escape_string(vv) for vv in v])
            if vrepr:
                vrepr = '"%s"' % vrepr
        else:
            continue

        parser.set(PERSISTENT_SECTION, name, vrepr)

    parser.write(fp, space_around_delimiters=False)

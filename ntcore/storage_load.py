# validated: 2019-02-26 DS 0e1f9c2ed271 cpp/Storage_load.cpp

import ast
import binascii
import base64
import re
from configparser import RawConfigParser, NoSectionError

from .value import Value

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


def load_entries(fp, filename, prefix):

    entries = []

    parser = RawConfigParser()
    parser.optionxform = str

    try:
        if hasattr(parser, "read_file"):
            parser.read_file(fp, filename)
        else:
            parser.readfp(fp, filename)
    except IOError:
        raise
    except Exception as e:
        raise IOError("Error reading persistent file: %s" % e)

    try:
        items = parser.items(PERSISTENT_SECTION)
    except NoSectionError:
        raise IOError("Persistent section not found")

    value = None
    m = None

    for k, v in items:

        # Reduces code duplication
        if value:
            key = _unescape_string(m.group(1))
            if key.startswith(prefix):
                entries.append((key, value))

        value = None

        m = _key_bool.match(k)
        if m:
            if v == "true":
                value = Value.makeBoolean(True)
            elif v == "false":
                value = Value.makeBoolean(False)
            else:
                logger.warning("Unrecognized boolean value %r for %s", v, m.group(1))
            continue

        m = _key_double.match(k)
        if m:
            try:
                value = Value.makeDouble(float(v))
            except ValueError as e:
                logger.warning("Unrecognized double value %r for %s", v, m.group(1))

            continue

        m = _key_string.match(k)
        if m:
            mm = _value_string.match(v)

            if mm:
                value = Value.makeString(_unescape_string(mm.group(1)))
            else:
                logger.warning("Unrecognized string value %r for %s", v, m.group(1))
            continue

        m = _key_raw.match(k)
        if m:
            try:
                v = base64.b64decode(v, validate=True)
                value = Value.makeRaw(v)
            except binascii.Error:
                logger.warning("Unrecognized raw value %r for %s", v, m.group(1))
            continue

        m = _key_bool_array.match(k)
        if m:
            bools = []
            arr = v.strip().split(",")
            if arr != [""]:
                for vv in arr:
                    vv = vv.strip()
                    if vv == "true":
                        bools.append(True)
                    elif vv == "false":
                        bools.append(False)
                    else:
                        logger.warning(
                            "Unrecognized bool '%s' in bool array %s'", vv, m.group(1)
                        )
                        bools = None
                        break

            if bools is not None:
                value = Value.makeBooleanArray(bools)
            continue

        m = _key_double_array.match(k)
        if m:
            doubles = []
            arr = v.strip().split(",")
            if arr != [""]:
                for vv in arr:
                    try:
                        doubles.append(float(vv))
                    except ValueError:
                        logger.warning(
                            "Unrecognized double '%s' in double array %s",
                            vv,
                            m.group(1),
                        )
                        doubles = None
                        break

            value = Value.makeDoubleArray(doubles)
            continue

        m = _key_string_array.match(k)
        if m:
            # Technically, this will let invalid inputs in... but,
            # I don't really care. Feel free to fix it if you do.
            strings = [_unescape_string(vv) for vv in _value_string.findall(v)]
            value = Value.makeStringArray(strings)
            continue

        logger.warning("Unrecognized type '%s'", k)

    if value:
        key = _unescape_string(m.group(1))
        if key.startswith(prefix):
            entries.append((key, value))

    return entries

# validated: 2016-10-27 DS a7eca7d src/Storage.cpp src/Storage.h
'''
    This tries to stay compatible with ntcore's persistence mechanism,
    but if you go outside the realm of normal operations it may differ.
'''

import ast
import binascii
import base64
import re

from .constants import *
from .value import Value

from .support.compat import RawConfigParser, NoSectionError, PY2

import logging
logger = logging.getLogger('nt')


PERSISTENT_SECTION = 'NetworkTables Storage 3.0'

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
    if '\\' not in s:
        return s
    
    # let python do the hard work
    return ast.literal_eval('"%s"' % s)

# This is mostly what we want... unicode strings won't work properly though
_table = {i: chr(i) if i >= 32 and i < 127 else '\\x%02x' % i for i in range(256)}
_table[ord('"')] = '\\"'
_table[ord('\\')] = '\\\\'
_table[ord('\n')] = '\\n'
_table[ord('\t')] = '\\t'
_table[ord('\r')] = '\\r'

if PY2:
    _table = dict(map(lambda v: (v[0], unicode(v[1])), _table.items()))
    def _escape_string(s):
        return unicode(s).translate(_table)
else:
    def _escape_string(s):
        return s.translate(_table)

def load_entries(fp, filename):
    
    entries = []
    
    parser = RawConfigParser()
    parser.optionxform = str
    
    try:
        if hasattr(parser, 'read_file'):
            parser.read_file(fp, filename)
        else:
            parser.readfp(fp, filename)
    except IOError:
        raise
    except Exception as e:
        raise IOError('Error reading persistent file: %s' % e)
    
    try:
        items = parser.items(PERSISTENT_SECTION)
    except NoSectionError:
        raise IOError("Persistent section not found")

    value = None
    m = None
    
    for k, v in items:
        
        # Reduces code duplication
        if value:
            entries.append((_unescape_string(m.group(1)), value))
            
        value = None
        
        m = _key_bool.match(k)
        if m:
            if v == 'true':
                value = Value.makeBoolean(True)
            elif v == 'false':
                value = Value.makeBoolean(False)
            else:
                logger.warn("Unrecognized boolean value %r for %s", v, m.group(1))
            continue
        
        m = _key_double.match(k)
        if m:
            try:
                value = Value.makeDouble(float(v))
            except ValueError as e:
                logger.warn("Unrecognized double value %r for %s", v, m.group(1))
                
            continue
        
        m = _key_string.match(k)
        if m:
            mm = _value_string.match(v)
            
            if mm:
                value = Value.makeString(_unescape_string(mm.group(1)))
            elif PY2 and v == '':
                value = Value.makeString('')
            else:
                logger.warn("Unrecognized string value %r for %s", v, m.group(1))
            continue
        
        m = _key_raw.match(k)
        if m:
            try:
                if PY2:
                    v = base64.b64decode(v)
                else:
                    v = base64.b64decode(v, validate=True)
                value = Value.makeRaw(v)
            except binascii.Error:
                logger.warn("Unrecognized raw value %r for %s", v, m.group(1))
            continue
        
        m = _key_bool_array.match(k)
        if m:
            bools = []
            arr = v.strip().split(',')
            if arr != ['']:
                for vv in arr:
                    vv = vv.strip()
                    if vv == 'true':
                        bools.append(True)
                    elif vv == 'false':
                        bools.append(False)
                    else:
                        logger.warn("Unrecognized bool '%s' in bool array %s'", vv, m.group(1))
                        bools = None
                        break
                
            if bools is not None:
                value = Value.makeBooleanArray(bools)    
            continue
        
        m = _key_double_array.match(k)
        if m:
            doubles = []
            arr = v.strip().split(',')
            if arr != ['']:
                for vv in arr:
                    try:
                        doubles.append(float(vv))
                    except ValueError:
                        logger.warn("Unrecognized double '%s' in double array %s", vv, m.group(1))
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
        
        logger.warn("Unrecognized type '%s'", k)
        
    if value:
        entries.append((_unescape_string(m.group(1)), value))
    
    return entries


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
            vrepr = 'true' if v else 'false'
        elif t == NT_DOUBLE:
            name = 'double "%s"' % _escape_string(name)
            vrepr = str(v)
        elif t == NT_STRING:
            name = 'string "%s"' % _escape_string(name)
            vrepr = '"%s"' % _escape_string(v)
        elif t == NT_RAW:
            name = 'raw "%s"' % _escape_string(name)
            vrepr = base64.b64encode(v).decode('ascii')
        elif t == NT_BOOLEAN_ARRAY:
            name = 'array boolean "%s"' % _escape_string(name)
            vrepr = ','.join(['true' if vv else 'false' for vv in v])
        elif t == NT_DOUBLE_ARRAY:
            name = 'array double "%s"' % _escape_string(name)
            vrepr = ','.join([str(vv) for vv in v])
        elif t == NT_STRING_ARRAY:
            name = 'array string "%s"' % _escape_string(name)
            vrepr = '","'.join([_escape_string(vv) for vv in v])
            if vrepr:
                vrepr = '"%s"' % vrepr
        else:
            continue
        
        parser.set(PERSISTENT_SECTION, name, vrepr)
    
    if PY2:
        parser.write(fp)
    else:
        parser.write(fp, space_around_delimiters=False)    

# novalidate
# fmt: off

# data types
NT_UNASSIGNED =     b'\x00'
NT_BOOLEAN =        b'\x01'
NT_DOUBLE =         b'\x02'
NT_STRING =         b'\x04'
NT_RAW =            b'\x08'
NT_BOOLEAN_ARRAY =  b'\x10'
NT_DOUBLE_ARRAY =   b'\x20'
NT_STRING_ARRAY =   b'\x40'
NT_RPC =            b'\x80'

# Raw types transmitted on the wire
NT_VTYPE2RAW = {
    NT_BOOLEAN:       b'\x00',
    NT_DOUBLE:        b'\x01',
    NT_STRING:        b'\x02',
    NT_RAW:           b'\x03',
    NT_BOOLEAN_ARRAY: b'\x10',
    NT_DOUBLE_ARRAY:  b'\x11',
    NT_STRING_ARRAY:  b'\x12',
    NT_RPC:           b'\x20',
}

NT_RAW2VTYPE = {v: k for k, v in NT_VTYPE2RAW.items()}



# NetworkTables notifier kinds.
NT_NOTIFY_NONE =        0x00
NT_NOTIFY_IMMEDIATE =   0x01 # initial listener addition
NT_NOTIFY_LOCAL =       0x02 # changed locally
NT_NOTIFY_NEW =         0x04 # newly created entry
NT_NOTIFY_DELETE =      0x08 # deleted
NT_NOTIFY_UPDATE =      0x10 # value changed
NT_NOTIFY_FLAGS =       0x20 # flags changed

# Client/server modes
NT_NET_MODE_NONE = 0x00      # not running
NT_NET_MODE_SERVER = 0x01    # running in server mode
NT_NET_MODE_CLIENT = 0x02    # running in client mode
NT_NET_MODE_STARTING = 0x04  # flag for starting (either client or server)
NT_NET_MODE_FAILURE = 0x08   # flag for failure (either client or server)
NT_NET_MODE_TEST = 0x10      # flag indicating test mode (either client or server)

# NetworkTables entry flags
NT_PERSISTENT = 0x01


# Message types
kKeepAlive =        b'\x00'
kClientHello =      b'\x01'
kProtoUnsup =       b'\x02'
kServerHelloDone =  b'\x03'
kServerHello =      b'\x04'
kClientHelloDone =  b'\x05'
kEntryAssign =      b'\x10'
kEntryUpdate =      b'\x11'
kFlagsUpdate =      b'\x12'
kEntryDelete =      b'\x13'
kClearEntries =     b'\x14'
kExecuteRpc =       b'\x20'
kRpcResponse =      b'\x21'

kClearAllMagic =    0xD06CB27A

_msgtypes = {
    kKeepAlive:       'kKeepAlive',
    kClientHello:     'kClientHello',
    kProtoUnsup:      'kProtoUnsup',
    kServerHelloDone: 'kServerHelloDone',
    kServerHello:     'kServerHello',
    kClientHelloDone: 'kClientHelloDone',
    kEntryAssign:     'kEntryAssign',
    kEntryUpdate:     'kEntryUpdate',
    kFlagsUpdate:     'kFlagsUpdate',
    kEntryDelete:     'kEntryDelete',
    kClearEntries:    'kClearEntries',
    kExecuteRpc:      'kExecuteRpc',
    kRpcResponse:     'kRpcResponse',
}

def msgtype_str(msgtype):
    return _msgtypes.get(msgtype, 'Unknown (%s)' % msgtype)

# The default port that network tables operates on
NT_DEFAULT_PORT = 1735

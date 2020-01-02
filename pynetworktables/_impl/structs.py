# novalidate
# fmt: off

from collections import namedtuple

#: NetworkTables Entry Information
EntryInfo = namedtuple('EntryInfo', [
    # Entry name
    'name',

    # Entry type
    'type',

    # Entry flags
    'flags',

    # Timestamp of last change to entry (type or value).
    #'last_change',
])


#: NetworkTables Connection Information
ConnectionInfo = namedtuple('ConnectionInfo', [
    'remote_id',
    'remote_ip',
    'remote_port',
    'last_update',
    'protocol_version',
])


#: NetworkTables RPC Parameter Definition
RpcParamDef = namedtuple('RpcParamDef', [
    'name',
    'def_value',
])

#: NetworkTables RPC Result Definition
RpcResultDef = namedtuple('RpcResultDef', [
    'name',
    'type',
])

#: NetworkTables RPC Definition
RpcDefinition = namedtuple('RpcDefinition', [
    'version',
    'name',
    'params',
    'results',
])


#: NetworkTables RPC Call Data
RpcCallInfo = namedtuple('RpcCallInfo', [
    'rpc_id',
    'call_uid',
    'name',
    'params',
])

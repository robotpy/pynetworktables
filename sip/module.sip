
%Module pynetworktables

%DefaultEncoding "UTF-8"


typedef signed char INT8 /PyInt/;
typedef short INT16;
typedef int INT32;
typedef long long INT64;

typedef unsigned char UINT8 /PyInt/;
typedef unsigned short UINT16;
typedef unsigned int UINT32;
typedef unsigned long long UINT64;

//typedef struct semaphore * SEM_ID;

%Include stdstring.sip
%Include sip/SensorBase.sip

%ModuleHeaderCode
    #if WIN32
        #include <Windows.h>
    #endif
%End

%InitialisationCode
    #if WIN32
        WSADATA data;
        WSAStartup(0x0202, &data);
    #endif
%End


%Include tables/TableKeyNotDefinedException.sip
%Include networktables2/connection/BadMessageException.sip
%Include networktables2/util/IOException.sip
%Include networktables2/util/EOFException.sip
%Include networktables2/util/IllegalStateException.sip
%Include networktables2/TableKeyExistsWithDifferentTypeException.sip

//%Include LiveWindow/LiveWindow.sip
//%Include LiveWindow/LiveWindowSendable.sip
//%Include LiveWindow/LiveWindowStatusListener.sip
%Include networktables/NetworkTable.sip
%Include networktables/NetworkTableConnectionListenerAdapter.sip
%Include networktables/NetworkTableKeyListenerAdapter.sip
%Include networktables/NetworkTableListenerAdapter.sip
%Include networktables/NetworkTableMode.sip
%Include networktables/NetworkTableProvider.sip
%Include networktables/NetworkTableSubListenerAdapter.sip
%Include networktables2/client/ClientConnectionAdapter.sip
%Include networktables2/client/ClientConnectionListenerManager.sip
%Include networktables2/client/ClientConnectionState.sip
%Include networktables2/client/ClientNetworkTableEntryStore.sip
%Include networktables2/client/NetworkTableClient.sip
%Include networktables2/connection/ConnectionAdapter.sip
%Include networktables2/connection/ConnectionMonitorThread.sip
%Include networktables2/connection/DataIOStream.sip
%Include networktables2/connection/NetworkTableConnection.sip
%Include networktables2/server/NetworkTableServer.sip
%Include networktables2/server/ServerAdapterManager.sip
%Include networktables2/server/ServerConnectionAdapter.sip
%Include networktables2/server/ServerConnectionList.sip
%Include networktables2/server/ServerConnectionState.sip
%Include networktables2/server/ServerIncomingConnectionListener.sip
%Include networktables2/server/ServerIncomingStreamMonitor.sip
%Include networktables2/server/ServerNetworkTableEntryStore.sip
%Include networktables2/stream/FDIOStream.sip
%Include networktables2/stream/IOStream.sip
%Include networktables2/stream/IOStreamFactory.sip
%Include networktables2/stream/IOStreamProvider.sip
%Include networktables2/stream/SocketServerStreamProvider.sip
%Include networktables2/stream/SocketStreamFactory.sip
%Include networktables2/stream/SocketStreams.sip
%Include networktables2/thread/DefaultThreadManager.sip
%Include networktables2/thread/NTThread.sip
%Include networktables2/thread/NTThreadManager.sip
%Include networktables2/thread/PeriodicRunnable.sip
%Include networktables2/type/ArrayData.sip
%Include networktables2/type/ArrayEntryType.sip
%Include networktables2/type/BooleanArray.sip
%Include networktables2/type/ComplexData.sip
%Include networktables2/type/ComplexEntryType.sip
%Include networktables2/type/NetworkTableEntryType.sip
%Include networktables2/type/NetworkTableEntryTypeManager.sip
%Include networktables2/type/NumberArray.sip
%Include networktables2/type/StringArray.sip
%Include networktables2/util/StringCache.sip
%Include networktables2/AbstractNetworkTableEntryStore.sip
%Include networktables2/FlushableOutgoingEntryReceiver.sip
%Include networktables2/IncomingEntryReceiver.sip
%Include networktables2/NetworkTableEntry.sip
%Include networktables2/NetworkTableMessageType.sip
%Include networktables2/NetworkTableNode.sip
%Include networktables2/OutgoingEntryReceiver.sip
%Include networktables2/TransactionDirtier.sip
%Include networktables2/WriteManager.sip
%Include SmartDashboard/NamedSendable.sip
%Include SmartDashboard/Sendable.sip
%Include SmartDashboard/SendableChooser.sip
%Include SmartDashboard/SmartDashboard.sip
%Include tables/IRemote.sip
%Include tables/IRemoteConnectionListener.sip
%Include tables/ITable.sip
%Include tables/ITableListener.sip
%Include tables/ITableProvider.sip


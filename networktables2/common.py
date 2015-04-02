# Common classes for client and server

import threading
import time
import warnings

from . import _impl
from .entry import NetworkTableEntry

__all__ = ["AbstractNetworkTableEntryStore", "WriteManager"]

class AbstractNetworkTableEntryStore:
    """An entry store that handles storing entries and applying transactions
    """

    def __init__(self, listenerManager):
        self.idEntries = {}
        self.namedEntries = {}
        self.listenerManager = listenerManager
        self.outgoingReceiver = None
        self.incomingReceiver = None
        self.entry_lock = _impl.create_rlock('entry_lock')

    def getEntry(self, name_id):
        """Get an entry based on its name or id
        :param name_id: the name or id of the entry to look for
        :returns: the entry or None if the entry does not exist
        """
        with self.entry_lock:
            if isinstance(name_id, str):
                return self.namedEntries.get(name_id)
            else:
                return self.idEntries.get(name_id)

    def keys(self):
        """Get the list of keys.
        :returns: the list of keys
        """
        with self.entry_lock:
            return [k for k in self.namedEntries.keys()]

    def clearEntries(self):
        """Remove all entries.
        NOTE: This method should not be used with applications which cache
        entries which would lead to unknown results.
        This method is for use in testing only.
        """
        with self.entry_lock:
            self.idEntries.clear()
            self.namedEntries.clear()

    def clearIds(self):
        """clear the id's of all entries
        """
        with self.entry_lock:
            self.idEntries.clear()
            for entry in self.namedEntries.values():
                entry.clearId()

    def setOutgoingReceiver(self, receiver):
        self.outgoingReceiver = receiver

    def setIncomingReceiver(self, receiver):
        self.incomingReceiver = receiver

    def addEntry(self, entry):
        raise NotImplementedError

    def updateEntry(self, entry, sequenceNumber, value):
        raise NotImplementedError

    def putOutgoing(self, name, type, value):
        """Stores the given value under the given name and queues it for
        transmission to the remote end.

        :param name: The name under which to store the given value.
        :param type: The type of the given value.
        :param value: The value to store.
        
        If the type is different than that which is stored, it will be
        changed.
        """
        with self.entry_lock:
            tableEntry = self.namedEntries.get(name)
            if tableEntry is None:
                if hasattr(type, 'internalizeValue'):
                    value = type.internalizeValue(name, value, None)
                
                #TODO validate type
                tableEntry = NetworkTableEntry(name, type, value)
                if self.addEntry(tableEntry):
                    tableEntry.fireListener(self.listenerManager)
                    if self.outgoingReceiver is not None:
                        self.outgoingReceiver.offerOutgoingAssignment(tableEntry)
            else:
                # Note: NetworkTables only allows the type to change on a new
                #       assignment, and existing server implementations ignore
                #       assignment if the entry already exists. This means we 
                #       have to raise an error here, instead of changing the type
                if tableEntry.getType().id != type.id:
                    raise TypeError("Cannot put %s '%s', existing value in table is a %s" % (
                                     tableEntry.getType().name, tableEntry.name,
                                     type.name))
                currentValue = tableEntry.getValue() 
                if value != currentValue:
                    
                    if hasattr(type, 'internalizeValue'):
                        value = type.internalizeValue(name, value, currentValue)
                    
                    if self.updateEntry(tableEntry, tableEntry.getSequenceNumber()+1, value):
                        if self.outgoingReceiver is not None:
                            self.outgoingReceiver.offerOutgoingUpdate(tableEntry)
                    tableEntry.fireListener(self.listenerManager)

    def offerIncomingAssignment(self, entry):
        '''Called when a remote NT wants to assign a value to our table'''
        with self.entry_lock:
            tableEntry = self.namedEntries.get(entry.name)
            if self.addEntry(entry):
                if tableEntry is None:
                    tableEntry = entry
                tableEntry.fireListener(self.listenerManager)
                if self.incomingReceiver is not None:
                    self.incomingReceiver.offerOutgoingAssignment(tableEntry)

    def offerIncomingUpdate(self, entry, sequenceNumber, value):
        '''Called when a remote NT wants to update a value in our table'''
        with self.entry_lock:
            if self.updateEntry(entry, sequenceNumber, value):
                entry.fireListener(self.listenerManager)
                if self.incomingReceiver is not None:
                    self.incomingReceiver.offerOutgoingUpdate(entry)

    def notifyEntries(self, table, listener):
        """Called to say that a listener should notify the listener manager
        of all of the entries
        :param listener:
        :param table:
        """
        with self.entry_lock:
            for entry in self.namedEntries.values():
                listener.valueChanged(table, entry.name, entry.getValue(), True)

class WriteManager:
    """A write manager is a IncomingEntryReceiver that buffers transactions
    and then dispatches them to a flushable transaction receiver that is
    periodically offered all queued transaction and then flushed
    """
    SLEEP_TIME = 0.050
    
    queueSize = 500

    def __init__(self, receiver, entryStore, keepAliveDelay):
        """Create a new Write manager
        :param receiver:
        :type receiver: :class:`.ServerConnectionList`, :class:`.ClientConnectionAdapter`
        :param entryStore:
        """
        self.receiver = receiver
        self.entryStore = entryStore
        self.keepAliveDelay = keepAliveDelay
        self.lastWrite = 0

        self.transactionsLock = _impl.create_rlock('trans_lock')
        self.transactionsCondition = threading.Condition(self.transactionsLock)

        self.incomingAssignmentQueue = []
        self.incomingUpdateQueue = []
        self.outgoingAssignmentQueue = []
        self.outgoingUpdateQueue = []

        self.thread = None
        self.running = False

    def start(self):
        """start the write thread
        """
        if self.thread is not None:
            self.stop()
        self.lastWrite = time.time()
        self.running = True
        self.thread = threading.Thread(target=self.run,
                                       name="Write Manager Thread")
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """stop the write thread
        """
        if self.thread is not None:
            self.running = False
            with self.transactionsCondition:
                self.transactionsCondition.notify()
            self.thread.join()

    def offerOutgoingAssignment(self, entry):
        # This is always called with the entry lock held
        
        # Mark entry as dirty to avoid duplicate updates
        if entry.isDirty:
            return
        entry.makeDirty()

        with self.transactionsLock:
            self.incomingAssignmentQueue.append(entry)
            if len(self.incomingAssignmentQueue) >= self.queueSize:
                warnings.warn("assignment queue overflowed. decrease the rate at which you create new entries or increase the write buffer size", ResourceWarning)
                self.transactionsCondition.notify()

    def offerOutgoingUpdate(self, entry):
        # This is always called with the entry lock held
        
        # Mark entry as dirty to avoid duplicate updates
        if entry.isDirty:
            return
        entry.makeDirty()

        with self.transactionsLock:
            self.incomingUpdateQueue.append(entry)
            if len(self.incomingUpdateQueue) >= self.queueSize:
                warnings.warn("update queue overflowed. decrease the rate at which you update entries or increase the write buffer size", ResourceWarning)
                self.transactionsCondition.notify()

    def run(self):
        """the periodic method that sends all buffered transactions
        """
        while self.running:
            
            with self.transactionsLock:
                
                self.transactionsCondition.wait(self.SLEEP_TIME)
                
                if not self.running:
                    break
                
                #swap the assignment and update queue
                self.incomingAssignmentQueue, self.outgoingAssignmentQueue = \
                    self.outgoingAssignmentQueue, self.incomingAssignmentQueue
    
                self.incomingUpdateQueue, self.outgoingUpdateQueue = \
                    self.outgoingUpdateQueue, self.incomingUpdateQueue
            
            # Decision: Choose to lock/unlock the entry lock quickly, instead
            #           of one big lock. This allows the main thread to not
            #           be interrupted for an extended period of time
            
            transactions = []
    
            for entry in self.outgoingAssignmentQueue:
                with self.entryStore.entry_lock:
                    entry.makeClean()
                    transactions.append(entry.getAssignmentBytes())
                    
            for entry in self.outgoingUpdateQueue:
                with self.entryStore.entry_lock:
                    entry.makeClean()
                    transactions.append(entry.getUpdateBytes())
                
            del self.outgoingAssignmentQueue[:]
            del self.outgoingUpdateQueue[:]
    
            for entry in transactions:
                self.receiver.sendEntry(entry)
    
            if len(transactions) > 0:
                self.receiver.flush()
                self.lastWrite = time.time()
            elif (self.keepAliveDelay is not None and
                  (time.time()-self.lastWrite) > self.keepAliveDelay):
                self.receiver.ensureAlive()
                self.lastWrite = time.time()

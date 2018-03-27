
from os.path import exists

class StreamWrapper(object):
    '''
        Intended for debugging NT protocol issues
    '''
    
    def __init__(self, wrapped, fname):
        self.data = bytearray()
        self.wrapped = wrapped
        self.fname = fname
        
    def read(self, size):
        data = self.wrapped.read(size)
        self.data.extend(data)
        return data
    
    def write(self, contents):
        self.wrapped.write(contents)
        
    def flush(self):
        self.wrapped.flush()
        
    def writeToFile(self):
        if not exists(self.fname):
            with open(self.fname, 'wb') as fp:
                fp.write(self.data)

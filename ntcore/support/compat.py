# notrack

import os
import sys

try:
    from configparser import RawConfigParser, NoSectionError
except ImportError:
    from ConfigParser import RawConfigParser, NoSectionError

try:
    from time import monotonic
except ImportError:
    from monotonic import monotonic

if sys.version_info[0] <= 2:
    range = xrange
    basestring = basestring
    unicode = unicode
    PY2 = True
else:
    range = range
    basestring = str
    unicode = str
    PY2 = False
    
#
# For information about atomic writes, see
# -> http://stupidpythonideas.blogspot.com/2014/07/getting-atomic-writes-right.html
#
# Basically, if you're using Python 3.3+, good to go. Otherwise
# we'll try our best, but no guarantees.
#

if hasattr(os, 'replace'):      # Python 3.3+
    file_replace = os.replace
elif os.name != 'nt':           # Not Windows
    file_replace = os.rename
else:                           # Windows
    def file_replace(src, dst):
        try:
            os.unlink(dst)
        except FileNotFoundError:
            pass
        os.rename(src, dst)

#
# Polyfill for Condition.wait_for()
#
# Copied from Python 3.5 source code, Python license
#


if not PY2: # technically, 3.2... but we don't support 3.2
    from queue import Queue, Empty
    from threading import Condition
else:
    _time = monotonic
    from threading import _Condition as _ConditionBase
    
    class Condition(_ConditionBase):
        
        def wait_for(self, predicate, timeout=None):
            """Wait until a condition evaluates to True.
    
            predicate should be a callable which result will be interpreted as a
            boolean value.  A timeout may be provided giving the maximum time to
            wait.
    
            """
            endtime = None
            waittime = timeout
            result = predicate()
            while not result:
                if waittime is not None:
                    if endtime is None:
                        endtime = _time() + waittime
                    else:
                        waittime = endtime - _time()
                        if waittime <= 0:
                            break
                self.wait(waittime)
                result = predicate()
            return result
    
    from Queue import Queue as _Queue, Empty
    
    class Queue(_Queue):
        def __init__(self, maxsize=0):
            _Queue.__init__(self, maxsize=maxsize)
            
            self.not_empty = Condition(self.mutex)
            self.not_full = Condition(self.mutex)
            self.all_tasks_done = Condition(self.mutex)

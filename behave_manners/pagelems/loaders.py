# -*- coding: UTF-8 -*-
import errno
from abc import abstractmethod
import os.path


class BaseLoader(object):
    """Abstract base for loading DPO html files off some storage
    """
    def __init__(self):
        pass
    
    @abstractmethod
    def open(self, fname):
        """Open file at `fname` path for reading.
        
            Return a context manager file object
        """

class FSLoader(BaseLoader):

    def __init__(self, root_dir):
        super(FSLoader, self).__init__()
        if not os.path.exists(root_dir):
            raise IOError(errno.ENOENT, "No such directory: %s" % root_dir)
        self.root_dir = root_dir

    def open(self, fname):
        if '..' in fname.split('/'):
            raise IOError(errno.EACCESS, "Parent directory not allowed")
        pathname = os.path.normpath(os.path.join(self.root_dir, fname))
        return open(pathname, 'rb')


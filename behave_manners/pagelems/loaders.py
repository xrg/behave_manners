# -*- coding: UTF-8 -*-
from __future__ import absolute_import
import errno
from abc import abstractmethod
import os
import glob
from os.path import normpath, join


class BaseLoader(object):
    """Abstract base for loading DPO html files off some storage

        Subclass this to enable loading from any kind of storage.
    """
    def __init__(self):
        pass

    @abstractmethod
    def open(self, fname, directory='', mode='rb'):
        """Open file at `fname` path for reading.
        
            Return a context manager file object
        """

    @abstractmethod
    def multi_open(self, filepattern, directory='', mode='rb'):
        """Open a set of files (by glob pattern) for reading
        
           :return: iterator of open files
        """


class FSLoader(BaseLoader):
    """Trivial filesystem-based loader of files
    """

    def __init__(self, root_dir):
        super(FSLoader, self).__init__()
        if not os.path.exists(root_dir):
            raise IOError(errno.ENOENT, "No such directory: %s" % root_dir)
        self.root_dir = root_dir

    def open(self, fname, mode='rb'):
        if '..' in fname.split('/'):
            raise IOError(errno.EACCESS, "Parent directory not allowed")
        pathname = normpath(join(self.root_dir, fname))
        return open(pathname, mode)

    def multi_open(self, filepattern, mode='rb'):
        if '..' in filepattern.split('/'):
            raise IOError(errno.EACCESS, "Parent directory not allowed")

        old_cwd = os.getcwd()
        fp = None
        try:
            for fname in glob.glob(normpath(join(self.root_dir, filepattern))):
                pdir, fname2 = os.path.split(fname)
                if pdir:
                    os.chdir(pdir)
                fp = self.open(fname2, mode)
                yield fname, fp
                fp.close()
                fp = None
                if pdir:
                    os.chdir(old_cwd)
        finally:
            if fp is not None:
                fp.close()
            os.chdir(old_cwd)


#eof

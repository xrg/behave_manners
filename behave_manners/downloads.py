# -*- coding: UTF-8 -*-
""" Utilities for browser screenshots, connected to events
    
"""
from __future__ import absolute_import
import os
import os.path
import logging
import time
import errno
import fnmatch


logger = logging.getLogger(__name__)


class DownloadManager(object):
    """Capture downloads that appear on some folder
    
        Some sites may have complex JS mechanisms about storing downloads.
        In such a case, webdriver may not know what file has come (at this
        point most drivers don't have an explicit API for that).
        This manager tries to guess which files may have appeared since
        some UI interaction
    """

    def __init__(self, download_dir):
        self._dir = os.path.abspath(download_dir)
        self._past_files = set()
        self._cur_files = set()
        if not os.path.isdir(self._dir):
            raise IOError(errno.ENOENT, "No such directory")
        self.reset()

    def reset(self):
        """Scan directory. Consider all files 'past', reset 'current'
        """
        self._past_files.clear()
        for path in os.listdir(self._dir):
            self._past_files.add(path)   # even if it is a directory
        self._cur_files.clear()

    def wait(self, timeout=10.0, expect='*'):
        """Waits for known temporary files patterns, browser to finish downloads
        """
        NotImplemented

    def look_for(self, pattern='*', files_only=True):
        """Look for downloaded file matching pattern, since last reset

            :param pattern: glob pattern to match files
            :param files_only: only report files, not directories
            :return: iterator of (filename, absolute_pathname) of matching files
        """

        for path in os.listdir(self._dir):
            if path in self._past_files:
                continue
            fullpath = os.path.join(self._dir, path)
            if files_only and not os.path.isfile(fullpath):
                continue
            if fnmatch.fnmatch(path, pattern):
                self._cur_files.add(path)
                yield path, fullpath
            else:
                self._cur_files.add(path)

#eof

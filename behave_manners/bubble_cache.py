# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import threading
import time
import six


__all__ = ('BubbleCache',)


class BubbleCache(object):
    """A cache, meant to have a very short lifetime

        Meant to bust on touch, whenever any operation would risk
        changing its contents
    """

    enabled = True
    timeout = 3.0  # seconds

    # Class methods that instantiate thread-local sigleton

    @classmethod
    def cache(cls, fn):
        hfn = hash(fn)
        @six.wraps(fn)
        def __fn(*args, **kwargs):
            if not cls.enabled:
                # immediate result, no hashing or so
                return fn(*args, **kwargs)
            cinst = cls._instance()
            key = (hfn, hash(args), repr(kwargs))
            try:
                return cinst.__get(key)
            except KeyError:
                ret = fn(*args, **kwargs)
                cinst.__set(key, ret)
                return ret

        if cls.enabled:
            return __fn
        else:
            return fn

    @classmethod
    def pop(cls, fn):
        """Invalidate the cache, whenever `fn` gets called
        """
        @six.wraps(fn)
        def __fn(*args, **kwargs):
            try:
                cls._local.cache.__pop()
            except AttributeError:
                # no need to pop if there is no instance
                pass
            return fn(*args, **kwargs)

        return __fn

    _local = threading.local()

    @classmethod
    def _instance(cls):
        """Retrieve/init singleton for this thread
        """
        try:
            return cls._local.cache
        except AttributeError:
            c = cls._local.cache = cls()
            return c

    def __init__(self):
        """Cache object, meant to be a singleton
        """
        self.__reset()

    def __reset(self):
        self._entries = {}
        self._expires_at = time.time() + self.timeout

    def __get(self, key):
        if time.time() > self._expires_at:
            self.__reset()
            raise KeyError()
        return self._entries[key]

    def __set(self, key, value):
        if time.time() > self._expires_at:
            self.__reset()
        self._entries[key] = value

    def __pop(self):
        self._expires_at = 0

#eof

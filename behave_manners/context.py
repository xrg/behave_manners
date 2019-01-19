# -*- coding: UTF-8 -*-

import threading



__all__ = ('context',)


class GContext(object):
    def __init__(self):
        self._stack = [dict(),]

    @classmethod
    def current(cls):
        local = threading.local()
        if not hasattr(local, 'gcontext'):
            local.gcontext = cls()
        return local.gcontext
    
    def push(self):
        nc = self._stack[-1].copy()
        self._stack.append(nc)
        return self

    def pop(self):
        if len(self._stack <= 1):
            raise RuntimeError("Pop from top stack")
        self._stack.pop()

    def __getattr__(self, name):
        try:
            return self._stack[-1][name]
        except KeyError:
            raise AttributeError(name)
        except IndexError:
            raise RuntimeError("Empty stack")

    def __setattr__(self, name, value):
        self._stack[-1][name] = value

    def __enter__(self):
        return self.push()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pop()
        return


# eof

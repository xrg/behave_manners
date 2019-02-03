# -*- coding: UTF-8 -*-

import threading



__all__ = ('GContext',)


class GContext(object):

    __slots__ = ('_ctx', '_globalroot')

    def __init__(self, **kwargs):
        self._ctx = ctx = threading.local()
        self._globalroot = kwargs   # global context limited to one (root) level
        # use 'ctx' name to avoid `self.__setattr__` call
        ctx.stack = [kwargs,]

    def __init_newthread(self):
        if hasattr(self._ctx , 'stack'):
            return
        self._ctx.stack = [self._globalroot, dict()]  # new thread. must be at stack+1

    def push(self):
        self.__init_newthread()
        nc = self._ctx.stack[-1].copy()
        self._ctx.stack.append(nc)
        return self

    def pop(self):
        if len(self._ctx.stack) <= 1:
            raise RuntimeError("Pop from top stack")
        self._ctx.stack.pop()

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        self.__init_newthread()
        try:
            return self._ctx.stack[-1][name]
        except KeyError:
            raise AttributeError(name)
        except IndexError:
            raise RuntimeError("Empty stack")

    def __setattr__(self, name, value):
        if name.startswith('_'):
            return super(GContext, self).__setattr__(name, value)
        self.__init_newthread()
        self._ctx.stack[-1][name] = value

    def new(self, **kwargs):
        """Return context manager object, new level down current context
        
            Usage::
                my_context.a = 0
                with my_context.new(a=1) as ctx:
                    ctx.b = 2
                    assert my_context.a == 1
                    assert my_context.b == 2
                assert my_context.a == 0
        """
        return self._GContextContext(self, kwargs)

    def _update(self, dict2):
        self._ctx.stack[-1].update(dict2)

    @property
    def _parent(self):
        try:
            return self._GContextSnap(self._ctx.stack[-2])
        except IndexError:
            raise AttributeError("Current stack is top-level, no parent")

    class _GContextContext(object):
        def __init__(self, context, new_kwargs):
            self.context = context
            self.new_kwargs = new_kwargs

        def __enter__(self):
            return self.context.push()._update(self.new_kwargs)

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.context.pop()
            return

    class _GContextSnap(object):
        """Read-only snapshot of context, for accessing other levels
        """
        slots = ('_ctx', )

        def __init__(self, context):
            self._ctx = context

        def __getattr__(self, name):
            try:
                return self._ctx[name]
            except KeyError:
                raise AttributeError(name)

        def __setattr__(self, name, value):
            if name.startswith('_'):
                return super(GContext._GContextSnap, self).__setattr__(name, value)
            raise TypeError("attempt to set value to read-only context")



# eof

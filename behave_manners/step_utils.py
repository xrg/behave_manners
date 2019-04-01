from __future__ import print_function
#from functools import wraps


class _StepImplies(object):
    def __init__(self, step_fn, implies=False):
        assert callable(step_fn)
        self._step_fn = step_fn
        self._imply_stmt = []
        if implies:
            self._imply_stmt.insert(0, implies)

    def __call__(self, context, *args, **kwargs):
        step_text = u'\n    and %s'.join(self._imply_stmt)

        context.execute_steps(step_text)
        return self._step_fn(context, *args, **kwargs)

    def insert_implies(self, step_text):
        # TODO detect Given/When/Then prefix
        self._imply_stmt.insert(0, step_text)

    @property
    def func_code(self):
        """Return code for introspection; the wrapped one
        """
        return self._step_fn.__code__

    @property
    def __code__(self):
        return self._step_fn.__code__


def implies(step_text):

    def _wrap_step(step_fn):
        if isinstance(step_fn, _StepImplies):
            step_fn.insert_implies(step_text)
            return step_fn
        else:
            return _StepImplies(step_fn, step_text)

    return _wrap_step

#eof

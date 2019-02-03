# -*- coding: UTF-8 -*-

from __future__ import absolute_import, print_function
import threading
import pytest
from behave_manners.context import GContext


def function_check(context, var, value):
    assert getattr(context, var, 'not-found') == value


class TestTheContext(object):
    context = GContext(a=1)

    def test_global_is_here(self):
        assert self.context.a == 1

    def test_context_no_underscore(self):
        with pytest.raises(AttributeError):
            self.context._foo = 3

    def test_global_in_subthread(self):
        t = threading.Thread(target=function_check,
                             args=(self.context, 'a', 1))
        t.start()
        t.join()

    def test_sub_context(self):

        try:
            self.context.push()
            self.context.b = 2
            self.context.a = 3
            assert self.context.a == 3
            assert self.context.b == 2
        finally:
            self.context.pop()

        assert self.context.a == 1
        with pytest.raises(AttributeError):
            print("global b:", self.context.b)

    def test_with_context(self):

        with self.context.new(c=3):
            self.context.a = 4
            assert self.context.c == 3
            assert self.context.a == 4

        assert self.context.a == 1
        assert not hasattr(self.context, 'c')


    def test_parent_context(self):
        with self.context.new():
            self.context.a = 4
            assert self.context.a == 4
            assert self.context._parent.a == 1
            with pytest.raises(TypeError):
                self.context._parent.a = 2

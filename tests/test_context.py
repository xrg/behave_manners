# -*- coding: UTF-8 -*-

from __future__ import absolute_import, print_function
import threading
import pytest
from behave_manners.context import GContext, EventContext


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


class TestEventContext(object):
    econtext = EventContext(on_spam=None, on_ham=lambda l: l.append('ham1'))

    def test_call_spam(self):
        lr = []
        self.econtext.on_spam(lr)
        assert lr == []

    def test_call_ham(self):
        lr = []
        self.econtext.on_ham(lr)
        assert lr == ['ham1']

    def test_call_other(self):
        with pytest.raises(AttributeError):
            self.econtext.on_nee()

    def test_call_spam2(self):
        self.econtext.push(on_spam=lambda l: l.append('spam2'),
                           on_ham=lambda l: l.append('ham2'))
        try:
            spam = []
            ham = []
            self.econtext.on_spam(spam)
            self.econtext.on_ham(ham)

            assert spam == ['spam2']
            assert ham == ['ham2', 'ham1']

        finally:
            self.econtext.pop()

    def test_call_contextmgr(self):
        ham = []
        spam = []
        with self.econtext(on_spam=lambda l: l.append('spam3'),
                           on_ham=lambda l: l.append('ham3')):
            self.econtext.on_spam(spam)
            self.econtext.on_ham(ham)

        assert spam == ['spam3']
        assert ham == ['ham3', 'ham1']

        self.econtext.on_spam(spam)
        self.econtext.on_ham(ham)

        assert spam == ['spam3']
        assert ham == ['ham3', 'ham1', 'ham1']


    def test_call_return(self):
        def fn_with_return(l):
            l.append('ret')
            return 1

        ham = []
        with self.econtext(on_ham=fn_with_return):
            r = self.econtext.on_ham(ham)

        assert ham == ['ret']
        assert r == 1


# eof

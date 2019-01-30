# -*-coding: UTF-8 -*-

from __future__ import division
import re


word_re = re.compile(r'\w+$')

def textescape(tstr):
    if "'" not in tstr:
        return "'%s'" % tstr
    elif '"' not in tstr:
        return '"%s"' % tstr
    else:
        return "concat('" + "', '\"', '".join(tstr.split('"')) + "')"  # Perl alert!


def prepend_xpath(pre, xpath):
    """Prepend some xpath to another, properly joining the slashes

    """

    if pre.endswith('./'):
        if xpath.startswith('./'):
            return pre[:-2] + xpath
        elif xpath.startswith('/'):  # including '//'
            return pre[:-1] + xpath
    elif pre.endswith('//'):
        return pre + xpath.lstrip('/')
    elif pre.endswith('/') and xpath.startswith('/'):
        return pre[:-1] + xpath
    elif pre.endswith('/') and xpath.startswith('./'):
        return pre + xpath[2:]

    return pre + xpath


class Integer(object):
    """Mutable integer implementation
    
        Useful for counters, that need to be passed by reference
    """

    __slots__ = ('_value',)

    def __init__(self, value):
        if not isinstance(value, (int, Integer)):
            raise TypeError("Cannot convert from %s to integer" % type(value))
        self._value = value

    def __int__(self):
        return self._value

    def __repr__(self):
        return str(self._value)

    def __bool__(self):
        return self._value

    __nonzero__ = __bool__

    def __lt__(self, other):
        if isinstance(other, Integer):
            other = other._value
        return self._value < other

    def __le__(self, other):
        if isinstance(other, Integer):
            other = other._value
        return self._value <= other

    def __gt__(self, other):
        if isinstance(other, Integer):
            other = other._value
        return self._value > other

    def __ge__(self, other):
        if isinstance(other, Integer):
            other = other._value
        return self._value >= other

    def __eq__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return self._value == other

    def __abs__(self):
        return Integer(abs(self._value))

    def __add__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return Integer(self._value + other)

    def __sub__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return Integer(self._value - other)

    def __mul__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return Integer(self._value * other)

    def __mod__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return Integer(self._value % other)

    def __truediv__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return self._value / other

    def __floordiv__(self, other):
        if isinstance(other, Integer):
            other = other._value

        return self._value // other

    def __iadd__(self, other):
        if isinstance(other, Integer):
            other = other._value

        self._value += other
        return self

    def __isub__(self, other):
        if isinstance(other, Integer):
            other = other._value

        self._value -= other
        return self

    def __itruediv__(self, other):
        raise RuntimeError("Integer only supports floor division inplace")

    def __ifloordiv__(self, other):
        if isinstance(other, Integer):
            other = other._value

        self._value //= other
        return self

    def __imul__(self, other):
        if isinstance(other, Integer):
            other = other._value

        self._value *= other
        return self


# eof

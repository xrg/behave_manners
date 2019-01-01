# -*- coding: UTF-8 -*-
""" Proxies of selenium WebElements into abstract structure of page's information

"""

import logging
import six
from collections import OrderedDict

from selenium.webdriver.common.by import By


class _SomeProxy(object):
    def __init__(self):
        self._elements = OrderedDict()

    def pretty_dom(self, key=None):
        for k, e in self._elements.items():
            for i,n,d in e.pretty_dom(key=k):
                yield i+1, n, d

    def set(self, key, elem):
        self._elements[key] = elem


class PageProxy(_SomeProxy):
    """DPO live page, connected to some selenium webdriver DOM
    """
    def __init__(self, dtmpl, webdriver):
        super(PageProxy, self).__init__()
        self._elements = OrderedDict()

    def pretty_dom(self, key=None):
        yield (0,key or '(Page)', '')
        for r in super(PageProxy, self).pretty_dom():
            yield r

    def add(self, elem):
        n = len(self._elements)  # FIXME
        self._elements[n] = elem


class ElementProxy(_SomeProxy):
    """Cross-breed of a Selenium element and DPO page object
    
    """
    def __init__(self, dtmpl, webelem):
        super(ElementProxy, self).__init__()
        self._dtmpl = dtmpl
        self._webelem = webelem

    def pretty_dom(self, key=None):
        yield (0, key or 'Element', '<%s>' % self._webelem.tag_name)
        for d in dir(self):
            yield (1, '', '%s=%s' % (d, getattr(self, d)))
        for r in super(ElementProxy, self).pretty_dom():
            yield r


# eof

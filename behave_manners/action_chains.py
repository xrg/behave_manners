# -*- coding: UTF-8 -*-
"""
    Wrapper around `selenium.common.action_chains` that uses domComponents as inputs
    
"""

from __future__ import absolute_import
import six
from selenium.webdriver.common.action_chains import ActionChains as SeleniumChains
from .pagelems.dom_components import PageProxy, ComponentProxy


class ActionChains(object):
    """Mirror of `selenium.common.action_chains` for domComponents
    """
    def __init__(self, component):
        if isinstance(component, ComponentProxy):
            remote = component._remote.parent
        elif isinstance(component, PageProxy):
            remote = component._remote
        else:
            raise TypeError(type(component))
        self._chain = SeleniumChains(remote)

        for name in ('move_by_offset', 'pause', 'perform', 'reset_actions', 'send_keys'):
            self.__decorate_zero(name)

        for name in ('click', 'click_and_hold', 'context_click', 'double_click',
                     'drag_and_drop_by_offset', 'release', 'send_keys_to_element',
                     'move_to_element', 'move_to_element_with_offset'):
            self.__decorate_one(name)

        for name in ('key_down', 'key_up'):
            self.__decorate_key_one(name)

    def drag_and_drop(self, source, target):
        self._chain.drag_and_drop(source._remote, target._remote)
        return self

    def __decorate_zero(self, name):
        method = getattr(self._chain, name)
        @six.wraps(method)
        def __fn(*args, **kwargs):
            method(*args, **kwargs)
            return self
        setattr(self, name, __fn)

    def __decorate_one(self, name):
        method = getattr(self._chain, name)

        @six.wraps(method)
        def __fn(comp=None, *args, **kwargs):
            if comp is None:
                remote = None
            else:
                remote = comp._remote
            method(remote, *args, **kwargs)
            return self

        setattr(self, name, __fn)

    def __decorate_key_one(self, name):
        method = getattr(self._chain, name)

        @six.wraps(method)
        def __fn(key, comp=None):
            if comp is None:
                remote = None
            else:
                remote = comp._remote
            method(key, remote)
            return self

        setattr(self, name, __fn)

#eof

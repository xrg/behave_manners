# -*-coding: UTF-8 -*-

from __future__ import absolute_import
from selenium.common.exceptions import NoSuchElementException


class ElementNotFound(NoSuchElementException):
    """Raised when a `WebElement` cannot locate a child, refers to that parent

    """
    def __init__(self, msg=None, screen=None, stacktrace=None, 
                 parent=None, selector=None, pagelem_name=None):
        if not msg:
            msg = "No such element: %s" % selector
        super(ElementNotFound, self).__init__(msg, screen=screen, stacktrace=stacktrace)
        self.parent = parent
        self.selector = selector
        self.pagelem_name = pagelem_name

    @property
    def pretty_parent(self):
        """String of parent element, in pretty format
        """
        if self.parent is None:
            return '<unknown>'
        try:
            parent_id = self.parent.get_attribute('id')
            if parent_id:
                return '<%s id="%s">' % (self.parent.tag_name, parent_id)
            else:
                return '<%s>' % self.parent.tag_name
        except Exception:
            return repr(self.parent)


class PageNotReady(AssertionError):
    pass


class Timeout(AssertionError):
    pass


class ComponentException(object):
    """Mixin for exceptions that can refer to faulty component
    
        The component would be an instance of `ComponentProxy`
    """
    def __init__(self, component=None, msg=None):
        self.component = component
        self.msg = msg


class CKeyError(KeyError, ComponentException):
    def __init__(self, arg, msg=None, component=None):
        KeyError.__init__(self, arg)
        ComponentException.__init__(self, msg=msg, component=component)


class CAttributeError(AttributeError, ComponentException):
    def __init__(self, arg, msg=None, component=None):
        AttributeError.__init__(self, arg)
        ComponentException.__init__(self, msg=msg, component=component)


class CAssertionError(AssertionError, ComponentException):
    def __init__(self, arg, component=None):
        AssertionError.__init__(self, arg)
        ComponentException.__init__(self, component=component)

#eof

# -*-coding: UTF-8 -*-

from __future__ import absolute_import
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import six

if six.PY2:
    import copy_reg as copyreg
else:
    import copyreg


"""
    Exceptions tailored to pagelems/behave usage.

    Most of these classes just subclass known exceptions, but also keep a
    reference to the component/web-element that caused the failure.

"""


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


class UnwantedElement(NoSuchElementException):
    pass


class PageNotReady(AssertionError):
    """Raised when browser has not finished rendering/settled the page
    """
    pass


class Timeout(AssertionError):
    """Raised when any action or element fails to respond in time
    """
    pass


class ComponentException(object):
    """Mixin for exceptions that can refer to faulty component

        The component would be an instance of `ComponentProxy`
    """
    def __init__(self, component=None, msg=None):
        self.component = component
        self.msg = msg

    def __getstate__(self):
        return {'component': self.component,
                'msg': '%s' % self.msg,      # render to string, py3 compatible
                }


class CKeyError(KeyError, ComponentException):
    def __init__(self, arg, msg=None, component=None):
        KeyError.__init__(self, arg)
        ComponentException.__init__(self, msg=msg, component=component)


class CAttributeError(AttributeError, ComponentException):
    def __init__(self, arg, msg=None, component=None):
        AttributeError.__init__(self, arg)
        ComponentException.__init__(self, msg=msg, component=component)


class CAttributeNoElementError(CAttributeError):
    """Raised when component attribute cannot be retrieved because of missing element

        Special case of `CAttributeError`, may need to be handled explicitly.
        Implies `NoSuchElementException` from remote DOM.
    """
    pass


class CAssertionError(AssertionError, ComponentException):
    def __init__(self, arg, component=None):
        AssertionError.__init__(self, arg)
        ComponentException.__init__(self, component=component)


class CValueError(ValueError, ComponentException):
    def __init__(self, arg, component=None):
        ValueError.__init__(self, arg)
        ComponentException.__init__(self, component=component)


def _pickle_wdexception(wde):
    """Pickle exception with bare information
    """
    return wde.__class__, (wde.msg, None, wde.stacktrace)


def _pickle_enotfound_exception(e):
    return e.__class__, ('%s' % e.msg, None, e.stacktrace,
                         None, e.selector, '%s' % e.pagelem_name)


copyreg.pickle(WebDriverException, _pickle_wdexception)
copyreg.pickle(ElementNotFound, _pickle_enotfound_exception)


#eof

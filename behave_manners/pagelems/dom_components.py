# -*- coding: UTF-8 -*-
""" Proxies of selenium WebElements into abstract structure of page's information

    Goal of the PageTemplates/Component is to reduce the multi-level DOM 
    structure of a web-page to a compact structure of /Components/ , which
    then convey the semantic information of that DOM and are easy to assert
    in testing.
    Components may be trivial, corresponding to single DOM elements, or not,
    being abstractions over complex DOM structures. They /should/ have their
    entry point mapped to a particular DOM element.
    
    Components must have a well-defined /path/ to be addressed with. This
    cannot be guaranteed by this framework, but rather should be achieved
    through careful design of the page templates. Heavily dependant on the
    web-page's structure and technology. A good path is one that would map
    the "same" DOM element to a specific path, through subsequent readings
    of the webpage. Even if the webpage's DOM has been re-built by the JS
    framework of the page (React, Angular, etc.) .
    
    Example: a table. Using a `<pe-repeat>` template element, rows of that
    table could be mapped to components. For static tables, path could just
    be the row number of those rows. But this becomes non-deterministic for
    tables that are, say, grids with dynamic sorting or infinite scroll. On
    those, key to the rows should be some primary key of the row data, like
    the remote database ID or unique name of that row-data.
    
    Components should be considered volatile. By design, this framewor does
    NOT hold a reference of children components to one, but rather re-maps
    children on demand. Likewise, values of attributes shall always be fetched
    from the remote, each time the Component attribute is read. No caching.
    It is the caller's responsibility to copy the Component attributes to
    some other variable, if caching (rather than multiple WebDriver requests)
    is desired.
    
    Unreachable components should be handled graceously. They would still
    raise an exception all the way up, but plugins may help in debugging,
    like by highlighting the visual position in the webpage where something
    is missing.
    
"""

from __future__ import absolute_import
import logging
import inspect
import warnings
from selenium.common.exceptions import WebDriverException
from .exceptions import CAttributeError, CKeyError


logger = logging.getLogger(__name__)


class _SomeProxy(object):
    """Baseclass for Component proxies
    
        Inherited by both `PageProxy` and `Component`, links "remote" WebDriver
        entities to this abstract structure.
        
        Proxies have a dict-like interface, "containing" other proxies. They can
        be iterated like dicts.
        
    """
    _pagetmpl = None
    _remote = None

    def __init__(self, pagetmpl, remote, scope=None):
        self._pagetmpl = pagetmpl
        self._remote = remote
        self._scope = scope
        if scope is not None:
            scope.take_component(self)

    @property
    def path(self):
        raise NotImplementedError()

    def __getitem__(self, name):
        for iname, ielem, ptmpl, scp in \
                self._pagetmpl.iter_items(self._remote, self._scope, match=name):
            if name == iname:
                return scp.component_class(iname, self, ptmpl, ielem, scp)
        raise CKeyError(name, component=self)  # no such element

    def keys(self):
        return self.__iter__()

    def __iter__(self):
        for name, welem, ptmpl, scp in self._pagetmpl.iter_items(self._remote, self._scope):
            yield name

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if (self._scope is not other._scope) or (self._pagetmpl is not other._pagetmpl):
            return False
        return self._remote == other._remote

    def items(self):
        for iname, ielem, ptmpl, scp in self._pagetmpl.iter_items(self._remote, self._scope):
            yield iname, scp.component_class(iname, self, ptmpl, ielem, scp)


class PageProxy(_SomeProxy):
    """Root of Components, the webpage
    
        Holds reference to remote WebDriver, has no parent
    """
    def __init__(self, pagetmpl, webdriver, scope):
        super(PageProxy, self).__init__(pagetmpl, webdriver, scope)
        self.__descrs = dict()

    @property
    def path(self):
        return ()

    def __getstate__(self):
        return {}

    def __repr__(self):
        try:
            return '<Page "%s">' % self._remote.current_url
        except Exception:
            return '<Page >'

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        descr = self.__getdescr(name)
        return descr.__get__(self)

    def __dir__(self):
        return self.__descrs.keys()

    def __setattr__(self, name, value):
        if name.startswith('_') or name in ('path', ):
            return super(PageProxy, self).__setattr__(name, value)
        descr = self.__getdescr(name)
        return descr.__set__(self, value)

    def __delattr__(self, name):
        if name.startswith('_') or name in ('path', ):
            raise AttributeError('Attribute %s cannot be deleted' % name)
        descr = self.__getdescr(name)
        return descr.__delete__(self)

    def __getdescr(self, name):
        if not name.startswith('_'):
            descr = self._scope._page_descriptors.get(name, None)
            if descr is not None:
                self.__descrs[name] = descr
                return descr

        raise AttributeError(name)


class CSSProxy(object):
    def __init__(self, parent):
        self.__remote = parent._remote

    def __getitem__(self, name):
        try:
            # non-existing properties will just return None from this call
            return self.__remote.value_of_css_property(name)
        except WebDriverException as e:   # TODO handling of WebDriverExceptions
            raise

    def __setitem__(self, name, value):
        raise NotImplementedError


class ComponentProxy(_SomeProxy):
    """Cross-breed of a Selenium element and DPO page object

    """
    __attrs = {}

    def __init__(self, name, parent, pagetmpl, webelem, scope):
        super(ComponentProxy, self).__init__(pagetmpl, webelem, scope)
        assert isinstance(parent, _SomeProxy)
        self._name = name
        self._parent = parent
        # Keep list of attributes
        self.__descrs = dict(self._pagetmpl.iter_attrs(webelem, scope))
        self.css = CSSProxy(self)

    def __repr__(self):
        try:
            return '<%s class="%s">' % (self._remote.tag_name, self._remote.get_attribute('class'))
        except Exception:
            return '<Component>'

    def __eq__(self, other):
        if not super(ComponentProxy, self).__eq__(other):
            return False
        return self._name == other._name  # has to match, too
        # but parent may differ

    def __getstate__(self):
        """Minimal serialization, just for `repr(self)` to work

            A component proxy, by nature, cannot be de-serialized and retain
            its functionality.
        """
        return {'_name': self._name}

    def __getdescr(self, name):
        """Resolve descriptor
        """
        try:
            # most likely case
            return self.__descrs[name]
        except KeyError:
            # new API for scope classes
            descr = self._scope._comp_descriptors.get(name, None)
            if descr is not None:
                self.__descrs[name] = descr
                return descr

            cwrap = getattr(self._scope, '_cwrap_'+name, None)
            # Found factory of remote element method
            if cwrap is not None:
                warnings.warn("cwrap interface will be deprecated", DeprecationWarning)
                if inspect.ismethod(cwrap):
                    val = cwrap(self, name)
                    cwrap = property(lambda c: val)
                self.__descrs[name] = cwrap
                return cwrap

        raise CAttributeError(name, component=self)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        descr = self.__getdescr(name)
        return descr.__get__(self)

    def __dir__(self):
        return list(self.__descrs.keys())

    def __setattr__(self, name, value):
        if name.startswith('_') or name in ('css', 'path', 'component_name'):
            return super(ComponentProxy, self).__setattr__(name, value)
        descr = self.__getdescr(name)
        return descr.__set__(self, value)

    def __delattr__(self, name):
        if name.startswith('_') or name in ('css', 'path', 'component_name'):
            raise AttributeError('Attribute %s cannot be deleted' % name)
        descr = self.__getdescr(name)
        return descr.__delete__(self)

    @property
    def path(self):
        return self._parent.path + (self._name,)

    @property
    def component_name(self):
        return self._name


# eof

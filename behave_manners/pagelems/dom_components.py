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
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException
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

    @property
    def path(self):
        raise NotImplementedError()

    def __iteritems(self, match=None):
        """Calls pagetmpl.iter_items() with stale support

            If `self` becomes stale during iteration, no recovery
            will ever be attempted
        """
        pr = True
        while pr:
            try:
                for neps in self._pagetmpl.iter_items(self._remote, self._scope, match=match):
                    pr = False
                    yield neps
            except StaleElementReferenceException:
                if pr and self._recover_stale():
                    continue
                else:
                    raise
            return

    def __getitem__(self, name):
        for iname, ielem, ptmpl, scp in self.__iteritems(name):
            if name == iname:
                comp = scp.component_class(iname, self, ptmpl, ielem, scp)
                scp.take_component(comp)
                return comp

        raise CKeyError(name, component=self)  # no such element

    def keys(self):
        return self.__iter__()

    def values(self):
        """Iteration of sub-components under this one
        """
        for name, welem, ptmpl, scp in self.__iteritems():
            comp = scp.component_class(name, self, ptmpl, welem, scp)
            scp.take_component(comp)
            yield comp

    def __len__(self):
        """Calculate length of sub-elements

            Warning: this must iterate over the remote elements, is *slow*
        """
        n = 0
        for x in self.__iteritems():
            n += 1
        return n

    def __bool__(self):
        """All components should be truthy

            This avoids calling expensive `len(self)`
        """
        return True

    __nonzero__ = __bool__   # py2.7 compatibility

    def __iter__(self):
        for name, welem, ptmpl, scp in self.__iteritems():
            yield name

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if (self._scope is not other._scope) or (self._pagetmpl is not other._pagetmpl):
            return False
        return self._remote == other._remote

    def items(self):
        for iname, ielem, ptmpl, scp in self.__iteritems():
            comp = scp.component_class(iname, self, ptmpl, ielem, scp)
            scp.take_component(comp)
            yield iname, comp

    def filter(self, *fn, **kwargs):
        raise NotImplementedError("%s.filter() not available" % self.__class__.__name__)

    def _recover_stale(self):
        """Update self after point to stale remote element

            This one cannot recover, see `ComponentProxy._recover_stale()`
        """
        return False


class PageProxy(_SomeProxy):
    """Root of Components, the webpage
    
        Holds reference to remote WebDriver, has no parent
    """
    def __init__(self, pagetmpl, webdriver, scope):
        super(PageProxy, self).__init__(pagetmpl, webdriver, scope)
        self.__descrs = self._scope._page_descriptors.copy()

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
        try:
            return self.__descrs[name]
        except KeyError:
            raise AttributeError(name)


class CSSProxy(object):
    def __init__(self, parent):
        self.__remote = parent._remote

    def __getitem__(self, name):
        try:
            # non-existing properties will just return None from this call
            return self.__remote.value_of_css_property(name)
        except WebDriverException:   # TODO handling of WebDriverExceptions
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
        # Prepare list of attributes
        # assume that `_pe_class` in some pageelement means that
        # the controller is root for that component.
        if getattr(pagetmpl, '_pe_class', None) is None \
                and getattr(scope, '_comp2_descriptors', None) is not None:
            self.__descrs = scope._comp2_descriptors.copy()
        else:
            self.__descrs = scope._comp_descriptors.copy()
        self.__descrs.update(self._pagetmpl.iter_attrs(webelem, scope))
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

    def filter(self, clause, safe=True):
        """Iterator over sub-components that satisfy a condition

            Usage::

                for row in table.filter(lambda r: r['col_4'].text == "bingo!"):
                    print("Found the bingo row:", row)

            equivalent to::

                for row in table.values():
                    if row['col_4'].text == "bingo!":
                        print("Found the bingo row:", row)


            `clause` must be a function, which evaluates against a component
            and returns True whenever that component should participate in
            the result.

            IFF `clause` is simple enough, `filter()` may optimize it to
            resolve the iteration in a very efficient search.
        """
        from .filter_components import FilterComp
        try:
            fc_res = FilterComp._filter_on_clause(self._pagetmpl, self._scope, clause)
            logger.debug("Got optimizer: %r", fc_res)
            if fc_res.complete and not safe:
                clause = None
        except (KeyError, AttributeError, NotImplementedError) as e:
            logger.warning("Cannot optimize <%s '%s'>.filter(): %s",
                           self._remote.tag_name, self._name, e)
            fc_res = None

        for name, welem, ptmpl, scp in self._SomeProxy__iteritems(match=fc_res):
            comp = scp.component_class(name, self, ptmpl, welem, scp)
            if (clause is None) or clause(comp):
                scp.take_component(comp)
                yield comp

    def filter_gen(self, clause, safe=True):
        """Generator of `.filter()` functions

            Just because the optimization in `.filter()` may be expensive
            to compute, it can be done once (offline) and re-applied
            multiple times to generate many iterator instances
        """
        from .filter_components import FilterComp
        try:
            fc_res = FilterComp._filter_on_clause(self._pagetmpl, self._scope, clause)
            logger.debug("Got optimizer: %r", fc_res)
            if fc_res.complete and not safe:
                clause = None
        except (KeyError, AttributeError, NotImplementedError) as e:
            logger.warning("Cannot optimize <%s '%s'>.filter(): %s",
                           self._remote.tag_name, self._name, e)
            fc_res = None

        def _filter():
            for name, welem, ptmpl, scp in self._SomeProxy__iteritems(match=fc_res):
                comp = scp.component_class(name, self, ptmpl, welem, scp)
                if (clause is None) or clause(comp):
                    scp.take_component(comp)
                    yield comp

        return _filter

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

    def _recover_stale(self):
        """Return new webelement to amend stale component

            :return: whether a new element has been located to recover this
        """
        parent = self._parent
        if not (parent and getattr(parent._scope, 'recover_stale', False)):
            return False

        for r in (0, 1):
            try:
                for iname, ielem, p, s in \
                        parent._pagetmpl.iter_items(parent._remote, parent._scope,
                                                    match=self._name):
                    if iname == self._name:
                        self._remote = ielem
                        return True
            except StaleElementReferenceException:
                if r or not parent._recover_stale():
                    raise
        return False


# eof

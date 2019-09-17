# -*- coding: UTF-8 -*-

from __future__ import absolute_import, unicode_literals
import six
from .helpers import prepend_xpath, textescape, XPath



class _HypoElem(object):
    """Hypothetical remote element, used to build locator for a real one
    """

    def __init__(self, xpath= ''):
        self._xpath = xpath

    def __repr__(self):
        return '<hypo %s>' % self._xpath

    def _append_xpath(self, xpath, glue=False):
        return _HypoElem(prepend_xpath(self._xpath, xpath, glue=glue))

    def find_elements_by_xpath(self, xpath):
        if not xpath:
            return self
        return [ self._append_xpath(xpath, glue='/')]

    def find_element_by_id(self, id_val):
        raise NotImplementedError('element by id:' + id_val)

    def find_element_by_xpath(self, xpath):
        return self._append_xpath(xpath, glue='/')

    @property
    def text(self):
        return self._attrCondition(self, '.')

    def get_attribute(self, name):
        return self._attrCondition(self, '@%s' % name)


    class _attrCondition(object):
        def __init__(self, parent, attr, strip=False):
            self._parent = parent
            self._attr = attr
            self._strip = strip

        def strip(self):
            return self.__class__(self._parent, self._attr, True)

        def __hash__(self):
            return hash(id(self))

        def __eq__(self, other):
            if not isinstance(other, six.string_types):
                raise TypeError("Can not compare properties to %s" % type(other))

            if self.strip:
                return self._parent._append_xpath('[contains(%s, %s)]' %
                                                  (self._attr, textescape(other)))
            else:
                return self._parent._append_xpath('[%s=%s]' %
                                                  (self._attr, textescape(other)))


class FilterComp(object):
    """Hypothetical component, obeying matching rules against template
    """

    @classmethod
    def _filter_on_clause(cls, pagetmpl, scope, clause):
        rem_root = _HypoElem('')
        ret = []
        for iname, welem, ptmpl, nscope in pagetmpl.iter_items(rem_root, scope):
            fcomp = cls(iname, welem, ptmpl, None, nscope)
            try:
                cr = clause(fcomp)
                if not cr:
                    continue
                elif isinstance(cr, _HypoElem):
                    fcomp._remote = cr
                elif isinstance(cr, FilterComp):
                    fcomp = cr
                ret.append(fcomp._get_matcher())
            except (KeyError, AttributeError):
                # TODO
                raise
        return XPath('[%s]' % (' or ' .join(ret)))

    def __init__(self, cname, remote, pagetmpl, parent, scope):
        self._cname = cname
        self._pagetmpl = pagetmpl
        self._scope = scope
        self._remote = remote
        self._parent = parent

    def __getitem__(self, name):
        """return a matcher against sub-component
        """
        welem = _HypoElem('')
        for iname, welem, ptmpl, scope \
                in self._pagetmpl.iter_items(welem, self._scope, match=name):
            clause = (iname == name)
            if not clause:
                continue
            elif isinstance(clause, _HypoElem):
                welem = clause
                iname = name  # Assume it will match

            return FilterComp(iname, welem, ptmpl, self, scope)
        raise KeyError(name)

    def __getattr__(self, name):
        """matcher against attribute
        """
        for n, descr in self._pagetmpl.iter_attrs(self._remote, self._scope):
            if n == name:
                try:
                    rev_fn = descr.get_rev(self)
                except AttributeError:
                    raise NotImplementedError("Descriptor %s cannot reverse" % descr.__class__.__name__)
                return rev_fn
        else:
            raise NotImplementedError(name)

    def _get_matcher(self):
        """Returns XPath expression that would match this one
        """
        x = self
        r = ''
        while x:
            if x._remote._xpath:
                if r:
                    r = '[' + r + ']'
                r = x._remote._xpath + r
            x = x._parent

        return r

#eof

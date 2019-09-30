# -*- coding: UTF-8 -*-

from __future__ import absolute_import, unicode_literals
import six
from .helpers import prepend_xpath, textescape, XPath



class _HypoElem(object):
    """Hypothetical remote element, used to build locator for a real one
    """

    def __init__(self, xpath= '', complete=True):
        self._xpath = xpath
        self._complete = complete

    def __repr__(self):
        return '<hypo %s%s>' % ('' if self._complete else '~',
                                self._xpath)

    def _append_xpath(self, xpath, glue=False, complete=True):
        return _HypoElem(prepend_xpath(self._xpath, xpath, glue=glue),
                         complete=complete)

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


    class _attrConditionBase(object):
        def __init__(self, parent=None, attr=None):
            self._parent = parent
            self._attr = attr

    class _attrCondition(_attrConditionBase):
        def __init__(self, parent, attr, strip=False):
            super(_HypoElem._attrCondition, self).__init__(parent, attr)
            self._strip = strip

        def __hash__(self):
            return hash(id(self))

        def strip(self):
            return self.__class__(self._parent, self._attr, True)

        def __eq__(self, other):
            if isinstance(other, six.string_types):
                if self._strip:
                    exp = '[contains(%s, %s)]'
                else:
                    exp = '[%s=%s]'

                return self._parent._append_xpath( exp % (self._attr, textescape(other)))
            elif other is True:
                return self._parent._append_xpath('[%s]' % self._attr)
            elif other is False:
                return self._parent._append_xpath('[not(%s)]' % self._attr)
            else:
                raise TypeError("Can not compare properties to %s" % type(other))

        def __ne__(self, other):
            if isinstance(other, six.string_types):
                if self._strip:
                    exp = '[not(contains(%s, %s))]'
                else:
                    exp = '[%s!=%s]'

                return self._parent._append_xpath( exp % (self._attr, textescape(other)))
            elif other is False:
                return self._parent._append_xpath('[%s]' % self._attr)
            elif other is True:
                return self._parent._append_xpath('[not(%s)]' % self._attr)
            else:
                raise TypeError("Can not compare properties to %s" % type(other))

        def __contains__(self, item):
            if isinstance(item, six.string_types):
                return self._parent._append_xpath('[contains(%s, %s)]' %
                                                  (self._attr, textescape(item)))
            else:
                raise TypeError("Can not compare properties to %s" % type(item))

        def startswith(self, item):
            if isinstance(item, six.string_types):
                return self._parent._append_xpath('[starts-with(%s, %s)]' %
                                                  (self._attr, textescape(item)))
            else:
                raise TypeError("Can not compare properties to %s" % type(item))

        def endswith(self, item):
            if isinstance(item, six.string_types):
                # there is no "ends-with()" function in XPath,
                # so narrow down results with 'contains()'
                return self._parent._append_xpath('[contains(%s, %s)]' %
                                                  (self._attr, textescape(item)),
                                                  complete=False)
            else:
                raise TypeError("Can not compare properties to %s" % type(item))

        def bool(self):
            """Return boolean representation.

                Note that this is not `__bool__` ; rather needs to be called
                explicitly
            """
            return self._parent._append_xpath( '[%s]' % self._attr)

        # __bool__ = bool

        def __int__(self):
            raise NotImplementedError("Must use toInt(attr) instead")

        def toNumber(self):
            return _HypoElem._intAttrCondition(self._parent, self._attr)

    class _intAttrCondition(_attrConditionBase):

        def __hash__(self):
            return hash(id(self))

        def __get_cmp_op(self, op, other):
            if isinstance(other, six.integer_types):
                return self._parent._append_xpath('[number(%s)%s%d]' %
                                                  (self._attr, op, other))
            elif isinstance(other, float):
                return self._parent._append_xpath('[number(%s)%s%f]' %
                                                  (self._attr, op, other))
            else:
                raise TypeError("Can not compare properties to %s" % type(other))

        def __eq__(self, other):
            return self.__get_cmp_op('=', other)

        def __ne__(self, other):
            return self.__get_cmp_op('!=', other)

        def __lt__(self, other):
            return self.__get_cmp_op('<', other)

        def __le__(self, other):
            return self.__get_cmp_op('<=', other)

        def __gt__(self, other):
            return self.__get_cmp_op('>', other)

        def __ge__(self, other):
            return self.__get_cmp_op('>=', other)


class _RootHypoElem(_HypoElem):
    """Variant of _HypoElem for the top-most matcher

        This has to be skipped, since the initial XPath is going to be
        located by the template in real mode
    """
    def __init__(self):
        super(_RootHypoElem, self).__init__(None)

    def find_elements_by_xpath(self, xpath):
        return [ _HypoElem('')]

    def find_element_by_id(self, id_val):
        return _HypoElem('')

    def find_element_by_xpath(self, xpath):
        return _HypoElem('')


class FilterComp(object):
    """Hypothetical component, obeying matching rules against template
    """

    @classmethod
    def _filter_on_clause(cls, pagetmpl, scope, clause):
        rem_root = _RootHypoElem()
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
                elif isinstance(cr, _HypoElem._attrConditionBase):
                    cr = cr.bool()
                    fcomp._remote = cr
                else:
                    raise NotImplementedError("Clause resolves to %s" % type(cr))
                ret.append(fcomp._get_matcher())
            except (KeyError, AttributeError):
                # TODO
                raise

        if not ret:
            # FIXME
            return False
        if ret[0].startswith('['):
            if len(ret) > 1:
                raise NotImplementedError("combine more than a simple matcher")
            return XPath(ret[0])

        return XPath('[%s]' % (' or ' .join(ret)))

    def __bool__(self):
        return True

    __nonzero__ = __bool__

    def __init__(self, cname, remote, pagetmpl, parent, scope):
        self._cname = cname
        self._pagetmpl = pagetmpl
        self._scope = scope
        self._remote = remote
        self._parent = parent

    def __getitem__(self, name):
        """return a matcher against sub-component
        """
        for iname, welem, ptmpl, scope \
                in self._pagetmpl.iter_items(self._remote, self._scope, match=name):
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
                if r and not r.startswith('['):
                    r = '[' + r + ']'
                r = x._remote._xpath + r
            x = x._parent

        return r


def toInt(sth):
    if isinstance(sth, _HypoElem._attrConditionBase):
        return sth.toNumber()
    else:
        return int(sth)


def toFloat(sth):
    if isinstance(sth, _HypoElem._attrConditionBase):
        return sth.toNumber()
    else:
        return int(sth)


#eof

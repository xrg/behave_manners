# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import logging
import re
import json
from collections import defaultdict

from .helpers import textescape, prepend_xpath, word_re, to_bool
from .base_parsers import DPageElement, DataElement, BaseDPOParser, \
                          HTMLParseError, DOMScope
from .site_collection import DSiteCollection
from .exceptions import ElementNotFound, CAttributeError, CKeyError
from selenium.webdriver.remote.webdriver import WebElement
from selenium.common.exceptions import NoSuchElementException
import six


method_re = re.compile(r'\w+\(')

class DomContainerElement(DPageElement):
    """Base class for 'regular' DOM elements that can contain others
    """
    _name = '.domContainer'

    xpath_score_attrs = {'id': 100, 'name': 80, 'class': 50,  # global attributes
                         'type': 50, 'action': 60,    # for forms
                         }

    @classmethod
    def calc_xpath_score(cls, keys):
        ret = 0
        for k in keys:
            ret += cls.xpath_score_attrs.get(k, 5)
        return ret

    def reduce(self, site=None):
        prev = None
        repls = []
        for n, c in enumerate(self._children):
            if isinstance(c, DataElement) and prev is not None:
                c.set_full(False)
            elif isinstance(prev, DataElement):
                prev.set_full(False)
            elif isinstance(c, Text2AttrElement) and prev is not None:
                nc = c.consume_after(prev)
                if nc is not c:
                    repls.append((n, nc))
            elif isinstance(prev, Text2AttrElement):
                nc = prev.consume_before(c)
                if nc is not prev:
                    repls.append((n-1, nc))
            prev = c
        if repls:
            for n, c in repls:
                self._children[n] = c

        return super(DomContainerElement, self).reduce(site)


DomContainerElement._consume_in = (DomContainerElement, )


class AttrGetter(object):
    """Descriptor to get some attribute of a `ComponentProxy`
    """
    __slots__ = ('xpath', 'name', 'optional')
    logger = logging.getLogger(__name__ + '.attrs')

    def __init__(self, name, xpath=None, optional=False):
        self.name = name
        self.xpath = xpath
        self.optional = optional

    def _elem(self, comp):
        """Locate the web element from given component
        """
        try:
            elem = comp._remote
            if self.xpath:
                elem = elem.find_element_by_xpath(self.xpath)
        except NoSuchElementException as e:
            if self.optional:
                self.logger.debug("Attribute %r.%s could not be found, returning None",
                                  comp, self.name)
                return None
            else:
                raise CAttributeError(six.text_type(e), component=comp)
        return elem

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        return elem.get_attribute(self.name)

    def __set__(self, comp, value):
        raise CAttributeError("%s is readonly" % self.name, component=comp)

    def __delete__(self, comp):
        raise CAttributeError("%s is readonly" % self.name, component=comp)



class AnyElement(DPageElement):
    """Match any HTML element
    
        This would match any element in the remote DOM, but also serves as a
        baseclass for matching particular tags.

        Offers some standard attributes and rich syntax for matching remote
        DOM element properties.
    """
    _name = 'tag.pe-any'
    _inherit = '.domContainer'

    def __init__(self, tag, attrs, any_tag='*'):
        super(AnyElement, self).__init__(tag)
        match_attrs = defaultdict(list)
        self.read_attrs = {}
        self._xpath = any_tag
        self._pe_class = None
        self._dom_slot = None
        self._pe_optional = False
        self._split_attrs(attrs, match_attrs, self.read_attrs)
        self._xpath_score = 0
        self._set_match_attrs(match_attrs)

    def _set_match_attrs(self, match_attrs):
        for k, vs in match_attrs.items():
            ors = []
            for v in vs:
                if v is True:
                    # only match existence of attribute
                    ors.append('@%s' % (k,))
                elif v == '!':
                    ors.append('not(@%s)' % (k,))
                elif v.startswith('!+'):
                    v = v[1:]
                    ors.append('not('
                            + ' and '.join(['contains(@%s,%s)' % (k, textescape(w))
                                            for w in v[1:].split(' ')])
                            + ')')
                elif v.startswith('+'):
                    v = v[1:]
                    clauses = ['contains(@%s,%s)' % (k, textescape(w))
                                for w in v.split(' ')]
                    if len(clauses) > 1:
                        ors.append('boolean(' + ' and '.join(clauses) + ')')
                    elif clauses:
                        ors.append(clauses[0])
                elif v.startswith('!'):
                    ors.append('not(@%s=%s)' % (k, textescape(v)))
                else:
                    ors.append('@%s=%s' % (k, textescape(v)))

            self._xpath += '[' + ' or '.join(ors) + ']'
        self._xpath_score += self.calc_xpath_score(match_attrs.keys())

    def _split_this(self, value, sub=None):
        raise RuntimeError('%s passed \'this\'' % self.__class__.__name__)

    def _split_attrs(self, attrs, match_attrs, read_attrs):
        for k, v in attrs:
            if k == 'this':
                self._split_this(v)
            elif k == 'slot':
                self._dom_slot = v
            elif k == 'pe-deep':
                self._xpath = './/' + self._xpath
            elif k == 'pe-optional':
                self._pe_optional = to_bool(v)
            elif k == 'pe-controller' or k == 'pe-ctrl':
                if self._pe_class:
                    raise ValueError("Attribute 'pe-controller' defined more than once")
                self._pe_class = DOMScope.get_class(v)  # is it defined?
            elif v is None:
                assert '.' not in k, k
                match_attrs[k].append(True)
            elif v.startswith('[') and v.endswith(']'):
                assert '.' not in k, k   # TODO
                # attribute to read value from
                if k in read_attrs:
                    raise ValueError('Attribute defined more than once: %s' % k)
                v = v[1:-1].strip()
                read_attrs[v or k] = k
            else:
                assert '.' not in k, k
                # attribute to match as locator
                match_attrs[k].append(v)

    def reduce(self, site=None):
        if len(self._children) == 1 \
                and self._name in ('any', 'tag.pe-any') \
                and not self.read_attrs \
                and self._dom_slot is None \
                and self._pe_class is None \
                and isinstance(self._children[0], NamedElement):
            # Merge Named element with self (its parent)
            ret = self._children[0]
            ret._xpath = prepend_xpath(self._xpath + '/', ret._xpath)
            if self._pe_optional:
                ret._pe_optional = True
            ret._reset_xpath_locator()
            return ret
        return super(AnyElement, self).reduce(site)

    def xpath_locator(self, score, top=False):
        locator = ''
        if self._pe_optional and not top:
            return locator
        if score and score > 0:
            locator = self._xpath
            score -= self._xpath_score

        if score > -100:
            child_locs = []
            for c in self._children:
                cloc = c.xpath_locator(score)
                if cloc and cloc != '*':
                    child_locs.append(cloc)

            if top or (len(child_locs) > 1) \
                    or (child_locs and method_re.match(child_locs[0])):
                for cloc in child_locs:
                    locator += '[%s]' % cloc
            elif child_locs:
                locator += prepend_xpath('/', child_locs[0])
        return locator

    def _locate_in(self, remote, scope, xpath_prefix, match):
        xpath2 = prepend_xpath(xpath_prefix, self.xpath)
        enoent = True
        for welem in remote.find_elements_by_xpath(xpath2):
            # Stop at first 'welem' that yields any children results
            try:
                nscope = scope
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)

                ret = list(self.iter_items(welem, nscope, match=match))
                # all children elements have been resolved here
                # List may be empty, but no children would have
                # raised exception by this point.
                for y4 in ret:
                    yield y4
                enoent = False
            except ElementNotFound as e:
                if enoent is True:
                    # Keep first exception encountered
                    enoent = e

        if enoent and not self._pe_optional:
            if enoent is True:
                # No element matched xpath2, loop above didn't run
                enoent = ElementNotFound(selector=xpath2, parent=remote)
            raise enoent

    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        return self._iter_items_cont(remote, scope, xpath_prefix, match)

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Iterate names of possible attributes

            :return: iterator of (name, descriptor)
        """
        for n, attr in self.read_attrs.items():
            yield n, AttrGetter(attr, xpath_prefix, optional=self._pe_optional)
        for ch in self._children:
            for n, attr in ch._locate_attrs(webelem, scope, xpath_prefix):
                if self._pe_optional and isinstance(attr, AttrGetter):
                    attr.optional = True
                yield n, attr

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        return self.iter_attrs(webelem, scope, prepend_xpath(xpath_prefix, self._xpath, '/'))


class GenericElement(DPageElement):
    _name = 'any'
    _inherit = 'tag.pe-any'

    def __init__(self, tag, attrs):
        super(GenericElement, self).__init__(tag, attrs, any_tag=tag)
        self._xpath_score += 10


class LeafElement(DPageElement):
    # TODO
    _name = '.leaf'
    _inherit = 'any'

    def consume(self, element):
        raise TypeError('%s cannot consume %r' % (self._name, element))


class TextAttrGetter(AttrGetter):
    def __init__(self, xpath, optional=False, do_strip=False):
        super(TextAttrGetter, self).__init__('text', xpath, optional=optional)
        self._do_strip = do_strip

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        ret = elem.text
        if not ret:
            ret = elem.get_attribute('innerText')
        if ret and self._do_strip:
            ret = ret.strip()
        return ret

class PartialTextAttrGetter(TextAttrGetter):
    def __init__(self, xpath, before_elem=None, after_elem=None, **kwargs):
        super(PartialTextAttrGetter, self).__init__(xpath, **kwargs)
        self._after_elem = after_elem
        self._before_elem = before_elem

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        js = 'let cnodes = arguments[0].childNodes;\n' \
             'let i = 0; let ret = "";\n'
        if self._after_elem == '*':
            js += '''
                for (;i<cnodes.length;i++){
                    if (cnodes[i].nodeType == 3) break;
                }
                '''
        elif self._after_elem:
            js += '''
                for (;i<cnodes.length;i++){
                    if ((cnodes[i].nodeType == 1) && (cnodes[i].tagName == arguments[1])) break;
                }
                '''
        js += 'for(;i<cnodes.length; i++){ \n'
        if self._before_elem == '*':
            js += '  if (cnodes[i].nodeType == 1) break; '
        elif self._before_elem:
            js += '  if ((cnodes[i].nodeType == 1) && (cnodes[i].tagName == arguments[2])) break;\n'
        js += '  if (cnodes[i].nodeType == 3) { ret += cnodes[i].nodeValue; }\n}\nreturn ret;'

        ret = elem.parent.execute_script(js, elem, self._after_elem, self._before_elem)
        if ret and self._do_strip:
            ret = ret.strip()
        return ret


class Text2AttrElement(DPageElement):
    _name = 'text2attr'
    is_empty = True
    _consume_in = (DomContainerElement,)

    def __init__(self, name, strip=False):
        super(Text2AttrElement, self).__init__()
        self._attr_name = name
        self._getter_class = TextAttrGetter
        self._getter_kwargs = dict(do_strip=strip)

    def consume(self, element):
        raise TypeError('Data cannot consume %r' % element)

    def _elem2tag(self, element):
        """Get the plain tag_name of some pagelement to be reached
        """
        if isinstance(element, GenericElement):
            return element.tag.upper()  # tagName is upper for HTML (not for XHTML)
        else:
            return '*'

    def consume_after(self, element):
        """Turn this into a partial text matcher, after some element tag
        """
        if 'after_elem' not in self._getter_kwargs:
            if isinstance(element, DPageElement):
                element = self._elem2tag(element)
            self._getter_kwargs['after_elem'] = element
            self._getter_class = PartialTextAttrGetter
        return self

    def consume_before(self, element):
        """Turn this into a partial text matcher, before some tag
        """
        if 'before_elem' not in self._getter_kwargs:
            if isinstance(element, DPageElement):
                element = self._elem2tag(element)
            self._getter_kwargs['before_elem'] = element
            self._getter_class = PartialTextAttrGetter
        return self

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        yield self._attr_name, self._getter_class(xpath_prefix, **self._getter_kwargs)


class RegexAttrGetter(AttrGetter):
    def __init__(self, regex, xpath, group=None, optional=False):
        super(RegexAttrGetter, self).__init__('text', xpath, optional=optional)
        self._regex = regex
        self._group = group

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        m = self._regex.match(elem.text or '')
        if not m:
            return None

        if self._group:
            return m.group(self._group)
        else:
            return m.group()

class RegexElement(DPageElement):
    """Match text of remote DOM element, parse with regex into attribute(s)

        If this regex contains ``(?P<name>...)`` named groups, these will be
        exposed as `name` attributes.

        Otherwise, if `this` attribute is defined, expose *all* matched string
        under this name.

        .. note :: text inside this element can contain '<' and '>', no need
            to escape these.
    """
    _name = 'tag.pe-regex'
    _consume_in = (DomContainerElement,)
    _attrs_map = {'name': ('_attr_name', None, None),
                 }

    def __init__(self, tag, attrs):
        super(RegexElement, self).__init__(tag)
        self._parse_attrs(attrs)
        self._regex = None

    def consume(self, element):
        if not isinstance(element, DataElement):
            raise TypeError("Regex can only contain text")
        super(RegexElement, self).consume(element)

    def reduce(self, site=None):
        if self._regex is None:
            regstr = ''.join([c.data for c in self._children])
            self._regex = re.compile(regstr)
        return super(RegexElement, self).reduce(site)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        if self._attr_name:
            yield self._attr_name, RegexAttrGetter(self._regex, xpath_prefix)
        for g in self._regex.groupindex:
            yield g, RegexAttrGetter(self._regex, xpath_prefix, group=g)


class NamedElement(DPageElement):
    _name = 'named'
    _inherit = 'any'

    class _fakeComp(object):
        def __init__(self, elem):
            self._remote = elem

    def __init__(self, tag, attrs):
        super(NamedElement, self).__init__(tag, attrs)

        # parse `this_name` into dynamic function
        pattern = self.this_name
        if pattern.startswith('[') and pattern.endswith(']'):
            pattern = pattern[1:-1].strip()
            if not word_re.match(pattern):
                raise NotImplementedError("Cannot parse expression '%s'" % pattern)

            self._this_fn = self.__get_pattern_resolver(pattern)
            self._this_rev = lambda m: True   # TODO
        elif '%s' in pattern or '%d' in pattern:
            self._this_fn = lambda n, x, c: pattern % n
            self._this_rev = lambda m: True  # TODO
        else:
            # plain name, no iteration
            self._this_fn = lambda *a: pattern
            self._this_rev = lambda m: m == pattern

    def __get_pattern_resolver(self, pattern):
        """Closure for computing item name based on attributes

            :param pattern: name of attribute to resolve
        """
        def _resolver(n, welem, scope):
            for name, descr in self.iter_attrs(welem, scope):
                if name == pattern:
                    ret = descr.__get__(self._fakeComp(welem))
                    if ret:
                        return ret.strip()
                    else:
                        return ''
            return n

        return _resolver

    def _split_this(self, value, sub=None):
        if sub:
            raise NotImplementedError()
        self.this_name = value

    def pretty_dom(self):
        """Walk this template, generate (indent, name, xpath) sets of each node
        """
        yield (0, self.this_name, self.xpath)
        for c in self._children:
            for i, n, x in c.pretty_dom():
                yield i+1, n, prepend_xpath('./',  x)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        if match is None:
            reverse = True
        else:
            # resolve some boolean or xpath to reverse match name looking for
            reverse = self._this_rev(match)

        if reverse is False:
            return

        xpath = prepend_xpath(xpath_prefix, self.xpath)
        if reverse is not True:
            xpath += reverse

        n = 0
        enofound = None
        for welem in remote.find_elements_by_xpath(xpath):
            try:
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)
                else:
                    nscope = scope
                yield self._this_fn(n, welem, nscope), welem, self, nscope
            except NoSuchElementException as e:
                enofound = ElementNotFound(msg=str(e), parent=welem, selector='*')
            n += 1
        if not (n or self._pe_optional):
            if enofound is None:
                enofound = ElementNotFound(parent=remote, selector=xpath)
            raise enofound

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        # Stop traversing, no attributes exposed from this to parent
        return ()


class InputValueDescr(AttrGetter):
    def __init__(self, xpath):
        super(InputValueDescr, self).__init__('value', xpath)

    def __set__(self, comp, value):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        driver = elem.parent
        driver.execute_script("arguments[0].value = arguments[1];", elem, value)

    def __delete__(self, comp):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        elem.clear()


class InputElement(DPageElement):
    _name = 'tag.input'
    _inherit = 'any'
    is_empty = True
    descr_class = InputValueDescr

    def __init__(self, tag, attrs):
        self.this_name = None
        self.name_attr = None
        super(InputElement, self).__init__(tag, attrs)

    def _split_this(self, value, sub=None):
        if sub:
            raise NotImplementedError()
        self.this_name = value

    def _set_match_attrs(self, match_attrs):
        vs = match_attrs.get('name', None)
        if vs is None:
            self.name_attr = '*'
            if ('id' not in match_attrs) and not self.this_name:
                raise ValueError("An input element must be identified by 'id' or 'name'")
        elif vs == ['*']:
            del match_attrs['name']
            self.name_attr = '*'
        else:
            self.name_attr = vs[0]

        # TODO: per type

        super(InputElement, self)._set_match_attrs(match_attrs)

    def consume(self, element):
        raise TypeError('Input cannot consume %r' % element)

    def iter_items(self, remote, xpath_prefix=''):
        # no children, nothing to return
        return []

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        for y2 in super(InputElement, self).iter_attrs(webelem, scope, xpath_prefix):
            yield y2
        if self.this_name:
            yield ('value', self.descr_class(xpath_prefix))

    def _locate_in(self, remote, scope, xpath_prefix, match):
        if self.this_name:
            enoent = True
            xpath2 = prepend_xpath(xpath_prefix, self.xpath, glue='/')
            for welem in remote.find_elements_by_xpath(xpath2):
                nscope = scope
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)
                enoent = False
                yield self.this_name, welem, self, nscope
            if enoent and not self._pe_optional:
                raise ElementNotFound(parent=remote, selector=xpath2)
        else:
            return

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        if not self.this_name:
            # expose self as attribute
            if self.name_attr == '*':
                # Active remote iteration here, must discover all <input> elements
                # and yield as many attributes
                for relem in webelem.find_elements_by_xpath(prepend_xpath(xpath_prefix, self.xpath, glue='/')):
                    rname = relem.get_attribute('name')
                    xpath = self._xpath + "[@name=%s]" % textescape(rname)
                    yield rname, self.descr_class(prepend_xpath(xpath_prefix, xpath, glue='/'))
            else:
                # Avoid iteration, yield attribute immediately
                yield self.name_attr, self.descr_class(prepend_xpath(xpath_prefix, self._xpath, glue='/'))


class TextAreaObj(DPageElement):
    _name = 'tag.textarea'
    _inherit = 'tag.input'


class DeepContainObj(DPageElement):
    _name = 'tag.pe-deep'
    _inherit = '.domContainer'

    def __init__(self, tag, attrs):
        if attrs:
            raise ValueError('Deep cannot have attributes')
        super(DeepContainObj, self).__init__(tag)

    def reduce(self, site=None):
        if len(self._children) == 1 and self._children[0]._name in ('any', 'tag.pe-any', 'named'):
            ch = self._children.pop()
            ch._xpath = prepend_xpath('.//', ch._xpath)
            ch._reset_xpath_locator()
            return ch
        return super(DeepContainObj, self).reduce(site)

    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        return self._iter_items_cont(remote, scope, xpath_prefix='.//', match=match)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        return self._iter_items_cont(remote, scope, xpath_prefix='.//', match=match)

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix='.//'):
        """Iterate names of possible attributes

            returns iterator of (name, descriptor)
        """
        for ch in self._children:
            for y2 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y2

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix='.//'):
        return self.iter_attrs(webelem, scope, prepend_xpath(xpath_prefix, self.xpath))

    def xpath_locator(self, score, top=False):
        if score <= -100:
            return ''

        score *= 2   # operating in half-score
        try:
            child_locs = []
            for c in self._children:
                cloc = c.xpath_locator(score)
                if cloc:
                    child_locs.append(cloc)

            if top or (len(child_locs) > 1):
                locator = './/'
                for cloc in child_locs:
                    locator += '[%s]' % cloc
                return locator
            elif child_locs:
                return prepend_xpath('.//', child_locs[0])
            else:
                score -= 2
                return '*'  # any stray element satisfies a 'Deep' match
        finally:
            score //= 2


class RootAgainElem(DPageElement):
    """Reset to root element (of DOM), keep component deep in tree

    """
    _name = 'tag.pe-root'
    _inherit = '.domContainer'

    def __init__(self, tag, attrs):
        if attrs:
            raise ValueError('Deep cannot have attributes')
        super(RootAgainElem, self).__init__(tag)

    def iter_items(self, remote, scope, xpath_prefix='//', match=None):
        return self._iter_items_cont(remote, scope, xpath_prefix=xpath_prefix, match=match)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        return self._iter_items_cont(remote.parent, scope, xpath_prefix='//', match=match)

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix='//'):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for ch in self._children:
            for y2 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y2

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix='//'):
        return self.iter_attrs(webelem.parent, scope, self.xpath)

    def xpath_locator(self, score, top=False):
        if not top:
            return ''

        child_locs = []
        for c in self._children:
            cloc = c.xpath_locator(score)
            if cloc:
                child_locs.append(cloc)

        locator = '//'
        for cloc in child_locs:
            locator += '[%s]' % cloc
        return locator



class RepeatObj(DPageElement):
    _name = 'tag.pe-repeat'
    _inherit = '.domContainer'

    _attrs_map = {'min': ('min_elems', int, 0),
                  'max': ('max_elems', int, 1000000),
                  'this': ('this_name', str, ''),
                  'slot': ('_dom_slot', None, None),
                  }

    def __init__(self, tag, attrs):
        super(RepeatObj, self).__init__(tag)
        self._parse_attrs(attrs)

    def reduce(self, site=None):
        if not self._children:
            raise ValueError("<Repeat> must have contained elements")

        if len(self._children) > 1:
            raise NotImplementedError("Cannot handle siblings in <Repeat>")  # yet

        self._reset_xpath_locator()
        return super(RepeatObj, self).reduce(site)

    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        ni = 0
        seen = set()
        enofound = None
        try:
            for name, welem, ptmpl, scp in self._children[0] \
                    ._locate_in(remote, scope, xpath_prefix, match):
                if not name:
                    name = ni   # integer type, not a string!
                elif name in seen:
                    name += str(ni)
                yield name, welem, ptmpl, scp
                ni += 1
                if ni > self.max_elems:
                    break
        except ElementNotFound as e:
            enofound = e
        if match is None and ni < self.min_elems:
            if enofound is None:
                raise ElementNotFound(parent=remote, selector=xpath_prefix)
            else:
                raise enofound

    def _locate_in(self, remote, scope, xpath_prefix, match):
        # If this has a name, return new container Component,
        # else just iterate contents
        if self.this_name:
            if match is None or match == self.this_name:
                yield self.this_name, remote, self, scope
        else:
            for y4 in self.iter_items(remote, scope, xpath_prefix, match):
                yield y4


class PeChoiceElement(DPageElement):
    """Matches the first child of this element

    """
    _name = 'tag.pe-choice'
    _inherit = '.domContainer'
    _attrs_map = {'slot': ('_dom_slot', None, None),
                  }

    def __init__(self, tag, attrs):
        super(PeChoiceElement, self).__init__(tag)
        self._parse_attrs(attrs)

    def reduce(self, site=None):
        if not self._children:
            return None
        elif len(self._children) == 1:
            return self._children[0]
        else:
            return super(PeChoiceElement, self).reduce(site)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        enofound = None
        nfound = 0
        seen = set()
        for ch in self._children:
            # Stop at first 'welem' that yields any children results
            try:
                for n, welem, p, scp in ch._locate_in(remote, scope, xpath_prefix, match):
                    if welem in seen:
                        continue
                    seen.add(welem)
                    yield n, welem, p, scp
                    nfound += 1
            except ElementNotFound as e:
                if enofound is None:
                    enofound = e

        if match is None and not nfound:
            if enofound is not None:
                raise enofound
            else:
                locs = []
                for ch in self._children[:3]:
                    locs.append(ch.xpath)
                raise ElementNotFound(selector=' or '.join(locs),
                                      parent=remote)


class PeGroupElement(DPageElement):
    """Trivial group, DOM-less container of many elements

        Elements within a group are ordered!
    """
    _name = 'tag.pe-group'
    _inherit = '.domContainer'
    _attrs_map = {'slot': ('_dom_slot', None, None),
                  'pe-controller': ('_pe_ctrl', None, None),
                  'pe-ctrl': ('_pe_ctrl', None, None),
                  'pe-optional': ('_pe_optional', to_bool, None),
                  }

    def __init__(self, tag, attrs):
        super(PeGroupElement, self).__init__(tag)
        self._parse_attrs(attrs)
        if self._pe_ctrl is None:
            self._pe_class = None
        else:
            self._pe_class = DOMScope.get_class(self._pe_ctrl)

    def reduce(self, site=None):
        if not self._children:
            return None
        elif len(self._children) == 1:
            return self._children[0]
        else:
            return super(PeGroupElement, self).reduce(site)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        ret = []

        # get all sub-components in one go
        seen = set()
        nscope = scope
        if self._pe_class is not None:
            nscope = self._pe_class(parent=scope)
        try:
            for ch in self._children:
                for y4 in ch._locate_in(remote, nscope, xpath_prefix, match):
                    if y4[0] in seen:
                        continue
                    ret.append(y4)
                    seen.add(y4[0])
        except ElementNotFound:
            if self._pe_optional:
                return  # ignore 'ret'
            else:
                raise

        # after this has finished (all located), return them
        for y4 in ret:
            yield y4

    def xpath_locator(self, score, top=False):
        if score < -100:
            return ''

        locs = []
        for ch in self._children:
            xloc = ch.xpath_locator(score, top=True)  # want the first DOM child
            if xloc:
                if locs:
                    locs += '/following-sibling::'
                locs.append(xloc)

        return ''.join(locs)


class PeMatchIDElement(DPageElement):
    _name = 'tag.pe-matchid'
    _inherit = '.domContainer'
    _attrs_map = {'pe-controller': ('_pe_ctrl', None, None),
                  'pe-ctrl': ('_pe_ctrl', None, None),
                  'pe-optional': ('_pe_optional', to_bool, None),
                  'id': ('attr_id', None, AttributeError),
                  'this': ('this_name', None, None),
                  }

    def __init__(self, tag, attrs):
        super(PeMatchIDElement, self).__init__(tag)
        self._parse_attrs(attrs)
        if self._pe_ctrl is None:
            self._pe_class = None
        else:
            self._pe_class = DOMScope.get_class(self._pe_ctrl)

        self._idc = compile(self.attr_id, 'html:pe-matchid', mode='eval')

    def _locate_remote(self, remote, scope):
        try:
            id_val = eval(self._idc, {}, {'root': scope.root_component})
        except (KeyError, AttributeError) as e:
            if self._pe_optional:
                return None
            raise e
        if not id_val:
            if self._pe_optional:
                return None
            else:
                raise ElementNotFound(msg='Attribute \'%s\' has no value' % self.attr_id,
                                        parent=scope.root_component)

        if isinstance(remote, WebElement):
            remote = remote.parent   # operate at root of DOM, the page

        try:
            return remote.find_element_by_id(id_val)
        except NoSuchElementException as e:
            if not self._pe_optional:
                raise ElementNotFound(msg=str(e), selector='@id=%s' % id_val)
            return None

    def _locate_in(self, remote, scope, xpath_prefix, match):
        if self.this_name and match is not None and match != self.this_name:
            return

        welem = self._locate_remote(remote, scope)
        if welem is None:
            return

        if self._pe_class is not None:
            nscope = self._pe_class(parent=scope)
        else:
            nscope = scope

        # only expect a single element (by id) ever
        if self.this_name:
            yield self.this_name, welem, self, nscope
        else:
            for y4 in self.iter_items(welem, nscope, match):
                yield y4


    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        return self._iter_items_cont(remote, scope, xpath_prefix, match)

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for ch in self._children:
            for y2 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y2

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Only expose attributes if this is not a named element
        """
        if not self.this_name:
            welem = self._locate_remote(webelem, scope)
            if welem is not None:
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)
                else:
                    nscope = scope
                for y2 in self.iter_attrs(welem, nscope):
                    yield y2


class PeDataElement(DPageElement):
    """Define arbitrary data as a component attribute

        This supports two modes: with a `value=` attribute or
        using inner JSON data.

        When using the `value=` attribute, the data will be a
        plain string.
        When using inner JSON, it can be any of the simple types
        that JSON supports.
    """
    _name = 'tag.pe-data'
    _attrs_map = {'slot': ('_dom_slot', None, None),
                'name': ('_attr_name', None, AttributeError),
                'value': ('_attr_value', None, NotImplemented),
                         # Using NotImplemented as sentinel, because None is valid JSON
                }
    _consume_in = (DomContainerElement, )

    def __init__(self, tag, attrs):
        super(PeDataElement, self).__init__(tag)
        self._parse_attrs(attrs)

    def consume(self, element):
        if not isinstance(element, DataElement):
            raise TypeError("pe-data can only contain text")
        if self._attr_value is not NotImplemented:
            raise ValueError("<pe-data> cannot have both value and inner data")
        super(PeDataElement, self).consume(element)

    def reduce(self, site=None):
        if self._attr_value is NotImplemented:
            self._attr_value = json.loads(''.join([c.data for c in self._children]))
            self._children = []
        if self._attr_value is NotImplemented:
            raise ValueError("<pe-data> has no data")
        return super(PeDataElement, self).reduce(site)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Irrespective of webelem or scope, return the value
        """
        yield self._attr_name, property(lambda *c: self._attr_value)


class ConsumeTmplMixin(object):
    """Common between Head and Body elements, temporarily hold templates
    """
    _tmp_templates = ()  # start with immutable iterable

    def consume(self, element):
        if isinstance(element, DTemplateElement):
            if isinstance(self._tmp_templates, tuple):
                # copy class-wide to instance-specific list
                self._tmp_templates = list(self._tmp_templates)
            self._tmp_templates.append(element)
        else:
            super(ConsumeTmplMixin, self).consume(element)


class DHeadElement(ConsumeTmplMixin, DPageElement):
    _name = 'tag.head'

    def reduce(self, site=None):
        self._reduce_children(site)
        if not self._children:
            return None
        return super(DHeadElement, self).reduce(site)


class DBodyElement(ConsumeTmplMixin, DPageElement):
    _name = 'tag.body'
    _inherit = 'any'

    def reduce(self, site=None):
        self._reduce_children(site)
        return super(DBodyElement, self).reduce(site)


class ScriptElement(DPageElement):
    _name = 'tag.script'
    _consume_in = ()  # Not allowed anywhere, so far


class DLinkObject(DPageElement):
    _name = 'tag.link'
    _inherit = '.base.link'
    _consume_in = (DHeadElement,)


class DTemplateElement(DPageElement):
    """A template defines reusable DOM that is not normally rendered/scanned

        See: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/template

        Likewise, the template will be re-used in this parser, match remote
        DOM and generate same proxy elements, under their caller.
    """

    _name = 'tag.template'
    _inherit = '.domContainer'
    _consume_in = (DHeadElement, DBodyElement, )
    _attrs_map = { 'id': ('this_id', str, AttributeError),
                 }


    def __init__(self, tag, attrs):
        super(DTemplateElement, self).__init__(tag)
        self._parse_attrs(attrs)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        """A template is never parsed at its original DOM location
        """
        return ()

    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        return self._iter_items_cont(remote, scope, xpath_prefix)


class DSlotElement(DPageElement):
    """The contents of a <slot> are replaced by parent scope, if available
    
        This resembles the official W3C definition of slots in the browser,
        meant to be a placeholder for content that can be customized within
        a template.
    """
    _name = 'tag.slot'
    _inherit = '.domContainer'
    _attrs_map = { 'name': ('this_name', str, AttributeError),
                 }

    def __init__(self, tag, attrs):
        super(DSlotElement, self).__init__(tag)
        self._parse_attrs(attrs)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        target = scope.slots.get(self.this_name, None)
        if target is not None:
            scope = scope.child()
            scope.slot_caller = self
            return target._locate_in(remote, scope, xpath_prefix, match)
        else:
            return self._iter_items_cont(remote, scope, xpath_prefix, match)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        target = scope.slots.get(self.this_name, None)
        if target is not None:
            scope = scope.child()
            scope.slot_caller = self
            return target._locate_attrs(webelem, scope, xpath_prefix)
        else:
            return self.iter_child_attrs(webelem, scope, xpath_prefix)

    def iter_child_attrs(self, webelem, scope, xpath_prefix=''):
        for ch in self._children:
            for y2 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y2


class DSlotContentElement(DPageElement):
    """Jump back to the content of calling '<slot>' element

        Example::

            <div class="slot">
                <slot name="foo">
                    <div class="content">
                    </div>
                </slot>
            </div>

            <div slot="foo" class="bar">
                <middle>
                    <pe-slotcontent/>
                </middle>
            </div>

        Should be equivalent to::

            <div class="slot">
                <div class="bar">
                    <middle>
                        <div class="content"></div>
                    </middle>
                </div>
            </div>


        This is inspired by Jinja2 'caller' concept:
            http://jinja.pocoo.org/docs/2.10/templates/#call
    """
    _name = 'tag.pe-slotcontent'
    is_empty = True
    _consume_in = (DomContainerElement,)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        try:
            slot = scope.slot_caller
        except AttributeError:
            return
        return slot._iter_items_cont(remote, scope, xpath_prefix=xpath_prefix, match=match)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        try:
            slot = scope.slot_caller
        except AttributeError:
            return
        return slot.iter_child_attrs(webelem, scope, xpath_prefix)


class DUseTemplateElem(DPageElement):
    _name = 'tag.use-template'
    _inherit = '.domContainer'

    _attrs_map = { 'id': ('template_id', str, AttributeError),
                 }

    def __init__(self, tag, attrs):
        super(DUseTemplateElem, self).__init__(tag)
        self._parse_attrs(attrs)
        self._by_slot = {}

    def consume(self, element):
        dom_slot = getattr(element, '_dom_slot', NotImplemented)
        if dom_slot is NotImplemented:
            raise ValueError('Use-template cannot consume %s' % (element._name))

        if not dom_slot:
            raise ValueError('Use-template can only have sub-elements with slot= defined '
                             'Cannot consume a %s' % element)

        if dom_slot in self._by_slot:
            raise ValueError('Slot "%s" already defined' % element._dom_slot)
        self._by_slot[dom_slot] = element

    def iter_items(self, remote, xpath_prefix='', match=None):
        raise RuntimeError('should not be referenced by DOM component')

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        raise RuntimeError('should not be referenced by DOM component')

    def _locate_in(self, remote, scope, xpath_prefix, match):
        # Proxy to actual template. Locate that one and iterate that
        tmpl = scope.get_template(self.template_id)
        scp2 = DOMScope.new(parent=scope)
        scp2.slots = self._by_slot
        return tmpl.iter_items(remote, scp2, xpath_prefix, match)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        tmpl = scope.get_template(self.template_id)
        scp2 = DOMScope.new(parent=scope)
        scp2.slots = self._by_slot
        return tmpl.iter_attrs(webelem, scp2, xpath_prefix)


class DBaseHtmlObject(DPageElement):
    _name = '.basehtml'
    _consume_in = (DSiteCollection,)

    def __init__(self, tag, attrs):
        super(DBaseHtmlObject, self).__init__(tag, attrs)
        self._templates = {}

    def consume(self, element):
        if isinstance(element, ConsumeTmplMixin):
            for tmpl in element._tmp_templates:
                if tmpl.this_id in self._templates:
                    raise HTMLParseError("Template id='%s' already registered" % tmpl.this_id,
                                         position=tmpl.pos)
                self._templates[tmpl.this_id] = tmpl
            element._tmp_templates = []
        super(DBaseHtmlObject, self).consume(element)


class DHtmlObject(DPageElement):
    """Consume the <html> element as top-level site page

    """
    _name = 'tag.html'
    _inherit = '.basehtml'

    def reduce(self, site=None):
        self._reduce_children(site)
        return super(DHtmlObject, self).reduce(site)

    def iter_items(self, remote, scope, xpath_prefix='', match=None):
            return self._iter_items_cont(remote, scope, xpath_prefix='//', match=match)

    def walk(self, webdriver, parent_scope=None, max_depth=1000, on_missing=None,
             starting_path=None):
        """Discover all interesting elements within webdriver current page+scope

            :param on_missing: function to call like `fn(comp, e)` when ElementNotFound
                               is raised under component=comp
            :param path: list of elements to enter before walking

            Iterator, yielding (path, Component) pairs, traversing depth first
        """
        if on_missing is None:
            on_missing = lambda c, e: None

        comp = self.get_root(webdriver, parent_scope)
        if starting_path:
            try:
                for p in starting_path:
                    comp = comp[p]
            except (ElementNotFound, KeyError) as e:
                on_missing(comp, e)
                return

        stack = [((), comp)]
        while stack:
            path, comp = stack.pop()
            yield path, comp
            if len(path) < max_depth:
                try:
                    celems = [(path + (n,), c) for n, c in comp.items()]
                    celems.reverse()
                    stack += celems
                except ElementNotFound as e:
                    if on_missing(comp, e):
                        continue
                    raise

    def get_root(self, webdriver, parent_scope=None):
        """Obtain a proxy to the root DOM of remote WebDriver, bound to this template
        """
        from .dom_components import PageProxy
        if parent_scope is not None:
            klsname = parent_scope.site_config.get('page_controller', 'page')
        else:
            klsname = 'page'
        new_scope = DOMScope[klsname](parent=parent_scope, templates=self._templates)
        return PageProxy(self, webdriver, scope=new_scope)


class GHtmlObject(DPageElement):
    """Handle the <html> element of a gallery file

    """
    _name = 'gallery.html'
    _inherit = '.basehtml'

    def reduce(self, site=None):
        logger = logging.getLogger(__name__ + '.GHtmlObject')
        if isinstance(site, DSiteCollection):
            for tn in self._templates.keys():
                if tn in site._templates:
                    logger.warning("Template id=%s already in gallery: %s",
                                   tn, site.cur_file)
            site._templates.update(self._templates)
            return None
        else:
            return super(GHtmlObject, self).reduce(site)


class DPageObject(DPageElement):
    """HTML page embedded as a sub-element of <html>

        This would behave like a <html> but can be nested inside a file,
        unlike <html> element that is unique per file.
    """
    _name = 'tag.htmlpage'
    _inherit = 'tag.html'
    _consume_in = ()  # TODO

    def __init__(self, tag=None, attrs=()):
        super(DPageObject, self).__init__(tag, attrs)


DHeadElement._consume_in = (DHtmlObject,)
DBodyElement._consume_in = (DHtmlObject,)


class GHeadElement(ConsumeTmplMixin, DPageElement):
    _name = 'gallery.head'
    _consume_in = (GHtmlObject,)


class GBodyElement(ConsumeTmplMixin, DPageElement):
    _name = 'gallery.body'
    _consume_in = (GHtmlObject,)


DTemplateElement._consume_in += (GHeadElement, GBodyElement)
DataElement._consume_in += (DomContainerElement, RegexElement, PeDataElement)


class PageParser(BaseDPOParser):
    CDATA_CONTENT_ELEMENTS = BaseDPOParser.CDATA_CONTENT_ELEMENTS + ('pe-regex', 'pe-data')
    logger = logging.getLogger(__name__ + '.PageParser')

    def __init__(self, root_element):
        assert isinstance(root_element, DPageElement)
        super(PageParser, self).__init__(root_element)

    def handle_starttag(self, tag, attrs):
        self._pop_empty()
        attr_this = None
        for k, v in attrs:
            if k == 'this':
                attr_this = v
                break

        if attr_this is not None:
            order = ['named.' + tag, 'tag.' + tag, 'named']
        else:
            order = ['tag.' + tag, 'any']
        try:
            elem = DPageElement.get_class(order)(tag, attrs)
        except ValueError as e:
            raise HTMLParseError(six.text_type(e), position=self.getpos())

        elem.pos = self.getpos()
        self._dom_stack.append(elem)

    def handle_data(self, data):
        sdata = data.strip()
        if not sdata:
            return

        self._pop_empty()
        stripped = (sdata != data)

        if sdata.startswith('[') and sdata.endswith(']'):
            data = sdata[1:-1]
            if data.startswith('[') and data.endswith(']'):
                # Quoting for [] expressions
                elem = DataElement.new(data)
            else:
                if not data:
                    data = 'text'   # hard code "[ ]" to "[ text ]"

                if not word_re.match(data):
                    raise ValueError("Invalid expression: %s" % data)

                elem = Text2AttrElement.new(data, strip=stripped)
        else:
            elem = DataElement.new(data)

        elem.pos = self.getpos()
        self._dom_stack.append(elem)


class GalleryParser(PageParser):
    logger = logging.getLogger(__name__ + '.GalleryParser')

    def handle_starttag(self, tag, attrs):
        if tag in ('html', 'head', 'body'):
            # these need to be overriden, only
            try:
                elem = DPageElement.get_class('gallery.' + tag)(tag, attrs)
            except ValueError as e:
                raise HTMLParseError(six.text_type(e), position=self.getpos())
            elem.pos = self.getpos()
            self._dom_stack.append(elem)
        else:
            super(GalleryParser, self).handle_starttag(tag, attrs)


#eof

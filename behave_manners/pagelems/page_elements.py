# -*- coding: UTF-8 -*-

import logging
import re
from collections import defaultdict

from .helpers import textescape, prepend_xpath, word_re
from .base_parsers import DPageElement, DataElement, BaseDPOParser, \
                          HTMLParseError, DOMScope
from .site_collection import DSiteCollection
from .exceptions import ElementNotFound
from selenium.common.exceptions import NoSuchElementException


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


DomContainerElement._consume_in = (DomContainerElement, )
DataElement._consume_in += (DomContainerElement,)


def _attr_getter(attr):
    return lambda w: w.get_attribute(attr)


class AnyElement(DPageElement):
    _name = 'tag.pe-any'
    _inherit = '.domContainer'

    def __init__(self, tag, attrs, any_tag='*'):
        super(AnyElement, self).__init__(tag)
        match_attrs = defaultdict(list)
        self.read_attrs = {}
        self._xpath = any_tag
        self._pe_class = None
        self._dom_slot = None
        self._split_attrs(attrs, match_attrs, self.read_attrs)
        self._xpath_score = 0
        self._set_match_attrs(match_attrs)

    def _set_match_attrs(self, match_attrs):
        for k, vs in match_attrs.items():
            if len(vs) > 1:
                raise NotImplementedError('Dup arg: %s' % k)
            if vs[0] is True:
                # only match existence of attribute
                self._xpath += '[@%s]' % (k,)
            elif vs[0].startswith('+'):
                val = vs[0][1:]
                self._xpath += '[contains(@%s,%s)]' % (k, textescape(val))
            else:
                self._xpath += '[@%s=%s]' % (k, textescape(vs[0]))
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
                read_attrs[v or k] = _attr_getter(k)
            else:
                assert '.' not in k, k
                # attribute to match as locator
                match_attrs[k].append(v)

    def reduce(self):
        if len(self._children) == 1 \
                and self._name in ('any', 'tag.pe-any') \
                and not self.read_attrs \
                and self._dom_slot is None \
                and isinstance(self._children[0], NamedElement):
            # Merge Named element with self (its parent)
            ret = self._children[0]
            ret._xpath = prepend_xpath(self._xpath + '/', ret._xpath)
            ret._reset_xpath_locator()
            return ret
        return self

    def xpath_locator(self, score, top=False):
        locator = ''
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

    def _locate_in(self, remote, scope, xpath_prefix):
        xpath2 = prepend_xpath(xpath_prefix, self.xpath)
        enoent = True
        for welem in remote.find_elements_by_xpath(xpath2):
            # Stop at first 'welem' that yields any children results
            try:
                nscope = scope
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)

                ret = list(self.iter_items(welem, nscope))
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

        if enoent:
            if enoent is True:
                # No element matched xpath2, loop above didn't run
                enoent = ElementNotFound(selector=xpath2, parent=remote)
            raise enoent

    def iter_items(self, remote, scope, xpath_prefix=''):
        return self._iter_items_cont(remote, scope, xpath_prefix)

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for k, fn in self.read_attrs.items():
            yield k, xpath_prefix, fn, None
        for ch in self._children:
            for y4 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y4

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


class Text2AttrElement(DPageElement):
    _name = 'text2attr'
    is_empty = True
    _consume_in = (DomContainerElement,)

    def __init__(self, name):
        super(Text2AttrElement, self).__init__()
        self._attr_name = name

    def consume(self, element):
        raise TypeError('Data cannot consume %r' % element)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        yield self._attr_name, xpath_prefix, lambda w: w.text or w.get_attribute('innerText'), None


class NamedElement(DPageElement):
    _name = 'named'
    _inherit = 'any'

    def __init__(self, tag, attrs):
        super(NamedElement, self).__init__(tag, attrs)

        # parse `this_name` into dynamic function
        pattern = self.this_name
        if pattern.startswith('[') and pattern.endswith(']'):
            pattern = pattern[1:-1].strip()
            if not word_re.match(pattern):
                raise NotImplementedError("Cannot parse expression '%s'" % pattern)

            self._this_fn = self.__get_pattern_resolver(pattern)
        elif '%s' in pattern or '%d' in pattern:
            self._this_fn = lambda n, x, c: pattern % n
        else:
            # plain name, no iteration
            self._this_fn = lambda *a: pattern

    def __get_pattern_resolver(self, pattern):
        """Closure for computing item name based on attributes

            :param pattern: name of attribute to resolve
        """
        def _resolver(n, welem, scope):
            for name, xpath, getter, s in self.iter_attrs(welem, scope):
                if name == pattern:
                    if xpath:
                        welem = welem.find_element_by_xpath(xpath)
                    ret = getter(welem)
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

    def _locate_in(self, remote, scope, xpath_prefix):
        xpath = prepend_xpath(xpath_prefix, self.xpath)
        n = 0
        enofound = None
        for welem in remote.find_elements_by_xpath(xpath):
            try:
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)
                else:
                    nscope = scope
                yield self._this_fn(n, welem, nscope), welem, self, nscope
            except NoSuchElementException, e:
                enofound = ElementNotFound(msg=str(e), parent=welem, selector='*')
            n += 1
        if not n:
            if enofound is None:
                enofound = ElementNotFound(parent=remote, selector=xpath)
            raise enofound

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        # Stop traversing, no attributes exposed from this to parent
        return ()


class InputElement(DPageElement):
    _name = 'tag.input'
    _inherit = 'any'
    is_empty = True

    class _InputValueActor(object):
        def __init__(self, xpath):
            self._xpath = xpath

        def _elem(self, welem):
            if self._xpath:
                ielem = welem.find_element_by_xpath(self._xpath)
            else:
                ielem = welem
            return ielem

    class InputValueGetter(_InputValueActor):

        def __call__(self, welem):
            return self._elem(welem).get_attribute('value')

    class InputValueSetter(_InputValueActor):
        def __init__(self, xpath):
            self._xpath = xpath

        def __call__(self, welem, value):
            driver = welem.parent
            driver.execute_script("arguments[0].setAttribute('value', arguments[1]);",
                                  self._elem(welem), value)

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
        for y4 in super(InputElement, self).iter_attrs(webelem, scope, xpath_prefix):
            yield y4
        if self.this_name:
            yield ('value', xpath_prefix,
                       self.InputValueGetter(''),
                       self.InputValueSetter(''))

    def _locate_in(self, remote, scope, xpath_prefix):
        if self.this_name:
            enoent = True
            xpath2 = prepend_xpath(xpath_prefix, self.xpath)
            for welem in remote.find_elements_by_xpath(xpath2):
                nscope = scope
                if self._pe_class is not None:
                    nscope = self._pe_class(parent=scope)
                enoent = False
                yield self.this_name, welem, self, nscope
            if enoent:
                raise ElementNotFound(parent=remote, selector=xpath2)
        else:
            return

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        if not self.this_name:
            # expose self as attribute
            if self.name_attr == '*':
                # Active remote iteration here, must discover all <input> elements
                # and yield as many attributes
                for relem in webelem.find_elements_by_xpath(prepend_xpath(xpath_prefix, self.xpath)):
                    rname = relem.get_attribute('name')
                    xpath = self._xpath + "[@name=%s]" % textescape(rname)
                    yield (rname, xpath_prefix,
                           self.InputValueGetter(xpath),
                           self.InputValueGetter(xpath))
            else:
                # Avoid iteration, yield attribute immediately
                yield (self.name_attr, xpath_prefix,
                       self.InputValueGetter(self._xpath),
                       self.InputValueSetter(self._xpath))


class DeepContainObj(DPageElement):
    _name = 'tag.pe-deep'
    _inherit = '.domContainer'

    def __init__(self, tag, attrs):
        if attrs:
            raise ValueError('Deep cannot have attributes')
        super(DeepContainObj, self).__init__(tag)

    def reduce(self):
        if len(self._children) == 1 and self._children[0]._name in ('any', 'tag.pe-any', 'named'):
            ch = self._children.pop()
            ch._xpath = prepend_xpath('.//', ch._xpath)
            ch._reset_xpath_locator()
            return ch
        return self

    def iter_items(self, remote, scope, xpath_prefix=''):
        return self._iter_items_cont(remote, scope, xpath_prefix='.//')

    def _locate_in(self, remote, scope, xpath_prefix):
        return self._iter_items_cont(remote, scope, xpath_prefix='.//')

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix='.//'):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for ch in self._children:
            for y4 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y4

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

    def iter_items(self, remote, scope, xpath_prefix=''):
        return self._iter_items_cont(remote, scope, xpath_prefix='//')

    def _locate_in(self, remote, scope, xpath_prefix):
        return self._iter_items_cont(remote, scope, xpath_prefix='//')

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix='//'):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for ch in self._children:
            for y4 in ch._locate_attrs(webelem, scope, xpath_prefix):
                yield y4

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix='//'):
        return self.iter_attrs(webelem, scope, prepend_xpath(xpath_prefix, self.xpath))

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

    def reduce(self):
        if not self._children:
            raise ValueError("<Repeat> must have contained elements")

        if len(self._children) > 1:
            raise NotImplementedError("Cannot handle siblings in <Repeat>")  # yet

        self._reset_xpath_locator()
        return self

    def iter_items(self, remote, scope, xpath_prefix=''):
        ni = 0
        seen = set()
        enofound = None
        try:
            for name, welem, ptmpl, scp in self._children[0] \
                    ._locate_in(remote, scope, xpath_prefix):
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
        if ni < self.min_elems:
            if enofound is None:
                raise ElementNotFound(parent=remote, selector=xpath_prefix)
            else:
                raise enofound

    def _locate_in(self, remote, scope, xpath_prefix=''):
        # If this has a name, return new container Component,
        # else just iterate contents
        if self.this_name:
            yield self.this_name, remote, self, scope
        else:
            for y4 in self.iter_items(remote, scope, xpath_prefix):
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

    def _locate_in(self, remote, scope, xpath_prefix):
        enofound = None
        nfound = 0
        seen = set()
        for ch in self._children:
            # Stop at first 'welem' that yields any children results
            try:
                for n, welem, p, scp in ch._locate_in(remote, scope, xpath_prefix):
                    if welem in seen:
                        continue
                    seen.add(welem)
                    yield n, welem, p, scp
                    nfound += 1
            except ElementNotFound as e:
                if enofound is None:
                    enofound = e

        if not nfound:
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

    def _locate_in(self, remote, scope, xpath_prefix):
        ret = []

        # get all sub-components in one go
        seen = set()
        nscope = scope
        if self._pe_class is not None:
            nscope = self._pe_class(parent=scope)
        for ch in self._children:
            for y4 in ch._locate_in(remote, nscope, xpath_prefix):
                if y4[0] in seen:
                    continue
                ret.append(y4)
                seen.add(y4[0])

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


class DBodyElement(ConsumeTmplMixin, DPageElement):
    _name = 'tag.body'
    _inherit = 'any'


class ScriptElement(DPageElement):
    _name = 'tag.script'
    _consume_in = ()  # Not allowed anywhere, so far


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

    def _locate_in(self, remote, scope, xpath_prefix):
        """A template is never parsed at its original DOM location
        """
        return ()

    def iter_items(self, remote, scope, xpath_prefix=''):
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

    def _locate_in(self, remote, scope, xpath_prefix):
        this = scope.slots.get(self.this_name, super(DSlotElement, self))
        return this._locate_in(remote, scope, xpath_prefix)

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        this = scope.slots.get(self.this_name, super(DSlotElement, self))
        return this._locate_attrs(webelem, scope, xpath_prefix)


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
        if not isinstance(element, AnyElement):
            raise ValueError('Use-template cannot consume %s' % (element._name))
        if not element._dom_slot:
            raise ValueError('Use-template can only have sub-elements with slot= defined '
                             'Cannot consume a %s' % element)

        if element._dom_slot in self._by_slot:
            raise ValueError('Slot "%s" already defined' % element._dom_slot)
        self._by_slot[element._dom_slot] = element

    def iter_items(self, remote, xpath_prefix=''):
        raise RuntimeError('should not be referenced by DOM component')

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        raise RuntimeError('should not be referenced by DOM component')

    def _locate_in(self, remote, scope, xpath_prefix):
        # Proxy to actual template. Locate that one and iterate that
        tmpl = scope.get_template(self.template_id)
        scp2 = DOMScope.new(parent=scope)
        scp2.slots = self._by_slot
        return tmpl.iter_items(remote, scp2, xpath_prefix)

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
        if site is not None:
            nchildren = []
            for celem in self._children:
                try:
                    ncelem = celem.reduce(site)
                    if ncelem is not None:
                        nchildren.append(ncelem)
                except TypeError:
                    nchildren.append(celem)

            self._children[:] = nchildren     # inplace

        return super(DHtmlObject, self).reduce()

    def iter_items(self, remote, scope, xpath_prefix=''):
            return self._iter_items_cont(remote, scope, xpath_prefix='//')

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
            except ElementNotFound as e:
                on_missing(comp, e)
                return
            except KeyError as e:
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
            return super(GHtmlObject, self).reduce()


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


class PageParser(BaseDPOParser):
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
        except ValueError, e:
            raise HTMLParseError(unicode(e), position=self.getpos())

        elem.pos = self.getpos()
        self._dom_stack.append(elem)

    def handle_data(self, data):
        if not data.strip():
            return

        self._pop_empty()
        if data.startswith('[') and data.endswith(']'):
            data = data[1:-1].strip()
            if data.startswith('[') and data.endswith(']'):
                # Quoting for [] expressions
                elem = DataElement.new(data)
            else:
                if not data:
                    data = 'text'   # hard code "[ ]" to "[ text ]"

                if not word_re.match(data):
                    raise ValueError("Invalid expression: %s" % data)

                elem = Text2AttrElement.new(data)
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
            except ValueError, e:
                raise HTMLParseError(unicode(e), position=self.getpos())
            elem.pos = self.getpos()
            self._dom_stack.append(elem)
        else:
            super(GalleryParser, self).handle_starttag(tag, attrs)


#eof

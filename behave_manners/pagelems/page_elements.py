# -*- coding: UTF-8 -*-

import logging
from collections import defaultdict

from .helpers import textescape, prepend_xpath, word_re
from .base_parsers import DPageElement, DataElement, BaseDPOParser, HTMLParseError


class AnyElement(DPageElement):
    _name = 'tag.anyelement'

    def __init__(self, tag, attrs):
        super(AnyElement, self).__init__(tag)
        match_attrs = defaultdict(list)
        self.read_attrs = {}
        self._split_attrs(attrs, match_attrs, self.read_attrs)
        self._xpath = '*'
        self._set_match_attrs(match_attrs)

    def _set_match_attrs(self, match_attrs):
        for k, vs in match_attrs.items():
            if len(vs) > 1:
                raise NotImplementedError('Dup arg: %s' % k)
            self._xpath += '[@%s=%s]' % (k, textescape(vs[0]))

    def _split_this(self, value, sub=None):
        raise RuntimeError('%s passed \'this\'' % self.__class__.__name__)
    
    def _split_attrs(self, attrs, match_attrs, read_attrs):
        for k, v in attrs:
            if k == 'this':
                self._split_this(v)
            elif v.startswith('[') and v.endswith(']'):
                assert '.' not in k, k   # TODO
                # attribute to read value from
                if k in read_attrs:
                    raise ValueError('Attribute defined more than once: %s' % k)
                v = v[1:-1].strip()
                read_attrs[v or k] = lambda w: w.get_attribute(k)
            else:
                assert '.' not in k, k
                # attribute to match as locator
                match_attrs[k].append(v)

    def reduce(self):
        if len(self._children) == 1 \
                and not isinstance(self, NamedElement) \
                and not self.read_attrs \
                and isinstance(self._children[0], NamedElement):
            # Merge Named element with self (its parent)
            ret = self._children[0]
            ret._xpath = prepend_xpath(self._xpath + '/', ret._xpath)
            return ret
        for child in self._children:
            for clause in child.must_have():
                self._xpath += '[' + clause + ']'
        return self
    
    @property
    def xpath(self):
        return self._xpath

    def _locate_in(self, remote, xpath_prefix):
        found = False
        for welem in remote.find_elements_by_xpath(prepend_xpath(xpath_prefix, self._xpath)):
            for y3 in self.iter_items(welem, xpath_prefix):
                yield y3
                found = True
            # Stop at first 'welem' that yields any children results
            if found:
                break

    def iter_items(self, remote, xpath_prefix=''):
        return self._iter_items_cont(remote, xpath_prefix)

    def iter_attrs(self, webelem=None, xpath_prefix=''):
        """Iterate names of possible attributes

            returns iterator of (name, getter, setter)
        """
        for k, fn in self.read_attrs.items():
            yield k, xpath_prefix, fn, None
        for ch in self._children:
            for y4 in ch._locate_attrs(webelem, xpath_prefix):
                yield y4

    def _locate_attrs(self, webelem=None, xpath_prefix=''):
        return self.iter_attrs(webelem, prepend_xpath(xpath_prefix, self.xpath))


class GenericElement(DPageElement):
    _name = 'any'
    _inherit = 'tag.anyelement'
    
    def __init__(self, tag, attrs):
        super(GenericElement, self).__init__(tag, attrs)
        self._xpath = tag + self._xpath[1:]  # no '/', _xpath is clauses on same element


class _LeafElement(DPageElement):
    # TODO
    _name = '.leaf'
    _inherit = 'any'
    
    def consume(self, element):
        raise TypeError('%s cannot consume %r' % (self._name, element))



class Text2AttrElement(DPageElement):
    _name = 'text2attr'
    
    def __init__(self, name):
        super(Text2AttrElement, self).__init__()
        self._attr_name = name

    def consume(self, element):
        raise TypeError('Data cannot consume %r' % element)

    def _locate_attrs(self, webelem=None, xpath_prefix=''):
        yield self._attr_name, xpath_prefix, lambda w: w.text, None


class NamedElement(DPageElement):
    _name = 'named'
    _inherit = 'any'

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

    def _locate_in(self, remote, xpath_prefix):
        for welem in remote.find_elements_by_xpath(prepend_xpath(xpath_prefix, self._xpath)):
            yield self.this_name, welem, self

    def _locate_attrs(self, webelem=None, xpath_prefix=''):
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

        for k, vs in match_attrs.items():
            if len(vs) > 1:
                raise NotImplementedError('Dup arg: %s' % k)
            self._xpath += '[@%s=%s]' % (k, textescape(vs[0]))

    def consume(self, element):
        raise TypeError('Input cannot consume %r' % element)
    
    def iter_items(self, remote, xpath_prefix=''):
        # no children, nothing to return
        return []

    def iter_attrs(self, webelem=None, xpath_prefix=''):
        return []

    def _locate_in(self, remote, xpath_prefix):
        if self.this_name:
            for welem in remote.find_elements_by_xpath(prepend_xpath(xpath_prefix, self._xpath)):
                yield self.this_name, welem, self
        else:
            return
    
    def _locate_attrs(self, webelem=None, xpath_prefix=''):
        if not self.this_name:
            # expose self as attribute
            if self.name_attr == '*':
                # Active remote iteration here, must discover all <input> elements
                # and yield as many attributes
                for relem in webelem.find_elements_by_xpath(prepend_xpath(xpath_prefix, self._xpath)):
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


class MustContain(DPageElement):
    _name = 'tag.mustcontain'
    
    @property
    def xpath(self):
        return ''

    def must_have(self):
        print "must have of ", self
        # is ./ needed?
        return [ prepend_xpath('./', ch.xpath) for ch in self._children]


class DeepContainObj(DPageElement):
    _name = 'tag.deep'

    def __init__(self, tag, attrs):
        if attrs:
            raise ValueError('Deep cannot have attributes')
        super(DeepContainObj, self).__init__(tag)

    @property
    def xpath(self):
        return './/'

    def reduce(self):
        if len(self._children) == 1 and isinstance(self._children[0], AnyElement):
            ch = self._children.pop()
            ch._xpath = prepend_xpath('.//', ch._xpath)
            return ch
        return self

    def iter_items(self, remote, xpath_prefix=''):
        return self._iter_items_cont(remote, xpath_prefix='.//')


class RepeatObj(DPageElement):
    _name = 'tag.repeat'
    
    _attrs_map = {'min': ('min_elems', int, 0),
                  'max': ('max_elems', int, 1000000),
                  'this': ('this_name', str, '')
                  }

    def __init__(self, tag, attrs):
        super(RepeatObj, self).__init__(tag)
        self._parse_attrs(attrs)

    def reduce(self):
        if not self._children:
            raise ValueError("<Repeat> must have contained elements")
        
        if len(self._children) > 1:
            raise NotImplementedError("Cannot handle siblings in <Repeat>")  # yet

        # Check top child
        ch = self._children[0]
        if isinstance(ch, NamedElement):
            pass
        elif isinstance(ch, AnyElement):
            # convert to NamedElement
            name = ''
            if 'id' in ch.read_attrs:
                name = '[id]'
            nch = NamedElement.new(ch.tag, [])
            nch.this_name = name
            nch._xpath = ch._xpath
            nch.read_attrs = ch.read_attrs
            nch._children = ch._children[:]
            self._children[0] = nch
        else:
            raise ValueError("<Repeat> cannot contain %s" % ch._name)
        return self

    def must_have(self):
        print "must have of ", self
        return [ './' + ch.xpath for ch in self._children]

    def iter_items(self, remote, xpath_prefix=''):
        pattern = self._children[0].this_name   # assuming NamedElement, so far
        if not pattern:
            pfun = lambda n, x: n
        elif pattern.startswith('[') and pattern.endswith(']'):
            pattern = pattern[1:-1].strip()
            if not word_re.match(pattern):
                raise NotImplementedError("Cannot parse expression '%s'" % pattern)
            #pfun = lambda n, x: self._children[0].get_attr(pattern, x) or str(n)
            pfun = lambda n, x: x.get_attribute(pattern)
        elif '%s' in pattern or '%d' in pattern:
            pfun = lambda n, x: pattern % n
        else:
            # suffix
            pfun = lambda n, x: pattern + str(n)

        ni = 0
        for name, welem, ptmpl in self._children[0]._locate_in(remote, xpath_prefix):
            yield pfun(ni, welem), welem, ptmpl
            ni += 1
            if ni > self.max_elems:
                break
        if ni < self.min_elems:
            raise Exception('Not enough children')

    def _locate_in(self, remote, xpath_prefix=''):
        # If this has a name, return new container Component,
        # else just iterate contents
        if self.this_name:
            yield self.this_name, remote, self
        else:
            for y3 in self.iter_items(remote, xpath_prefix):
                yield y3


class DHtmlObject(DPageElement):
    """Consume the <html> element as top-level site page
    
    """
    _name = 'tag.html'
    
    # TODO
    
    def reduce(self, site=None):
        if site is not None:
            i = 0
            while i < len(self._children):
                celem = self._children[i]
                if not isinstance(celem, DHtmlObject):
                    i += 1
                    continue
                ncelem = celem.reduce(site)
                if ncelem is not celem:
                    self._children.pop(i)
                    if ncelem is not None:
                        self._children.insert(i, ncelem)
                if ncelem is not None:
                    i += 1

        return super(DHtmlObject, self).reduce()

    def iter_items(self, remote, xpath_prefix=''):
        return self._iter_items_cont(remote, xpath_prefix='//')

    def walk(self, webdriver, max_depth=1000):
        """Discover all interesting elements within webdriver current page+context
        
            Iterator, yielding (path, Component) pairs, traversing depth first
        """
        stack = [((), self.get_root(webdriver))]
        while stack:
            path, comp = stack.pop()
            yield path, comp
            if len(path) < max_depth:
                celems = [(path + (n,), c) for n, c in comp.iteritems()]
                celems.reverse()
                stack += celems

    def get_root(self, webdriver):
        """Obtain a proxy to the root DOM of remote WebDriver, bound to this template
        """
        from .dom_components import PageProxy
        return PageProxy(self, webdriver)


class DPageObject(DPageElement):
    """HTML page embedded as a sub-element of <html>
    
        This would behave like a <html> but can be nested inside a file,
        unlike <html> element that is unique per file.
    """
    _name = 'tag.htmlpage'
    _inherit = 'tag.html'

    def __init__(self, tag=None, attrs=()):
        super(DPageObject, self).__init__(tag, attrs)



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


#eof

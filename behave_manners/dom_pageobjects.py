# -*- coding: UTF-8 -*-
"""
"""

import logging
import six
from f3utils.service_meta import abstractmethod, _ServiceMeta
from abc import abstractproperty
from collections import defaultdict
if six.PY2:
    from HTMLParser import HTMLParser as parser
else:
    from html import parser

from selenium.webdriver.common.by import By


class DPageElement(object):
    __metaclass__ = _ServiceMeta
    tag = ''

    def __init__(self, tag=None, attrs=()):
        self.pos = None
        self.tag = tag
        self._children = []

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.tag)

    def consume(self, element):
        assert isinstance(element, DPageElement), repr(element)
        element = element.reduce()
        if isinstance(element, DataElement) and self._children \
                and isinstance(self._children[-1], DataElement):
            self._children[-1].append(element)
        else:
            self._children.append(element)

    def reduce(self):
        """Cleanup internally, possibly merging nested elements
        """
        return self

    @abstractproperty
    def xpath(self):
        """Obtain selenium locator for this element
        """
        raise NotImplementedError

    def pretty_dom(self):
        """Walk this template, generate (indent, name, xpath) sets of each node
        
            Used for debugging, pretty-printing of parsed structure
        """
        #return []
        for c in self._children:
            for pd in c.pretty_dom():
                yield pd

    def must_have(self):
        """Return clauses of must-have elements

            :return: list
        """
        return []


class AnyElement(DPageElement):
    _name = 'tag.AnyElement'

    def __init__(self, tag, attrs):
        super(AnyElement, self).__init__(tag)
        match_attrs = defaultdict(list)
        self.read_attrs = {}
        self._split_attrs(attrs, match_attrs, self.read_attrs)
        self._xpath = ''
        for k, vs in match_attrs.items():
            if len(vs) > 1:
                raise NotImplementedError('Dup arg: %s' % k)
            self._xpath += '[@%s=%s]' % (k, vs[0])

    def _split_attrs(self, attrs, match_attrs, read_attrs):
        for k, v in attrs:
            if k == 'this':
                raise RuntimeError('%s passed \'this\'' % self.__class__.__name__)
            elif v.startswith('[') and v.endswith(']'):
                assert '.' not in k, k   # TODO
                # attribute to read value from
                if k in read_attrs:
                    raise HTMLParseError('Attribute defined more than once: %s' % k,
                                         position=self.getpos())
            else:
                assert '.' not in k, k
                # attribute to match as locator
                match_attrs[k].append(_textescape(v))

    @property
    def xpath(self):
        return self._xpath

    def reduce(self):
        if len(self._children) == 1 \
                and not self.read_attrs \
                and isinstance(self._children[0], NamedElement):
            # Merge Named element with self (its parent)
            ret = self._children[0]
            ret._xpath = self._xpath + '/' + ret._xpath
            return ret
        for child in self._children:
            for clause in child.must_have():
                self._xpath += '[' + clause + ']'
        return self


class GenericElement(DPageElement):
    _name = 'any'
    _inherit = 'tag.AnyElement'
    
    def __init__(self, tag, attrs):
        super(GenericElement, self).__init__(tag, attrs)
        self._xpath = tag + self._xpath

    def finalize(self):
        pass  # TODO


class _LeafElement(DPageElement):
    # TODO
    _name = '.leaf'
    _inherit = 'any'
    def consume(self, element):
        raise TypeError('%s cannot consume %r' % (self._name, element))


def _textescape(tstr):
    if "'" not in tstr:
        return "'%s'" % tstr
    elif '"' not in tstr:
        return '"%s"' % tstr
    else:
        return "concat('" + "', '\"', '".join(tstr.split('"')) + "')"  # Perl alert!


class DataElement(DPageElement):
    _name = 'text'

    def __init__(self, data):
        super(DataElement, self).__init__()
        assert isinstance(data, six.string_types)
        self.data = data

    def consume(self, element):
        raise TypeError('Data cannot consume %r' % element)

    def append(self, other):
        assert isinstance(other, DataElement)
        self.data += other.data

    @property
    def xpath(self):
        raise NotImplementedError('xpath of text')

    def must_have(self):
        if self.data.startswith(' ') or self.data.endswith(' '):
            return ['contains(text(), %s)' % _textescape(self.data.strip())]
        else:
            return ['text()=%s' % _textescape(self.data)]


class NamedElement(DPageElement):
    _name = 'named'
    _inherit = 'any'
    def __init__(self, tag, attrs):
        nattrs = []
        for kv in attrs:
            if kv[0] == 'this':
                self.this_name = kv[1]
            else:
                nattrs.append(kv)
        super(NamedElement, self).__init__(tag, nattrs)

    def finalize(self):
        pass  # TODO

    def pretty_dom(self):
        """Walk this template, generate (indent, name, xpath) sets of each node
        """
        yield (0, self.this_name, self.xpath)
        for c in self._children:
            for i, n, x in c.pretty_dom():
                yield i+1, n, './' + x


class MustContain(DPageElement):
    _name = 'tag.mustcontain'
    
    @property
    def xpath(self):
        return ''

    def must_have(self):
        return [ './' + ch.xpath for ch in self._children]


class DPageObject(DPageElement):
    _name = 'pageObject'

    def __init__(self, tag=None, attrs=()):
        super(DPageObject, self).__init__(tag, attrs)

    def pretty_dom(self):
        """Walk this template, generate (indent, name, xpath) sets of each node
        """
        yield (0, None, '/')
        for c in self._children:
            for i, n, x in c.pretty_dom():
                yield i+1, n, x

    @property
    def xpath(self):
        return '/'


class DeepContainObj(DPageElement):
    _name = 'tag.deep'

    def __init__(self, tag, attrs):
        if attrs:
            raise ValueError('Deep cannot have attributes')
        super(DeepContainObj, self).__init__(tag)

    @property
    def xpath(self):
        return '//'

    def reduce(self):
        if len(self._children) == 1 and isinstance(self._children[0], AnyElement):
            ch = self._children.pop()
            ch._xpath = '/' + ch._xpath
            return ch
        return self


class SampleParser(parser, object):
    logger = logging.getLogger(__name__ + '.SampleParser')

    def __init__(self, root_element=None):
        super(SampleParser, self).__init__()
        self._dom_stack = []
        if root_element is not None:
            self._dom_stack.append(root_element)

    def handle_starttag(self, tag, attrs):
        attr_this = None
        for k, v in attrs:
            if k == 'this':
                attr_this = v
                break
    
        if attr_this is not None:
            try:
                elem = DPageElement['named.' + tag](tag, attrs)
            except TypeError:
                elem = DPageElement['named'](tag, attrs)
        else:
            try:
                elem = DPageElement['tag.' + tag](tag, attrs)
            except TypeError:
                elem = DPageElement['any'](tag, attrs)
        elem.pos = self.getpos()
        self._dom_stack.append(elem)

    def handle_endtag(self, tag):
        while self._dom_stack:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            prev.consume(closed)
            if closed.tag == tag:
                break

    def close(self):
        super(SampleParser, self).close()
        # consume remaining element
        while len(self._dom_stack) > 1:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            self.logger.warning("Missing </%s> tag at end of stream %d:%d ",
                                closed.tag, *self.getpos())
            prev.consume(closed)

    def handle_data(self, data):
        if not data.strip():
            return

        elem = DataElement.new(data)
        elem.pos = self.getpos()
        self._dom_stack.append(elem)

    def handle_charref(self, name):
        print "Encountered char ref :", repr(name)

    def handle_entityref(self, name):
        print "Encountered entity ref :", repr(name)
        raise NotImplementedError

    def handle_comment(self, data):
        print "Encountered comment :", repr(data)
        raise NotImplementedError

    def handle_decl(self, decl):
        print "Encountered comment :", repr(decl)
        raise NotImplementedError

    def handle_pi(self, data):
        raise NotImplementedError

    def unknown_decl(self, data):
        print "Encountered decl :", repr(data)
        raise ValueError()

    def get_result(self):
        if len(self._dom_stack) != 1:
            raise RuntimeError("get_result() called with %d items in stack" % \
                               len(self._dom_stack))
        return self._dom_stack.pop()


#eof

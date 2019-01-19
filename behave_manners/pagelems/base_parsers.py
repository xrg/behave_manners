# -*- coding: UTF-8 -*-

import six
from f3utils.service_meta import abstractmethod, _ServiceMeta
from .helpers import textescape

if six.PY2:
    from HTMLParser import HTMLParser as parser, HTMLParseError
else:
    from html import parser
    
    class HTMLParseError(Exception):
        """Exception raised for all parse errors."""

        def __init__(self, msg, position=(None, None)):
            assert msg
            self.msg = msg
            self.lineno = position[0]
            self.offset = position[1]

        def __str__(self):
            result = self.msg
            if self.lineno is not None:
                result = result + ", at line %d" % self.lineno
            if self.offset is not None:
                result = result + ", column %d" % (self.offset + 1)
            return result


class BaseDPOParser(parser, object):
    logger = None

    def __init__(self, root_element):
        super(BaseDPOParser, self).__init__()
        self._dom_stack = [root_element]

    def handle_endtag(self, tag):
        if len(self._dom_stack) < 2:
            if tag == 'html':
                return
            raise HTMLParseError("Invalid closing tag </%s> at root element" % tag,
                                 position=self.getpos())
        while self._dom_stack:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            prev.consume(closed)
            if closed.tag == tag:
                break

    def _pop_empty(self):
        if len(self._dom_stack) > 1 and self._dom_stack[-1].is_empty:
            closed = self._dom_stack.pop()
            self._dom_stack[-1].consume(closed)

    def close(self):
        super(BaseDPOParser, self).close()
        # consume remaining element
        while len(self._dom_stack) > 1:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            self.logger.warning("Missing </%s> tag at end of stream %d:%d ",
                                closed.tag, *self.getpos())
            prev.consume(closed)

    @abstractmethod
    def handle_starttag(self, tag, attrs):
        pass

    def handle_data(self, data):
        """Reject any non-whitespace text in elements
        """
        if not data.strip():
            return
        raise HTMLParseError("Text not allowed at this level: %r" % data[:5],
                        position=self.getpos())

    def handle_charref(self, name):
        print "Encountered char ref :", repr(name)

    def handle_entityref(self, name):
        print "Encountered entity ref :", repr(name)
        raise NotImplementedError

    def handle_comment(self, data):
        print "Encountered comment :", repr(data)
        # raise NotImplementedError

    def handle_decl(self, decl):
        raise HTMLParseError("Declaration not allowed at this level",
                             position=self.getpos())

    def handle_pi(self, data):
        raise HTMLParseError("Processing instruction not allowed at this level",
                             position=self.getpos())
        # TODO: include statement
        raise NotImplementedError

    def unknown_decl(self, data):
        raise HTMLParseError("Declaration not allowed at this level",
                        position=self.getpos())

    def get_result(self):
        if len(self._dom_stack) != 1:
            raise RuntimeError("get_result() called with %d items in stack" % \
                               len(self._dom_stack))
        return self._dom_stack.pop()


@six.add_metaclass(_ServiceMeta)
class DPageElement(object):
    tag = ''
    is_empty = False   # for elements that need no end tag

    def __init__(self, tag=None, attrs=()):
        self.pos = None
        self.tag = tag
        self._children = []

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.tag)

    def _parse_attrs(self, attrs):
        """Parse html attributes according to fixed class mapping

            This method is intended for `__init__()`, when a fixed set
            of attributes is expected.
            It assumes that class contains an `_attrs_map` entry, a dict,
            mapping `html_attr` to `(py_attr, type, default)`
        """
        expected = self.__class__._attrs_map.copy()
        for (k, v) in attrs:
            if k not in expected:
                raise ValueError('Unexpected attribute "%s" in <%s>' % (k, self.tag))
            py, typ, d = expected.pop(k)
            if typ:
                v = typ(v)
            setattr(self, py, v)

        for py, typ, d in expected.values():
            setattr(self, py, d)

    def consume(self, element):
        assert isinstance(element, DPageElement), repr(element)
        element = element.reduce()
        if element is None:
            return
        if isinstance(element, DataElement) and self._children \
                and isinstance(self._children[-1], DataElement):
            self._children[-1].append(element)
        else:
            self._children.append(element)

    def reduce(self):
        """Cleanup internally, possibly merging nested elements
        
            None can be returned, in case this element is no longer
            useful.
        """
        return self


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

    # Methods for Component Proxies
    def iter_items(self, remote, context, xpath_prefix=''):
        """Iterate possible children components
        
            :return: tuple (name, welem, ptmpl)
        """
        return
    
    def _iter_items_cont(self, remote, context, xpath_prefix=''):
        """Standard `iter_items()` implementation for containing components
        """
        seen_names = set()
        for ch in self._children:
            for n, w, p in ch._locate_in(remote, context, xpath_prefix):
                # Suppress duplicate names, only return first match
                if n not in seen_names:
                    yield n, w, p
                    seen_names.add(n)

    def _locate_in(self, remote, context, xpath_prefix):
        """Locate (possibly) this component under 'remote' webelem
        
            Called by the parent component, to resolve this.
            Returns tuple (name, welem, ptmpl)
        """
        return ()

    def iter_attrs(self, webelem=None, context=None, xpath_prefix=''):
        """Iterate names of possible attributes

            returns iterator of (name, xpath, getter, setter)
        """
        return ()

    def _locate_attrs(self, webelem=None, context=None, xpath_prefix=''):
        """Locate self and return our possible attributes

            To be called by parent to return possible attributes
            return: same as `iter_attrs()`
        """
        return ()


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

    def must_have(self):
        if self.data.startswith(' ') or self.data.endswith(' '):
            return ['contains(text(), %s)' % textescape(self.data.strip())]
        else:
            return ['text()=%s' % textescape(self.data)]


#eof

# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import six
from f3utils.service_meta import abstractmethod, _ServiceMeta
from .helpers import textescape, Integer
from .dom_meta import DOM_Meta

from six.moves.html_parser import HTMLParser
from six.moves import html_entities
from selenium.webdriver.remote.webdriver import WebElement
from selenium.common.exceptions import WebDriverException

if six.PY2:
    from HTMLParser import HTMLParseError
else:

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


class BaseDPOParser(HTMLParser, object):
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
            if not self._dom_stack:
                raise HTMLParseError("Syntax error at element <%s>" % closed.tag,
                                     position=self.getpos())
            prev = self._dom_stack[-1]
            if not isinstance(prev, closed._consume_in):
                raise HTMLParseError("A <%s> element cannot be consumed in a <%s>" % \
                                     (closed.tag, prev.tag or prev._name),
                                     position=closed.pos)
            prev.consume(closed)
            if closed.tag == tag:
                break

    def _pop_empty(self):
        if len(self._dom_stack) > 1 and self._dom_stack[-1].is_empty:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            if not isinstance(prev, closed._consume_in):
                raise HTMLParseError("A <%s> element cannot be consumed in a <%s>" % \
                                     (closed.tag, prev.tag), position=closed.pos)
            prev.consume(closed)

    def close(self):
        super(BaseDPOParser, self).close()
        # consume remaining element
        while len(self._dom_stack) > 1:
            closed = self._dom_stack.pop()
            prev = self._dom_stack[-1]
            if not isinstance(prev, closed._consume_in):
                raise HTMLParseError("A <%s> element cannot be consumed in a <%s>" % \
                                     (closed.tag, prev.tag), position=closed.pos)
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
        self.handle_data(six.unichr(int(name)))

    def handle_entityref(self, name):
        uchr = html_entities.name2codepoint.get(name, None)
        if uchr is None:
            raise HTMLParseError("Invalid HTML entity ref: &%s;" % name,
                                 position=self.getpos())
        self.handle_data(six.unichr(uchr))

    def handle_comment(self, data):
        """Comments are ignored
        """
        pass

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
    """Base class for elements scanned in pagetemplate html

        This is an abstract class, only subclasses shall be instantiated.

    """
    tag = ''
    is_empty = False   # for elements that need no end tag

    def __init__(self, tag=None, attrs=()):
        self.__xpath = None
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

        for k, vals in expected.items():
            py, typ, d = vals
            if d is AttributeError:
                raise ValueError('Missing mandatory attribute in <%s %s=??>'
                                 % (self.tag, k))
            else:
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

    def reduce(self, site=None):
        """Cleanup internally, possibly merging nested elements

            None can be returned, in case this element is no longer
            useful.
            `reduce()` shall be called *after* all children have been
            scanned and appended to this; after thet have been reduced.

            If `site` is provided, this should be a context object,
            which provides (or consumes) additional resources from this
            element.
        """
        # reset cached xpath, let it compute again
        self.__xpath = None
        return self

    def _reduce_children(self, site):
        """Apply site reduce to immediate children

            To be added to `reduce()` in those classes that need it
        """
        if site is None:
            return
        nchildren = []
        for celem in self._children:
            try:
                ncelem = celem.reduce(site)
                if ncelem is not None:
                    nchildren.append(ncelem)
            except TypeError:
                nchildren.append(celem)

        self._children[:] = nchildren     # inplace

    def pretty_dom(self):
        """Walk this template, generate (indent, name, xpath) sets of each node

            Used for debugging, pretty-printing of parsed structure
        """
        #return []
        for c in self._children:
            for pd in c.pretty_dom():
                yield pd

    def xpath_locator(self, score, top=False):
        """Return xpath locator of this and any child elements

            :param score: mutable Integer, decrement depending on precision of locators
            :param top: locate exactly this (the top) element, or else any of its children

            :return: str
        """
        return ''

    @property
    def xpath(self):
        if self.__xpath is None:
            self.__xpath = self.xpath_locator(Integer(100), top=True)
        return self.__xpath

    def _reset_xpath_locator(self):
        self.__xpath = None

    # Methods for Component Proxies
    def iter_items(self, remote, scope, xpath_prefix='', match=None):
        """Iterate possible children components
        
            :param remote: remote WebElement to work on
            :param scope: DOMScope under which to operate
            :param xpath_prefix: hanging xpath from parent element
            :param match: if provided, only look for those items
                currently only a string is expected in `match`

            :return: tuple (name, welem, ptmpl, scope)
        """
        return

    def _iter_items_cont(self, remote, scope, xpath_prefix='', match=None):
        """Standard `iter_items()` implementation for containing components

            Returns **one** set of discovered elements
        """
        seen_names = set()
        for ch in self._children:
            for n, w, p, scp in ch._locate_in(remote, scope, xpath_prefix, match):
                # Suppress duplicate names, only return first match
                if n in seen_names:
                    break
                yield n, w, p, scp
                seen_names.add(n)

    def _locate_in(self, remote, scope, xpath_prefix, match):
        """Locate (possibly) this component under 'remote' webelem

            Called by the parent component, to resolve this.
            Returns tuple (name, welem, ptmpl, scope)
        """
        return []

    def iter_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Iterate names of possible attributes

            returns iterator of (name, descriptor)
        """
        return ()

    def _locate_attrs(self, webelem=None, scope=None, xpath_prefix=''):
        """Locate self and return our possible attributes

            To be called by parent to return possible attributes
            return: same as `iter_attrs()`
        """
        return ()


class DataElement(DPageElement):
    _name = 'text'
    _consume_in = ()
    is_empty = True
    _xpath_score = 20

    def __init__(self, data):
        super(DataElement, self).__init__()
        assert isinstance(data, six.string_types)
        self.data = data
        self._xpath = None
        if data.startswith((' ', '\n')) or data.endswith((' ', '\n')):
            self.full = False
        else:
            self.full = True

    def set_full(self, full):
        self.full = full
        self._xpath = None

    def consume(self, element):
        if isinstance(element, DataElement):
            self.data += element.data
            return
        raise TypeError('Data cannot consume %r' % element)

    def append(self, other):
        assert isinstance(other, DataElement)
        self.data += other.data

    def xpath_locator(self, score, top=False):
        locator = ''
        if self._xpath is None:
            if self.full:
                self._xpath = 'text()=%s' % textescape(self.data)
            else:
                self._xpath = 'contains(text(), %s)' % textescape(self.data.strip())
        if score and score > 0:
            locator = self._xpath
            score -= self._xpath_score
        return locator


DataElement._consume_in = (DataElement,)


class DBaseLinkElement(DPageElement):
    """Baseclass for `<link>` elements in any pagelem document
    
        Links have mandatory "rel", "href" attributes and
        optional "url", "title".
    """
    _name = '.base.link'
    is_empty = True

    _attrs_map = {'rel': ('rel', None, AttributeError),
                  'href': ('href', None, AttributeError),
                  'title': ('title', None, None),
                  'url': ('url', None, None),
                 }

    def __init__(self, tag, attrs):
        super(DBaseLinkElement, self).__init__(tag, attrs)
        self._parse_attrs(attrs)
        self.registered = False

    def reduce(self, site=None):
        if site is not None and site.register_link(self):
            self.registered = True

        return super(DBaseLinkElement, self).reduce()

    def consume(self, element):
        raise TypeError('%s cannot consume %r' % (self._name, element))


@six.add_metaclass(DOM_Meta)
class DOMScope(object):
    """A simple holder of shared components or variables across DOM levels
    """
    wait_js_conditions = []
    timeouts = {}

    
    def __init__(self, parent, templates=None):
        self._parent = parent
        if templates is None:
            templates = {}
        self._templates = templates
        self._root_component = None

    def child(self):
        """Return a child scope linked to this one
        """
        return DOMScope.new(self)

    def get_template(self, key):
        try:
            return self._templates[key]
        except KeyError:
            if self._parent is not None:
                return self._parent.get_template(key)
            else:
                raise KeyError("Template id='%s' not found" % key)

    def take_component(self, comp):
        if self._root_component is None:
            self._root_component = comp

    @property
    def root_component(self):
        return self._root_component

    def __getattr__(self, name):
        if self._parent is not None:
            return getattr(self._parent, name)
        raise AttributeError(name)

    class Component(object):
        def __make_cwrap_simple(name):
            """Create wrapper function, that will bind to `ComponentProxy` and call `WebElement` equivalent

            """
            webelem_fn = getattr(WebElement, name, None)
            if webelem_fn is None:
                return None

            @six.wraps(webelem_fn)
            def __fn(self, *args, **kwargs):
                try:
                    return getattr(self._remote, name)(*args, **kwargs)
                except WebDriverException as e:
                    # Reset traceback to this level, ignore rest of stack
                    e.component = self
                    raise e
                except Exception as e:
                    raise e
            return __fn

        # aliases for simple WebElement methods:
        click = __make_cwrap_simple('click')
        clear = __make_cwrap_simple('clear')
        get_attribute = __make_cwrap_simple('get_attribute')
        get_property = __make_cwrap_simple('get_property')
        is_displayed = __make_cwrap_simple('is_displayed')
        is_enabled = __make_cwrap_simple('is_enabled')
        is_selected = __make_cwrap_simple('is_selected')
        send_keys = __make_cwrap_simple('send_keys')
        submit = __make_cwrap_simple('submit')

#eof

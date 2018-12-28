# -*- coding: UTF-8 -*-
"""
    These classes represent a *map* of the site/page to be scanned/tested

    They are the /definition/ describing interesting parts of the target
    page, not the elements of that page.
"""

import logging
import six
import fnmatch
import re
import errno
from f3utils.service_meta import abstractmethod, _ServiceMeta
from abc import abstractproperty
from collections import defaultdict
import os.path
import posixpath as pp
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

from selenium.webdriver.common.by import By
from behave_manners import dom_elemproxy


class DPageElement(object):
    __metaclass__ = _ServiceMeta
    tag = ''
    is_empty = False   # for elements that need no end tag

    def __init__(self, tag=None, attrs=()):
        self.pos = None
        self.tag = tag
        self._children = []

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.tag)

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

    @property
    def xpath(self):
        """Obtain selenium locator for this element
        """
        raise NotImplementedError

    def prepend_xpath(self, xpath):
        """Prepend parent's xpath into this one
        """
        pass

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

    def analyze(self, webdriver, parent=None, max_depth=1000):
        assert parent is not None, "Parent must be provided"
        return


class AnyElement(DPageElement):
    _name = 'tag.anyelement'

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
                    raise ValueError('Attribute defined more than once: %s' % k)
            else:
                assert '.' not in k, k
                # attribute to match as locator
                match_attrs[k].append(_textescape(v))

    @property
    def xpath(self):
        return self._xpath

    def prepend_xpath(self, xpath):
        if not self._xpath.startswith(xpath):
            self._xpath = xpath + self._xpath

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
    _inherit = 'tag.anyelement'
    
    def __init__(self, tag, attrs):
        super(GenericElement, self).__init__(tag, attrs)
        self._xpath = tag + self._xpath


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

    def analyze(self, webelem, parent=None, max_depth=1000):
        assert parent is not None
        print "searching for ", self.xpath
        elem = webelem.find_element_by_xpath(self.xpath)
        proxy = dom_elemproxy.ElementProxy(self, elem)
        parent.set(self.this_name, proxy)
        if max_depth > 0:
            super(NamedElement, self).analyze(elem, proxy, max_depth=max_depth-1)

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
        print "must have of ", self
        return [ './' + ch.xpath for ch in self._children]


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
        print "Reduce deep ", self._children # *-*
        if len(self._children) == 1 and isinstance(self._children[0], AnyElement):
            ch = self._children.pop()
            ch._xpath = '/' + ch._xpath
            return ch
        return self

    
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
                if not isinstance(celem, DHtmlObject): # *-*
                    i += 1  # *-*  or pop it?
                    continue
                ncelem = celem.reduce(site)
                if ncelem is not celem:
                    self._children.pop(i)
                    if ncelem is not None:
                        self._children.insert(i, ncelem)
                if ncelem is not None:
                    i += 1

        for c in self._children:
            c.prepend_xpath(self.xpath)

        return super(DHtmlObject, self).reduce()

    @property
    def xpath(self):
        return '//'
    
    def analyze(self, webdriver, parent=None, max_depth=1000):
        """Discover all interesting elements within webdriver current page+context
        """
        assert parent is None
        page = dom_elemproxy.PageProxy(self, webdriver)
        if max_depth > 0:
            for ch in self._children:
                ch.analyze(webdriver, page, max_depth=max_depth-1)
        return page


class ISomeObject(DPageElement):
    """Base class for 'index.html' and its sub-elements
    
        These override `reduce()` so that <link> elements are consumed and
        the rest is discarded.
    """
    _name = '.index.base'
    def reduce(self, site=None):
        if site is not None:
            i = 0
            while i < len(self._children):
                celem = self._children[i]
                ncelem = celem.reduce(site)
                if ncelem is not celem:
                    self._children.pop(i)
                    if ncelem is not None:
                        self._children.insert(i, ncelem)
                if ncelem is not None:
                    i += 1

        if not self._children:
            return None
        
        return super(ISomeObject, self).reduce()
    

class IHtmlObject(DPageElement):
    """Consume the <html> element as top-level index page
    
    """
    _name = 'index.html'
    _inherit = '.index.base'

    @property
    def xpath(self):
        return '/'


class IHeadObject(DPageElement):
    _name = 'index.head'
    _inherit = '.index.base'

    @property
    def xpath(self):
        return '/'


class ILinkObject(DPageElement):
    _name = 'index.link'
    _inherit = '.leaf'
    is_empty = True
    SUPPORTED_ATTRS = ('rel', 'href', 'title', 'url')
    
    def __init__(self, tag, attrs=()):
        super(ILinkObject, self).__init__(tag, attrs)
        self.title = self.url = None    # defaults
        seen = set()
        for k, v in attrs:
            if k in seen:
                raise ValueError("Duplicate attribute in <%s %s >" % (tag, k))
            if k in self.SUPPORTED_ATTRS:
                setattr(self, k, v)
                seen.add(k)
            else:
                raise ValueError("Unsupported attribute in <%s %s >" % (tag, k))
        for k in self.SUPPORTED_ATTRS:
            if not hasattr(self, k):
                raise ValueError("Tag <%s> missing '%s=' attribute" % (tag, k))

    @property
    def xpath(self):
        return '/'

    def reduce(self, site=None):
        if site is not None and site.register_link(self):
            return None

        return super(ILinkObject, self).reduce()


class DPageObject(DPageElement):
    """HTML page embedded as a sub-element of <html>
    
        This would behave like a <html> but can be nested inside a file,
        unlike <html> element that is unique per file.
    """
    _name = 'tag.htmlpage'
    _inherit = 'tag.html'

    def __init__(self, tag=None, attrs=()):
        super(DPageObject, self).__init__(tag, attrs)


    
class DSiteCollection(DPageElement):
    """Collection of several HTML pages, like a site
    
        Not supposed to be parsed, but directly instantiated as root hierarchy
        of all parsed html pageobject files.
    """
    _name = '.siteCollection'
    logger = logging.getLogger('site_collection')

    def __init__(self, loader):
        super(DSiteCollection, self).__init__()
        assert isinstance(loader, BaseLoader)
        self._loader = loader
        self.cur_file = None
        self.file_dir = {}
        self.urls = set()
        self.page_dir = {}
        self.pending_load = set()

    def consume(self, element):
        if isinstance(element, (IHtmlObject, DHtmlObject)):
            element = element.reduce(self)
            if element is None:
                pass
            elif self.cur_file:
                assert not self.file_dir.get(self.cur_file, None), self.cur_file
                self.file_dir[self.cur_file] = element
            else:
                super(DSiteCollection, self).consume(element)
        else:
            raise TypeError("Cannot consume %s in a site collection" % type(element))

    def register_link(self, link):
        assert isinstance(link, ILinkObject), repr(link)
        
        if not link.href:
            raise ValueError("Invalid <link>, without href=")
        cwd = ''
        if self.cur_file:
            cwd = pp.dirname(self.cur_file)
        target = pp.normpath(pp.join(cwd, link.href))
        content = self.file_dir.setdefault(target, None)
        if link.url:
            link_re = fnmatch.translate(link.url)   # TODO nio-style matching
            self.urls.add((re.compile(link_re), target))
        if link.title:
            self.page_dir[link.title] = target
        if link.rel == 'preload' and not content:
            self.pending_load.add(target)
        elif link.rel in ('next', 'prev', 'page'):
            pass
        else:
            raise ValueError("Invalid <link rel=\"%s\">" % (link.rel))
    
        return True

    def __len__(self):
        return len(self.children)

    def load_index(self, pname):
        old_file = self.cur_file
        try:
            if self.cur_file:
                pname = pp.join(pp.dirname(self.cur_file), pname)
            pname = pp.normpath(pname)
            self.cur_file = pname
            self.logger.debug("Trying to read index: %s", pname)
            parser = IndexHTMLParser(self)
            with self._loader.open(pname) as fp:
                while True:
                    chunk = fp.read(65536)
                    if not chunk:
                        break
                    parser.feed(chunk)
                    
            # TODO: reduce
            self.logger.info("Read index from '%s'", pname)
        finally:
            self.cur_file = old_file

    def load_preloads(self):
        """Load pending specified preloads
        """
        while self.pending_load:
            pname = self.pending_load.pop()
            self.load_pagefile(pname)

    def load_all(self):
        """Load all referenced pages

            Used for forced scan of their content
        """
        raise NotImplementedError
        pending = 1
        while True:
            pending = [ pname for pname, cnt in self.file_dir.items() if cnt is None]
            if not pending:
                break
            for pname in pending:
                self.load_pagefile(pname)

    def load_pagefile(self, pname):
        old_file = self.cur_file
        try:
            if self.cur_file:
                pname = pp.join(pp.dirname(self.cur_file), pname)
            pname = pp.normpath(pname)
            if self.file_dir.get(pname, False):
                self.logger.warning("Attempted to load page twice: %s", pname)
                return
            self.cur_file = pname
            self.logger.debug("Trying to read page: %s", pname)
            parser = PageParser(self)
            with self._loader.open(pname) as fp:
                while True:
                    chunk = fp.read(65536)
                    if not chunk:
                        break
                    parser.feed(chunk)
                    
            # TODO: reduce
            self.logger.info("Read page from '%s'", pname)
        finally:
            self.cur_file = old_file

    def get_by_url(self, url, fragment=None):
        """Find the page template that matches url (path) of browser
        
            returns (page, params)
        """
        if not url.startswith('/'):
            raise NotImplementedError("Only absolute URL paths supported")

        # TODO: decode fragments

        for expr, target in self.urls:
            m = expr.match(url)
            if m:
                page = self.get_by_file(target)
                return page, m.groups()[1:]
        else:
            raise KeyError("No match for url")

    def get_by_file(self, fname):
        """Get page by template filename
        """
        if fname not in self.file_dir:
            raise KeyError("Template not found: %s" % fname)
        if self.file_dir[fname] is None:
            # must load it
            self.load_pagefile(fname)

        return self.file_dir[fname]

    def get_by_title(self, title):
        """Get page by set title
        
           Titles are arbitrary, pretty names assigned to page templates
        """
        fname = self.page_dir[title]
        return self.get_by_file(fname)


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
            # print "consume %s in %r" % (closed.tag, prev.tag)  # *-*
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
        raise NotImplementedError

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
            try:
                elem = DPageElement['named.' + tag](tag, attrs)
            except TypeError:
                elem = DPageElement['named'](tag, attrs)
            except ValueError, e:
                raise HTMLParseError(unicode(e), position=self.getpos())
        else:
            try:
                elem = DPageElement['tag.' + tag](tag, attrs)
            except TypeError, e:
                elem = DPageElement['any'](tag, attrs)
            except ValueError, e:
                raise HTMLParseError(unicode(e), position=self.getpos())
        elem.pos = self.getpos()
        self._dom_stack.append(elem)

    def handle_data(self, data):
        if not data.strip():
            return

        self._pop_empty()
        elem = DataElement.new(data)
        elem.pos = self.getpos()
        self._dom_stack.append(elem)


class IndexHTMLParser(BaseDPOParser):
    """Parser only for 'index.html', containing links to other pages
    
        In this pseydo-HTML site language, 'index.html' is only allowed
        to contain `<link>` elements to other named page object files.
        This parser restricts any other HTML elements for this file.
        
        Example::
            <html>
                <link rel="next" href="main-page.html" title="Main Page" url="/">
                <link rel="preload" href="common-components.html">
            </html>
    """
    logger = logging.getLogger(__name__ + '.IndexHTMLParser')

    def __init__(self, site_collection):
        assert isinstance(site_collection, DSiteCollection)
        super(IndexHTMLParser, self).__init__(site_collection)

    def handle_starttag(self, tag, attrs):
        self._pop_empty()
        try:
            elem = DPageElement['index.' + tag](tag, attrs)
        except ValueError, e:
            raise HTMLParseError(unicode(e), position=self.getpos())
        except TypeError, e:
            raise HTMLParseError("Element <%s> not allowed in index page" % tag,
                                 position=self.getpos())
        elem.pos = self.getpos()
        self._dom_stack.append(elem)


class BaseLoader(object):
    """Abstract base for loading DPO html files off some storage
    """
    def __init__(self):
        pass
    
    @abstractmethod
    def open(self, fname):
        """Open file at `fname` path for reading.
        
            Return a context manager file object
        """

class FSLoader(BaseLoader):

    def __init__(self, root_dir):
        super(FSLoader, self).__init__()
        if not os.path.exists(root_dir):
            raise IOError(errno.ENOENT, "No such directory: %s" % root_dir)
        self.root_dir = root_dir

    def open(self, fname):
        if '..' in fname.split('/'):
            raise IOError(errno.EACCESS, "Parent directory not allowed")
        pathname = os.path.normpath(os.path.join(self.root_dir, fname))
        return open(pathname, 'rb')


def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='check validity of DPO template files')
    parser.add_argument('-N', '--no-preloads', action='store_true',
                        help='check only the index file')
    parser.add_argument('index', metavar='index.html',
                        help="path to 'index.html' file")
    parser.add_argument('inputs', metavar='page.html', nargs='*',
                        help='input files')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    site = DSiteCollection(FSLoader('.'))
    log = logging.getLogger('main')
    if args.index:
        log.debug("Loading index from %s", args.index)
        site.load_index(args.index)
        if not args.no_preloads:
            site.load_preloads()

    for pfile in args.inputs:
        site.load_pagefile(pfile)

    if not args.no_preloads:
        site.load_preloads()
        
    log.info("Site collection contains %d pages, %d files",
             len(site.page_dir), len(site.file_dir))
    
    print "Site files:"
    for trg, content in site.file_dir.items():
        print "    ", trg, content and '*' or ''
    
    print "\nSite pages:"
    for page, trg in site.page_dir.items():
        print "    %s: %s" % (page, trg)

if __name__ == '__main__':
    cmdline_main()


#eof

# -*- coding: UTF-8 -*-

import posixpath as pp
import logging
import fnmatch
import re
from .base_parsers import DPageElement, BaseDPOParser, HTMLParseError
from .loaders import BaseLoader


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


class IHeadObject(DPageElement):
    _name = 'index.head'
    _inherit = '.index.base'


class ILinkObject(DPageElement):
    _name = 'index.link'
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

    def reduce(self, site=None):
        if site is not None and site.register_link(self):
            return None

        return super(ILinkObject, self).reduce()

    def consume(self, element):
        raise TypeError('%s cannot consume %r' % (self._name, element))


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
        self.file_dir = {}  # filename-to-pageelem main mapping
        self.urls = set()
        self.page_dir = {}  # title-to-filename mapping
        self.url_dir = {}  # title-to-url mapping
        self.pending_load = set()

    def consume(self, element):
        from .page_elements import DHtmlObject
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
            if link.url is not None:
                self.url_dir[link.title] = link.url
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
        from .page_elements import PageParser   # lazy import
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
        
            returns (page, title, params)
        """

        # TODO: decode fragments

        for expr, target in self.urls:
            m = expr.match(url)
            if m:
                page = self.get_by_file(target)
                title = None
                for t, u in self.url_dir.items():
                    if u == url:
                        title = t
                        break
                return page, title, m.groups()[1:]
        else:
            raise KeyError("No match for url")

    def get_by_file(self, fname):
        """Get page by template filename
        
            :return: pageelem
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
           :return: (pageelem, url)
        """
        fname = self.page_dir[title]
        url = self.url_dir.get(title, None)
        return self.get_by_file(fname), url


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


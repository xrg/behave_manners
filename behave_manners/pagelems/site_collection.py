# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import posixpath as pp
import fnmatch
import logging
import re
from .base_parsers import DPageElement, DOMScope, DBaseLinkElement
from .loaders import BaseLoader


class DSiteCollection(DPageElement):
    """Collection of several HTML pages, like a site

        Not supposed to be parsed, but directly instantiated as root hierarchy
        of all parsed html pageobject files.
    """
    _name = '.siteCollection'
    logger = logging.getLogger('site_collection')

    def __init__(self, loader, config=None):
        super(DSiteCollection, self).__init__()
        assert isinstance(loader, BaseLoader)
        self._loader = loader
        self.cur_file = None
        self.file_dir = {}  # filename-to-pageelem main mapping
        self.urls = set()
        self.page_dir = {}  # title-to-filename mapping
        self.url_dir = {}  # title-to-url mapping
        self.pending_load = set()
        self.pending_gallery = set()
        self._loaded_gallery = set()   # mark already loaded files
        self._templates = {}
        self._site_config = config or {}

    def consume(self, element):
        from .page_elements import DHtmlObject
        from .index_elems import IHtmlObject

        element = element.reduce(self)
        if element is None:
            return
        if isinstance(element, DHtmlObject):
            if self.cur_file:
                assert not self.file_dir.get(self.cur_file, None), self.cur_file
                self.file_dir[self.cur_file] = element
        else:
            raise TypeError("Cannot consume %s in a site collection" % type(element))
        super(DSiteCollection, self).consume(element)

    def register_link(self, link):
        assert isinstance(link, DBaseLinkElement), repr(link)

        if not link.href:
            raise ValueError("Invalid <link>, without href=")
        cwd = ''
        if self.cur_file:
            cwd = pp.dirname(self.cur_file)
        target = pp.normpath(pp.join(cwd, link.href))
        if link.rel in ('next', 'prev', 'page'):
            content = self.file_dir.setdefault(target, None)
            if link.url is not None:
                link_re = fnmatch.translate(link.pattern or link.url)   # TODO nio-style matching
                self.urls.add((link.url, re.compile(link_re), target))
            if link.title:
                self.page_dir[link.title] = target
                if link.url is not None:
                    self.url_dir[link.title] = link.url
            if link.rel == 'preload' and not content:
                self.pending_load.add(target)
        elif link.rel == 'import':
            if target not in self._loaded_gallery:
                self.pending_gallery.add(target)
        else:
            raise ValueError("Invalid <link rel=\"%s\">" % (link.rel))

        return True

    def __len__(self):
        return len(self._children)

    def _feed_parser(self, parser, pname, ptype):
        with self._loader.open(pname, mode='rt') as fp:
            while True:
                chunk = fp.read(65536)
                if not chunk:
                    break
                parser.feed(chunk)

        self.logger.info("Read %s from '%s'", ptype, pname)

    def load_index(self, pname):
        from .index_elems import IndexHTMLParser
        old_file = self.cur_file

        try:
            if self.cur_file:
                pname = pp.join(pp.dirname(self.cur_file), pname)
            pname = pp.normpath(pname)
            self.cur_file = pname
            self.logger.debug("Trying to read index: %s", pname)
            self._feed_parser(IndexHTMLParser(self), pname, 'index')
            # TODO: reduce
        finally:
            self.cur_file = old_file

    def load_preloads(self):
        """Load pending preloads or gallery files
        """
        while self.pending_load or self.pending_gallery:
            if self.pending_gallery:
                self.load_galleryfile(self.pending_gallery.pop())
            if self.pending_load:
                self.load_pagefile(self.pending_load.pop())

    def load_all(self):
        """Load all referenced pages

            Used for forced scan of their content
        """
        self.load_preloads()
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
            self._feed_parser(PageParser(self), pname, 'page')
            # TODO: reduce
        finally:
            self.cur_file = old_file

    def load_galleryfile(self, pname):
        from .page_elements import GalleryParser   # lazy import
        old_file = self.cur_file
        try:
            if self.cur_file:
                pname = pp.join(pp.dirname(self.cur_file), pname)
            pname = pp.normpath(pname)
            if pname in self._loaded_gallery:
                self.logger.warning("Attempted to load gallery twice: %s", pname)
                return
            self.cur_file = pname
            self.logger.debug("Trying to read page: %s", pname)
            self._feed_parser(GalleryParser(self), pname, 'gallery')
            self._loaded_gallery.add(pname)
        finally:
            self.cur_file = old_file

    def get_by_url(self, url, fragment=None):
        """Find the page template that matches url (path) of browser

            returns (page, title, params)
        """

        # TODO: decode fragments

        for fnpat, expr, target in self.urls:
            m = expr.match(url)
            if m:
                page = self.get_by_file(target)
                title = None
                for t, u in self.url_dir.items():
                    if u == fnpat:
                        title = t
                        break
                return page, title, m.groups()[1:]
        else:
            raise KeyError("No match for url: %s" % url)

    def get_by_file(self, fname):
        """Get page by template filename

            :return: pageelem
        """
        if fname not in self.file_dir:
            raise KeyError("Template not found: %s" % fname)
        if self.file_dir[fname] is None:
            # must load it
            self.load_pagefile(fname)
            # and any dependencies that have appeared since
            self.load_preloads()

        return self.file_dir[fname]

    def get_by_title(self, title):
        """Get page by set title

           Titles are arbitrary, pretty names assigned to page templates
           :return: (pageelem, url)
        """
        fname = self.page_dir[title]
        url = self.url_dir.get(title, None)
        return self.get_by_file(fname), url

    def get_root_scope(self):
        """Return new DOMScope bound to self

            A `DSiteCollection` can be reused across runs, but ideally
            each run should start with a new scope, as returned by
            this method.
            Then, this scope should be passed to pages under this site,
            as those returned by `get_by_title()` , `get_by_url()` etc.
        """
        root_klass = self._site_config.get('root_controller', '.root')
        return DOMScope[root_klass](templates=self._templates,
                                    site_config=self._site_config)


from . import scopes  # put scopes in scope, ensure they're loaded

# eof

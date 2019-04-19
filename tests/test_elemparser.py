# -*- coding: UTF-8 -*-

from __future__ import absolute_import, print_function
import threading
import pytest
import errno
from six.moves import StringIO
import contextlib
from behave_manners.context import GContext, EventContext
from behave_manners.pagelems.loaders import BaseLoader
from behave_manners.pagelems.base_parsers import HTMLParseError
from behave_manners.pagelems.site_collection import DSiteCollection


class DummyLoader(BaseLoader):
    def __init__(self):
        self.files = {}

    def open(self, fname):
        if fname not in self.files:
            raise IOError(errno.ENOENT, "No such file")
        return contextlib.closing(StringIO(self.files[fname]))


@pytest.fixture
def dummy_loader():
    dl = DummyLoader
    return dl


class TestPElemParser(object):

    def _set_site(self, files):
        site = DSiteCollection(DummyLoader())
        site._loader.files.update(files)
        return site

    def test_index_html_valid1(self):
        """Check minimal definition of 'index.html' script
        """
        h = '''
            <html>
            <head>
                <link rel="next" href="page.html" title="Index Page" url="">
            </head>
            </html>
        '''

        site = self._set_site({'index.html': h})
        site.load_index('index.html')
        assert site.file_dir  # has any entries, even if value=None
        assert site.page_dir.get('Index Page', '<missing>') == 'page.html'

    def test_index_html_valid2(self):
        """Check rich example of an 'index.html' page
        """
        h = '''
            <html>
            <head>
                <link rel="next" href="page.html" title="Index Page" url="">
                <link rel="next" href="page2.html" title="Page 2" url="/page2">
                <link rel="next" href="page3.html" url="/page3">
                <link rel="import" href="gallery1.html">
            </head>
            </html>
        '''

        site = self._set_site({'index.html': h})
        site.load_index('index.html')
        assert site.file_dir  # has any entries, even if value=None
        assert site.page_dir.get('Index Page', '<missing>') == 'page.html'
        assert site.page_dir.get('Page 2', '<missing>') == 'page2.html'
        assert 'page3.html' in site.file_dir
        assert 'gallery1.html' in site.pending_gallery

    def test_index_invalid1(self):
        """Test index.html without `<head>`
        """
        h = '''
            <html>
                <link rel="next" href="page.html" title="Index Page" url="">
            </html>
        '''

        site = self._set_site({'index.html': h})
        with pytest.raises(HTMLParseError):
            site.load_index('index.html')

    def test_index_invalid1(self):
        """Test index.html with other content
        """
        h = '''
            <html>
            <body>
                <p> Hello!</p>
            </body>
            </html>
        '''

        site = self._set_site({'index.html': h})
        with pytest.raises(HTMLParseError):
            site.load_index('index.html')

    def test_gallery_valid1(self):
        pass

        #index invalid

    def test_tmpl_page_valid1(self):
        """Test a trivial template page
        """
        h = '''
            <html>
            <body>
                <p>Hello!</p>
            </body>
            </html>
        '''

        site = self._set_site({'page.html': h})
        site.load_pagefile('page.html')

    def test_tmpl_page_valid2(self):
        """Test pagelem template
        """
        h = '''
            <html>
            <head>
            </head>
            <body>
                <div class="content">
                    <pe-deep>
                        <div id="pe1" this="pe1">
                            <p>Hello!</p>
                        </div>
                    </pe-deep>
                </div>
            </body>
            </html>
        '''

        site = self._set_site({'page.html': h})
        site.load_pagefile('page.html')

    def test_tmpl_page_valid3(self):
        """Test pagelem template with char refs and entity refs
        """
        h = '''
            <html>
            <head>
            </head>
            <body>
                <div class="content">
                    <pe-deep>
                        <div id="pe1" this="pe1">
                            <p>Hello &amp; have a nice time &#128338; !</p>
                        </div>
                    </pe-deep>
                </div>
            </body>
            </html>
        '''

        site = self._set_site({'page.html': h})
        site.load_pagefile('page.html')
        page = site.file_dir['page.html']
        assert page._children[0]._children[0]._children[0].xpath == \
                u"p[contains(text(), 'Hello & have a nice time ð !')]"

    def test_tmpl_page_invalid1(self):
        """Test bad HTML syntax
        """
        h = '''
            <html>
            <head>
            </head>
            <body>
                <!-- missing closing quote, below -->
                <div class="content>
                    <pe-deep>
                        <div id="pe1" this="pe1">
                            <p>Hello!</p>
                        </div>
                    </pe-deep>
                </div>
            </body>
            </html>
        '''

        site = self._set_site({'page.html': h})
        with pytest.raises(HTMLParseError):
            site.load_pagefile('page.html')

    def test_tmpl_page_valid_re1(self):
        """Test that less-than or greater-than work in <pe-regex> elements
        """
        h = '''
            <html>
            <body>
                <pe-regex>Hello (?P<b>world)!</pe-regex>
            </body>
            </html>
        '''

        site = self._set_site({'page.html': h})
        site.load_pagefile('page.html')
        page = site.file_dir['page.html']
        assert page._children[0]._children[0]._regex.pattern == 'Hello (?P<b>world)!'


#eof

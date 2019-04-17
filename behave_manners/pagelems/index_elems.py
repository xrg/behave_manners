# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import logging
from .base_parsers import DPageElement, BaseDPOParser, HTMLParseError
from .site_collection import DSiteCollection
import six


class ISomeObject(DPageElement):
    """Base class for 'index.html' and its sub-elements
    
        These override `reduce()` so that <link> elements are consumed and
        the rest is discarded.
    """
    _name = '.index.base'
    def reduce(self, site=None):
        self._reduce_children(site)

        if not self._children:
            return None

        return super(ISomeObject, self).reduce()


class IHtmlObject(DPageElement):
    """Consume the <html> element as top-level index page
    
    """
    _name = 'index.html'
    _inherit = '.index.base'
    _consume_in = (DSiteCollection,)


class IHeadObject(DPageElement):
    _name = 'index.head'
    _inherit = '.index.base'
    _consume_in = (IHtmlObject,)

    def reduce(self, site=None):
        ret = super(IHeadObject, self).reduce(site)
        if site is not None and ret is self:
            self._children = [c for c in self._children
                              if not (isinstance(c, ILinkObject) and c.registered)]
            if not self._children:
                ret = None
        return ret


class ILinkObject(DPageElement):
    _name = 'index.link'
    _inherit = '.base.link'
    _consume_in = (IHeadObject,)



class IndexHTMLParser(BaseDPOParser):
    """Parser only for 'index.html', containing links to other pages

        In this pseydo-HTML site language, 'index.html' is only allowed
        to contain ``<link>`` elements to other named page object files.
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
        except ValueError as e:
            raise HTMLParseError(six.text_type(e), position=self.getpos())
        except TypeError as e:
            raise HTMLParseError("Element <%s> not allowed in index page" % tag,
                                 position=self.getpos())
        elem.pos = self.getpos()
        self._dom_stack.append(elem)


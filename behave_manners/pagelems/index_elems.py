# -*- coding: UTF-8 -*-

import logging
from .base_parsers import DPageElement, BaseDPOParser, HTMLParseError
from .site_collection import DSiteCollection


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
    _consume_in = (DSiteCollection,)


class IHeadObject(DPageElement):
    _name = 'index.head'
    _inherit = '.index.base'
    _consume_in = (IHtmlObject,)


class ILinkObject(DPageElement):
    _name = 'index.link'
    is_empty = True
    _consume_in = (IHeadObject,)
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


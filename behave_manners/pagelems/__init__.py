# -*- coding: UTF-8 -*-

"""
    These classes represent a *map* of the site/page to be scanned/tested

    They are the /definition/ describing interesting parts of the target
    page, not the elements of that page.
"""

from .loaders import FSLoader
from .base_parsers import DPageElement, DOMScope
from .index_elems import DSiteCollection



# eof

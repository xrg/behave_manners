# -*- coding: UTF-8 -*-
"""
"""
from __future__ import print_function
import six
from behave.runner import Context
from .site import SiteContext, WebContext


def site_setup(context, config=None):
    # context.config.setup_logging() ??
    assert isinstance(context, Context)
    if hasattr(context, 'site'):
        raise RuntimeError("Site cannot be setup twice in same context")
    if config and isinstance(config, six.string_types):
        config = SiteContext._load_config(config)

    if config and config.get('browser'):
        context.site = WebContext(context, config)
    else:
        context.site = SiteContext(context, config)

    return



#eof

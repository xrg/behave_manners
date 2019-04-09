# -*- coding: UTF-8 -*-
"""
"""
from __future__ import print_function
from __future__ import absolute_import
import copy
import six
from behave.runner import Context
from .site import SiteContext, WebContext


def site_setup(context, config=None, extra_conf=None):
    # context.config.setup_logging() ??
    assert isinstance(context, Context)
    if hasattr(context, 'site'):
        raise RuntimeError("Site cannot be setup twice in same context")
    if not config:
        return
    if isinstance(config, six.string_types):
        config = SiteContext._load_config(config, extra_conf)

    if config.get('browser'):
        context.site = WebContext(context, config)
        if config['browser'].get('screenshots'):
            from .screenshots import Camera
            shots_cfg = config['browser']['screenshots']
            camera = context.site_camera = Camera(base_dir=shots_cfg.get('dir', '.'))
            events = context.site.events

            if shots_cfg.get('on_failure', False):
                events.after_step_failed = camera.snap_failure
            if shots_cfg.get('on_success', False):
                events.after_scenario = camera.snap_success
            events.on_missing_element = camera.capture_missing_elem
    else:
        context.site = SiteContext(context, config)

    if config.get('page_objects'):
        context.site.init_collection()

    if config.get('context'):
        if not isinstance(config['context'], dict):
            raise TypeError("Config 'context' section must be a dict")
        for k, v in config['context'].items():
            setattr(context, k, copy.deepcopy(v))
    return



#eof

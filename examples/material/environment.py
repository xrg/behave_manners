#from behave_manners.site import WebSite

import logging
from behave_manners import site_setup
import time


def before_all(context):
    extra_conf = {'browser': {} }
    if context.config.userdata.get('no-headless', False):
        extra_conf['browser']['headless'] = False
    site_setup(context, config='config.yaml', extra_conf=extra_conf)


def after_step(context, step):
    if context.config.userdata.get('slow', False):
        time.sleep(1.0)

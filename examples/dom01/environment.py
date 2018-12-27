#from behave_manners.site import WebSite

import logging
from behave_manners import site_setup


def before_all(context):
    site_setup(context, config='config.yaml')
    print "level is", logging.getLogger().level


def before_scenario(context, scenario):
    print "before scenario hook"
    #context.site.launch_browser(context)

def after_all(context):
    pass
    print "after all hook"

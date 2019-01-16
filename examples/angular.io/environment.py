#from behave_manners.site import WebSite

import logging
from behave_manners import site_setup

def before_all(context):
    site_setup(context, config='config.yaml')



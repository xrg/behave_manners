#from behave_manners.site import WebSite

import logging
from behave_manners import site_setup
import time

def before_all(context):
    site_setup(context, config=['config*.yaml', 'config2.yaml'])



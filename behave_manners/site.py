# -*- coding: UTF-8 -*-
"""
"""

from __future__ import absolute_import
import time
from selenium import webdriver
import os


class WebSite(object):
    def __init__(self):
        pass
    
    def launch_browser(self, context):
        options = webdriver.ChromeOptions()
        # options.binary_location = '/usr/lib64/chromium-browser/headless_shell'
        options.add_argument('headless')
        options.add_argument('window-size=1200x800')
        caps = {}
        caps['record_network'] = 'true'
        caps['take_snapshot'] = 'true'
        context.browser = webdriver.Chrome(chrome_options=options,
                                        desired_capabilities=caps)
        context.add_cleanup(self._return_browser, context)

    def _return_browser(self, context):
        """Release or destroy the browser after context has finished with it
        """
        print "cleanup browser"
        context.browser.quit()

    def __del__(self):
        print "delete site"


#eof

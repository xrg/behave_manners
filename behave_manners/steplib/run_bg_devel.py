# -*- coding: utf-8 -*
from __future__ import print_function
from __future__ import absolute_import
import json
from behave import when, given, then, step
import logging
import time
from selenium.webdriver.remote.command import Command

log = logging.getLogger('bg_steps')

@when("I launch a browser in foreground")
def _launch_browser_fg(context):
    pass

@when("I save the session to '{session_fname}'")
def _save_browser_session(context, session_fname):
    with open(session_fname, 'wb') as fp:
        json.dump({'url': context.browser.command_executor._url,
                   'session': context.browser.session_id }, fp)


@when("I navigate to the site main page")
def _navigate_site_main(context):
    context.browser.get(context.site.base_url)


@then("I wait for the browser to close itself")
def _wait_browser_forever(context):
    try:
        last_title = None
        while True:
            time.sleep(0.5)
            ntitle = context.browser.title
            if ntitle != last_title:
                log.info("Browser changed to: %s", ntitle)
                last_title = ntitle
            context.site.process_logs(context)
    except KeyboardInterrupt:
        log.warning("Closing by interrupt")
        # Don't need to do anything, just let this step finish
        # and context teardown will close the browser
    except Exception as e:
        log.error("Got exception: %s", e)

# eof

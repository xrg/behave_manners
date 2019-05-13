#!/bin/env python
# -*- coding: UTF-8 -*-
"""
    Standalone runner of 'DPO' structures, validate against an externally
    loaded Selenium WebDriver instance.
    
"""
from __future__ import print_function
from __future__ import absolute_import
import logging
import json
import time
from behave_manners.site import SiteContext, WebContext, FakeContext
from behave_manners.pagelems import FSLoader
from selenium.common.exceptions import WebDriverException



def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='Try DPO templates against open page')
    parser.add_argument('-c', '--config', default='config.yaml',
                        help='Site config file')
    parser.add_argument('-s', '--session-file', default='dbg-browser.session',
                        help="Path to file with saved Remote session")
    parser.add_argument('url', nargs='?',
                        help="Initial URL to load on the browser")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('main')

    context = FakeContext()
    try:
        config = SiteContext._load_config(args.config, loader=FSLoader('.'))
        if not config.get('browser'):
            raise RuntimeError("Supplied config must specify browser settings")

        context.site = WebContext(context, config)
        context.site.launch_browser(context)

        with open(args.session_file, 'wt') as fp:
            json.dump({'url': context.browser.command_executor._url,
                       'session': context.browser.session_id,
                       'capabilities': context.browser.capabilities,
                       # Pass those so that validator doesn't need to load the config
                       'base_url': config.get('site', {}).get('base_url', None),
                       'page_objects': config.get('page_objects', {})
                    }, fp)
        log.info("Entering main phase, waiting for browser to close")
        if args.url:
            if args.url == '.':
                url = context.site.base_url
            elif args.url.startswith('/'):
                url = context.site.base_url
                if url.endswith('/'):
                    url = url[:-1]
                url += args.url
            else:
                url = args.url
            context.browser.get(url)

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
    except WebDriverException as e:
        log.warning("WebDriver: %s", e)
    except Exception as e:
        log.exception("Got exception: %s", e)

    finally:
        context.close()

    log.info("Bye")


if __name__ == '__main__':
    cmdline_main()

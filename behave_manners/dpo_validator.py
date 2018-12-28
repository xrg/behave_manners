#!/bin/env python
# -*- coding: UTF-8 -*-
"""
    Standalone runner of 'DPO' structures, validate against an externally
    loaded Selenium WebDriver instance.
    
"""
from __future__ import print_function
import logging
import json
import time
from selenium import webdriver
from selenium.webdriver.remote.command import Command
from behave_manners.dom_pagetemplate import DSiteCollection, FSLoader
from six.moves.urllib import parse as urlparse


class ExistingRemote(webdriver.Remote):
    """Remote webdriver that attaches to existing session
    """
    def __init__(self, command_executor, session_id, desired_capabilities={}, **kwargs):
        self.__session_id = session_id
        super(ExistingRemote, self).__init__(command_executor=command_executor,
                                             desired_capabilities=desired_capabilities,
                                             **kwargs)

    def start_session(self, desired_capabilities, browser_profile=None):
        if not self.__session_id:
            raise RuntimeError("session_id must be specified in constructor")
        res = self.execute(Command.GET_ALL_SESSIONS)
        if res != 0:
            for session in res['value']:
                if session['id'] == self.__session_id:
                    self.session_id = self.__session_id
                    self.capabilities = session['capabilities']
                    self.w3c = "specificationLevel" in self.capabilities
                    break
            else:
                raise RuntimeError("Remote webdriver does not contain saved session")
        else:
            raise RuntimeError("Cannot get remote webdriver sessions")


def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='Try DPO templates against open page')
    parser.add_argument('-f', '--output', action='store_true', default=False,
                        help='Check all site, not just index')
    parser.add_argument('-s', '--session-file', default='dbg-browser.session',
                        help="Path to file with saved Remote session")
    parser.add_argument('index', metavar='index.html', nargs=1,
                        help="path to 'index.html' file")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    site = DSiteCollection(FSLoader('.'))
    log = logging.getLogger('main')
    log.debug("Loading index from %s", args.index[0])
    site.load_index(args.index[0])
    site.load_preloads()

    log.info("Site collection contains %d pages, %d files",
             len(site.page_dir), len(site.file_dir))

    with open(args.session_file, 'rb') as fp:
        sdata = json.load(fp)
    if 'url' in sdata and 'session' in sdata:
        driver = ExistingRemote(command_executor=sdata['url'],
                                session_id = sdata['session'])
    else:
        raise RuntimeError("Saved session must have 'url' and 'session' set")
    
    log.info("Entering main phase, connected to browser")
    while True:
        try:
            up = urlparse.urlparse(driver.current_url)
            if up.scheme not in ('http', 'https'):
                log.warning("Page is in unknown scheme, %s://", up.scheme)
            elif not up.netloc:
                log.warning("Page is not yet at server")
            else:
                
                try:
                    page, page_args = site.get_by_url(up.path, fragment=up.fragment)
                    log.info("Got page %s %r", page, page_args)
                    result = page.analyze(driver)
                    
                    for level, key, value in result.pretty_dom():
                        print('  ' * level, key, value)
                
                    break
                except KeyError as e:
                    log.warning("URL path not templated. %s: %s", e, up.path)
                except Exception as e:
                    log.warning("Could not resolve elements:", exc_info=True)
                    break

            # no useful result here, sleeping
            time.sleep(5)
        except KeyboardInterrupt:
            log.warning("Received interrupt, exiting")
            break

    # driver.close()   # should be done by remote
    log.info("Bye")


if __name__ == '__main__':
    cmdline_main()


#eof

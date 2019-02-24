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
from behave_manners.pagelems.main import DSiteCollection, FSLoader
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


def shorten_txt(txt, maxlen):
    if not txt:
        return txt
    txt = txt.split('\n', 1)[0]
    if len(txt) > maxlen:
        txt = txt[:maxlen] + '...'
    return txt


def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='Try DPO templates against open page')
    parser.add_argument('-f', '--full-site', action='store_true', default=False,
                        help='Check all site, not just index')
    parser.add_argument('-s', '--session-file', default='dbg-browser.session',
                        help="Path to file with saved Remote session")
    parser.add_argument('index', metavar='index.html', nargs='?',
                        help="path to 'index.html' file")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    site = DSiteCollection(FSLoader('.'))
    log = logging.getLogger('main')

    with open(args.session_file, 'rb') as fp:
        sdata = json.load(fp)
    if 'url' in sdata and 'session' in sdata:
        driver = ExistingRemote(command_executor=sdata['url'],
                                session_id = sdata['session'])
    else:
        raise RuntimeError("Saved session must have 'url' and 'session' set")

    if args.index:
        log.debug("Loading index from %s", args.index[0])
        site.load_index(args.index[0])
    elif sdata.get('page_objects', {}).get('index'):
        log.debug("Loading index from %s", sdata['page_objects']['index'])
        site.load_index(sdata['page_objects']['index'])
    else:
        raise RuntimeError("Session does not contain 'page_objects' and no index specified in arguments")
    site.load_preloads()

    log.info("Site collection contains %d pages, %d files",
             len(site.page_dir), len(site.file_dir))

    def _get_cur_path(cur_url):
        if sdata.get('base_url'):
            if cur_url.startswith(sdata['base_url']):
                return cur_url[len(sdata['base_url']):]
            else:
                log.warning("Current url not under base_url")
                return None
        else:
            # Try to decode URL, assume site at /
            up = urlparse.urlparse(cur_url)
            if up.scheme not in ('http', 'https'):
                log.warning("Page is in unknown scheme, %s://", up.scheme)
            elif not up.netloc:
                log.warning("Page is not yet at server")
            else:
                return up.path

    log.info("Entering main phase, connected to browser")
    while True:
        try:
            cur_path = _get_cur_path(driver.current_url)
            if cur_path is not None:
                try:
                    site_ctx = site.get_context()
                    page, title, page_args = site.get_by_url(cur_path, fragment=None)
                    log.info("Got page %s %r", title, page_args)

                    for path, elem in page.walk(driver, parent_ctx=site_ctx):
                        print('  ' * len(path), '/'.join(path), elem)
                        for a in dir(elem):
                            try:
                                print('  '* len(path), ' ' * 20, a, 
                                      '= %s' % shorten_txt(getattr(elem, a), 40))
                            except Exception, e:
                                print('  '* len(path), ' ' * 20, a, '= %s' % type(e))

                    break
                except KeyError as e:
                    log.warning("URL path not templated. %s: %s", e, cur_path)
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

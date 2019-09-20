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
import sys
import os.path
import six
import inspect
import pprint
import traceback
from selenium import webdriver
from selenium.webdriver.remote.command import Command
from behave.runner_util import exec_file
from behave_manners.site import FakeContext
from behave_manners.pagelems.main import DSiteCollection, FSLoader
from behave_manners.pagelems.exceptions import ElementNotFound, CKeyError
from behave_manners.pagelems.helpers import Integer, count_calls
from behave_manners.pagelems.dom_components import ComponentProxy
from behave_manners.pagelems.scopes import Fresh
from six.moves.urllib import parse as urlparse
from behave_manners import screenshots
try:
    import rlcompleter
    import readline
except ImportError:
    readline = None

HISTORY_FILE = '~/.behave-manners-history'


class ExistingRemote(webdriver.Remote):
    """Remote webdriver that attaches to existing session
    """
    def __init__(self, command_executor, session_id, saved_capabilities,
                 desired_capabilities={}, saved_w3c=None, **kwargs):
        self.__session_id = session_id
        self.__saved_caps = saved_capabilities
        self.__saved_w3c = saved_w3c
        super(ExistingRemote, self).__init__(command_executor=command_executor,
                                             desired_capabilities=desired_capabilities,
                                             **kwargs)

    def start_session(self, desired_capabilities, browser_profile=None):
        if not self.__session_id:
            raise RuntimeError("session_id must be specified in constructor")
        if self.__saved_caps and self.__saved_caps.get('browserName', '') == 'firefox':
            # Geckodriver does not support the 'GET_ALL_SESSIONS' command,
            # so have to trust data from JSON and go directly to that session
            self.session_id = self.__session_id
            self.capabilities = self.__saved_caps
            if self.__saved_w3c is not None:
                self.w3c = self.__saved_w3c
            else:
                self.w3c = "specificationLevel" in self.capabilities
            return

        res = self.execute(Command.GET_ALL_SESSIONS)
        if res != 0:
            for session in res['value']:
                if session['id'] == self.__session_id:
                    self.session_id = self.__session_id
                    self.capabilities = session['capabilities']
                    if self.__saved_w3c is not None:
                        self.w3c = self.__saved_w3c
                    else:
                        self.w3c = "specificationLevel" in self.capabilities
                    break
            else:
                raise RuntimeError("Remote webdriver does not contain saved session")
        else:
            raise RuntimeError("Cannot get remote webdriver sessions")


def shorten_txt(txt, maxlen):
    if not txt:
        return txt
    if not isinstance(txt, six.string_types):
        return txt
    txt = txt.split('\n', 1)[0]
    if len(txt) > maxlen:
        txt = txt[:maxlen] + '...'
    return txt


class _dummy_decorator(object):
    def __init__(self, txt, *args):
        pass

    def __call__(self, fn):
        return fn


def import_step_modules(paths, modules):
    """Import any python module under 'paths', store its names in 'modules/xx'
    
        This is used to implicitly register ServiceMeta classes defined in these
        step modules.
    """
    dglobals = globals().copy()
    for key in ('given', 'when', 'then', 'step'):
        dglobals[key] = dglobals[key.title()] = _dummy_decorator

    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.endswith(".py"):
                    globs = modules[p + '/' + name] = dglobals.copy()
                    exec_file(os.path.join(p, name), globs)
        elif os.path.isfile(p):
            assert p.endswith('.py')
            modules[p] = dglobals.copy()
            exec_file(p, modules[p])


def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='Try DPO templates against open page')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="Print debugging messages")
    parser.add_argument('-i', '--interactive', action='store_true', default=False,
                        help='Interactive mode: python prompt instead of walking')
    parser.add_argument('-f', '--full-site', action='store_true', default=False,
                        help='Check all site, not just index')
    parser.add_argument('-s', '--session-file', default='dbg-browser.session',
                        help="Path to file with saved Remote session")
    parser.add_argument('-p', '--screenshots',
                        help="Capture screenshots in this directory")
    parser.add_argument('--index', metavar='index.html',
                        help="path to 'index.html' file")
    parser.add_argument('-d', '--max-depth', type=int,
                        help="Max depth of components to discover")
    parser.add_argument('--measure-selenium', action='store_true',
                        help="Count number of selenium commands invoked")
    parser.add_argument('--pollute-data', action='store_true',
                        help="Set component names as data property on remote DOM")
    parser.add_argument('-M', '--animate', action='store_true',
                        help="Highlight each element discovered, animate")
    parser.add_argument('path', metavar="component", nargs="*",
                        help="Resolve components only under that path")

    args = parser.parse_args()
    errors = Integer(0)

    logging.basicConfig(level=args.verbose and logging.DEBUG or logging.INFO)
    site = DSiteCollection(FSLoader('.'))
    log = logging.getLogger('main')

    with open(args.session_file, 'rt') as fp:
        sdata = json.load(fp)
    if 'url' in sdata and 'session' in sdata:
        driver = ExistingRemote(command_executor=sdata['url'],
                                session_id=sdata['session'],
                                saved_capabilities=sdata.get('capabilities',{}),
                                saved_w3c=sdata.get('w3c', None),
                                keep_alive=sdata.get('keep_alive', True))
    else:
        raise RuntimeError("Saved session must have 'url' and 'session' set")

    bmodules = {}
    try:
        # Import steps modules a-la behave
        import_step_modules(['environment.py', 'steps'], bmodules)
        log.info("Loaded %d python modules relative to behave", len(bmodules))
    except Exception:
        log.warning("Cannot load behave environment and steps:", exc_info=True)

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

    camera = None
    becontext = FakeContext()
    becontext.browser = driver
    if args.screenshots or args.animate:
        camera = screenshots.Camera(args.screenshots or '.')

    def _get_cur_path(cur_url):
        if sdata.get('base_url'):
            if cur_url.startswith(sdata['base_url']):
                return cur_url[len(sdata['base_url']):].split('?', 1)[0]
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
    def path_str(path):
        return '/'.join([str(x) for x in path])

    def print_enoent(comp, exc, shoot=True):
        e = errors  # transfer from outer to local scope
        e += 1
        
        if isinstance(exc, ElementNotFound):
            print("    %s inside %s" % (exc.msg, comp))
            if camera and shoot and args.screenshots:
                camera.capture_missing_elem(becontext, exc.parent, exc.selector)
        elif isinstance(exc, CKeyError):
            print("    Missing %s inside component %s" % (exc, comp))
            if camera and shoot and args.screenshots:
                camera.capture_missing_elem(becontext, exc.component._remote, exc.args[0])
        elif isinstance(exc, KeyError):
            print("    Missing '%s' inside component %s" % (exc, comp))

        return True  # want walk() to continue

    def walk_validate(comp):
        """Walk all elements and print them, mode of operation
        """
        errors_l = errors
        if args.pollute_data:
            pelems = driver.find_elements_by_xpath('//*[@data-manners-component]')
            log.debug("Cleaning %d elements from previous pollution", len(pelems))
            if pelems:
                driver.execute_script(
                    "arguments[0].forEach(function(e) { "
                    "    e.removeAttribute('data-manners-component');"
                    " });", pelems)

        for path, elem in page.walk(driver, parent_scope=site_scp,
                                    on_missing=print_enoent,
                                    starting_path=comp,
                                    max_depth=args.max_depth or 1000):
            print('  ' * len(path), path_str(path), elem)
            if args.pollute_data and isinstance(elem, ComponentProxy):
                driver.execute_script(
                    "arguments[0].setAttribute('data-manners-component',"
                                                "arguments[1]);",
                    elem._remote, elem.component_name);

            if args.animate:
                with camera.highlight_element(becontext, component=elem,
                                                border='none', color='rgba(14, 118, 255, 0.4)'):
                    time.sleep(0.2)

            for a in dir(elem):
                try:
                    val = getattr(elem, a)
                    if not callable(val):
                        print('  '* len(path), ' ' * 20, a,
                                '= %s' % shorten_txt(val, 40))
                except ElementNotFound as e:
                    print('  '* len(path), ' ' * 20, a, '= X')
                    print_enoent(elem, e)
                except Exception as e:
                    exc_first_line = str(e).split('\n',1)[0]
                    print('  '* len(path), ' ' * 20, a, ': ' + exc_first_line)
                    errors_l += 1

        if args.measure_selenium:
            log.info("Used %d calls to walk", ExistingRemote.execute.count)

    def _exit_this():
        raise EOFError()

    def run_interactive(page, comp, scope):
        from behave_manners.pagelems.filter_components import toInt, toFloat
        iglobals = {
            '__builtins__': __builtins__,
            'toInt': toInt,
            'toFloat': toFloat,
        }
        ilocals = {
            'cur_page': page,
            'root_scope': scope,
            'comp': comp,
            'context': becontext,
            'Fresh': Fresh,
            'exit': _exit_this,
            '_': None,
            }

        def _recover_stale(comp):
            with Fresh(scope):
                comp._recover_stale()

        ilocals['recover_stale'] = _recover_stale

        if readline is not None:
            history_file = os.path.expanduser(HISTORY_FILE)
            readline.parse_and_bind("tab: complete")
            readline.set_completer(rlcompleter.Completer(ilocals).complete)
            try:
                readline.read_history_file(history_file)
            except IOError as e:
                if e.errno != 2:
                    log.info("Cannot read history: %s", e)

        # assignment_re = re.compile('[^=]=[^=]')
        while True:
            if isinstance(ilocals.get('comp', None), ComponentProxy):
                prompt = '%s > ' % ilocals['comp'].component_name
            else:
                prompt = '#Page > '
            try:
                cmd = six.moves.input(prompt)
                if not cmd.strip():
                    continue
                if cmd.endswith(':'):
                    while True:
                        line = six.moves.input(prompt)
                        if not line.startswith(' '):
                            break
                        cmd += '\n' + line
                    aste = compile(cmd, '<input>', 'exec')
                else:
                    try:
                        aste = compile(cmd, '<input>', 'eval')
                    except SyntaxError:
                        aste = compile(cmd, '<input>', 'single')

                res = eval(aste, iglobals, ilocals)
                if res is None:
                    pass
                elif inspect.isgenerator(res):
                    pprint.pprint(list(res))
                else:
                    pprint.pprint(res)
                ilocals['_'] = res
            except EOFError:
                break
            except KeyboardInterrupt:
                break
            except Exception:
                traceback.print_exc()

        print()
        if readline is not None:
            try:
                readline.write_history_file(history_file)
                log.debug("History saved")
            except IOError as e:
                log.warning("Cannot save history: %s", e)


    if args.measure_selenium:
        ExistingRemote.execute = count_calls(ExistingRemote.execute)

    while True:
        try:
            cur_path = _get_cur_path(driver.current_url)
            if cur_path is not None:
                try:
                    if args.measure_selenium:
                        ExistingRemote.execute.reset_count()
                    site_scp = site.get_root_scope()
                    page, title, page_args = site.get_by_url(cur_path, fragment=None)
                    log.info("Got page %s %r", title, page_args)

                    comp = page.get_root(driver, site_scp)
                    page_root = comp
                    try:
                        for p in args.path:
                            comp = comp[p]
                    except (ElementNotFound, KeyError) as e:
                        print_enoent(comp, e, shoot=False)
                        print("Waiting for it to appear")
                        time.sleep(3.0)
                        continue

                    errors -= errors  # reset, in-place
                    if args.interactive:
                        run_interactive(page_root, comp, site_scp)
                    else:
                        walk_validate(comp)
                    break
                except KeyError as e:
                    log.warning("URL path not templated. %s: '%s'", e, cur_path)
                except Exception as e:
                    log.warning("Could not resolve elements:", exc_info=True)
                    errors += 1
                    break

            # no useful result here, sleeping
            time.sleep(5)
        except KeyboardInterrupt:
            log.warning("Received interrupt, exiting")
            break

    # driver.close()   # should be done by remote
    if errors:
        log.warning("Validation finished, %s errors", errors or 'no')
        return 1
    else:
        log.info("Validation finished, no errors")
        return 0


if __name__ == '__main__':
    r = cmdline_main()
    sys.exit(r and 1)


#eof

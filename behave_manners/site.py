# -*- coding: UTF-8 -*-
"""
"""

from __future__ import absolute_import, print_function
import time
from selenium import webdriver
import os
import yaml
import six
from f3utils.dict_tools import merge_dict
import os.path
import re
from behave.model_core import Status
import logging
import urllib3.exceptions
# from six.moves.urllib import parse as urlparse
from .context import EventContext


log = logging.getLogger(__name__)

def _noop_fn(context, *args):
    pass


seconds_re = re.compile(r'([1-9]\d+)(m?)s(?:ec)?$')


class SiteContext(object):
    """Holds (web)site information in a behave context
    
        A SiteContext is attached to behave's context like
            `context.site = SiteContext(...)`
        and from there on tests can refer to site-wide attributes
        through that `context.site` object.
    """

    def __init__(self, context, config=None):
        self._config = config or {}
        self.__orig_hooks = context._runner.hooks.copy()
        context.config.setup_logging()
        self._log.debug("site setup at %s" % getattr(context, '@layer', '?'))
        self.events = EventContext()

        hook_names = {}
        for htime in ('before', 'after'):
            for hevent in ('all', 'feature', 'scenario', 'step'):
                self.__setup_hook(htime, hevent, context)
                hook_names[htime + '_' + hevent] = None

        self.events.update(**hook_names)
        self.events.push()
        context.add_cleanup(self.__cleanup_site, context)
        self._collection = None
        self.output_dir = '.'
        if 'output' in config and 'dir' in config['output']:
            self.output_dir = config['output']['dir']\
                    .format(pid=os.getpid(), timestamp=int(time.time()),
                            userdata=context.config.userdata)
            self._log.info("Storing all output under: %s", self.output_dir)

    def __setup_hook(self, htime, hevent, context):
        hkey = htime + '_' + hevent
        rhooks = context._runner.hooks
        orig_fn = self.__orig_hooks.get(hkey, _noop_fn)
        if htime == 'before':
            # Resolutions from self.events must happen at runtime,
            # in order to use the running context then
            def __hook_fn(context, *args):
                orig_fn(context, *args)
                getattr(self.events, hkey)(context, *args)
        elif htime == 'after':
            def __hook_fn(context, *args):
                getattr(self.events, hkey)(context, *args)
                orig_fn(context, *args)
        else:
            raise RuntimeError(htime)
        rhooks[hkey] = __hook_fn

    def __cleanup_site(self, context):
        self.events.pop()
        rhooks = context._runner.hooks
        rhooks.clear()
        rhooks.update(self.__orig_hooks)
        self.__orig_hooks.clear()
        try:
            del context.site
        except AttributeError:
            pass

    @classmethod
    def _load_config(cls, cfname, extra_conf=None):
        # TODO: use glob on cfname
        try:
            # Change directory to that of cfname, so that all mentioned
            # includes are searched relative to this one
            old_cwd = os.getcwd()
            pdir, fname = os.path.split(cfname)

            if pdir:
                os.chdir(pdir)
            with open(fname, 'rb') as fp:
                config = yaml.safe_load(fp)
            if not config:
                raise ValueError("Empty config at: %s" % cfname)
            if not isinstance(config, dict):
                raise TypeError("Config file \"%s\" does not have a dict root" % cfname)
            includes = config.pop('include', [])
            new_include = []
            for incl in includes:
                if isinstance(incl, dict):
                    new_cfg = cls._load_config(incl['file'])
                    if incl.get('when'):
                        new_include.append((incl['when'], new_cfg))
                    else:
                        merge_dict(config, new_cfg, copy=False)
                elif isinstance(incl, six.string_types):
                    sub_conf = cls._load_config(incl)
                    merge_dict(config, sub_conf, copy=False)
                else:
                    raise TypeError("Cannot load config: %r" % incl)
            if new_include:
                config['include'] = new_include
            if extra_conf:
                merge_dict(config, extra_conf, copy=False)
            return config
        except IOError:
            raise
        finally:
            os.chdir(old_cwd)

    @property
    def base_url(self):
        return self._config['site']['base_url']

    def init_collection(self):
        if self._collection is not None:
            return
        from .pagelems import FSLoader, DSiteCollection

        po_config = self._config['page_objects']
        self._collection = DSiteCollection(FSLoader('.'), po_config)
        index = po_config.get('index', 'index.html')
        log.debug("Loading index from %s", index)
        self._collection.load_index(index)
        self._collection.load_preloads()


class WebContext(SiteContext):
    _log = logging.getLogger('behave.site.webcontext')

    def __init__(self, context, config=None):
        super(WebContext, self).__init__(context, config)
        # install hooks
        self.events.update(before_feature=self._event_before_feature,
                           before_scenario=self._event_before_scenario,
                           after_step=self._event_after_step,
                           after_step_failed=None,
                           on_missing_element=None)
        self.events.push()
        self._config.setdefault('browser', {})
        self._browser_log_types = []
        self._implicit_sec = 0
        context.add_cleanup(self.events.pop)

    def launch_browser(self, context):
        browser_opts = self._config['browser']
        caps = {}
        caps['record_network'] = 'true'
        caps['take_snapshot'] = 'true'

        desired_engine = browser_opts.get('engine', 'chrome').lower()

        allow_downloads = False     # on an empty config
        download_dir = None
        if 'downloads' in browser_opts:
            if browser_opts['downloads'].get('allow', True):
                allow_downloads = True

                if getattr(context, 'download_dir', None):
                    # read it FROM the context
                    download_dir = context.download_dir
                else:
                    download_dir = os.path.abspath(
                            os.path.join(self.output_dir,
                                        browser_opts['downloads'].get('dir', 'downloads')))
                    if not os.path.exists(download_dir):
                        os.makedirs(download_dir)
                    context.download_dir = download_dir

        if desired_engine == 'chrome':
            options = webdriver.ChromeOptions()
            dcaps = webdriver.DesiredCapabilities.CHROME.copy()
            dcaps['loggingPrefs'] = {'driver': 'WARNING', 'browser': 'ALL'}
            if browser_opts.get('log_performance', False):
                dcaps['loggingPrefs']['performance'] = 'ALL'
                dcaps['perfLoggingPrefs'] = {'enableNetwork': True, 'enablePage': True}
            dcaps.update(caps)
            if 'binary_location' in browser_opts:
                options.binary_location = browser_opts['binary_location']
            if browser_opts.get('headless', True):
                options.add_argument('headless')
            options.add_argument('disable-infobars')
            if browser_opts.get('no_automation', False):
                options.add_experimental_option('useAutomationExtension', False)
            if 'window' in browser_opts:
                w, h = self._decode_win_size(browser_opts['window'])
                options.add_argument('window-size=%d,%d' % (w, h))

            if allow_downloads:
                options.add_experimental_option("prefs", {
                    "download.default_directory": download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                    })

            context.browser = webdriver.Chrome(chrome_options=options,
                                               desired_capabilities=dcaps,
                                               service_args=browser_opts\
                                                   .get('chromedriver_args', []))
            self._browser_log_types = context.browser.log_types

        elif desired_engine == 'firefox':
            options = webdriver.FirefoxOptions()
            dcaps = webdriver.DesiredCapabilities.FIREFOX.copy()
            dcaps.update(caps)
            if 'binary_location' in browser_opts:
                options.binary_location = browser_opts['binary_location']
            options.headless = browser_opts.get('headless', True)
            profile = webdriver.FirefoxProfile()

            if allow_downloads:
                profile.set_preference("browser.download.folderList", 2)
                profile.set_preference("browser.download.manager.showWhenStarting", False)
                profile.set_preference("browser.download.dir", download_dir)
                profile.set_preference("browser.download.loglevel", "Info")
                profile.set_preference("browser.download.forbid_open_with", True)
                # profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")

            context.browser = webdriver.Firefox(firefox_profile=profile,
                                                firefox_options=options,
                                                desired_capabilities=dcaps,
                                                service_args=browser_opts\
                                                    .get('geckodriver_args', []))
            if 'window' in browser_opts:
                w, h = self._decode_win_size(browser_opts['window'])
                context.browser.set_window_size(w,h)
            self._browser_log_types = []   # ['browser', 'driver', 'client', 'server']
        elif desired_engine == 'iexplorer':
            options = webdriver.IeOptions()
            dcaps = webdriver.DesiredCapabilities.INTERNETEXPLORER.copy()
            dcaps.update(caps)
            if 'binary_location' in browser_opts:
                options.binary_location = browser_opts['binary_location']
            context.browser = webdriver.Ie(ie_options=options,
                                           desired_capabilities=dcaps)
            if 'window' in browser_opts:
                w, h = self._decode_win_size(browser_opts['window'])
                context.browser.set_window_size(w,h)
            self._browser_log_types = []
        else:
            raise NotImplementedError('Unsupported engine: %s' % desired_engine)

        if browser_opts.get('implicit_wait'):
            m = seconds_re.match(browser_opts['implicit_wait'])
            if not m:
                raise ValueError("Invalid implicit wait: %s" % browser_opts['implicit_wait'])
            self._implicit_sec = float(int(m.group(1)))
            if not m.group(2):
                pass
            elif m.group(2) == 'm':
                self._implicit_sec /= 1000.0
            else:
                raise ValueError("Unknown multiplier: %s" % m.group(2))
            context.browser.implicitly_wait(self._implicit_sec)
        context.add_cleanup(self._release_browser, context)

    _pixel_size_re = re.compile(r'(\d+)x(\d+)$')

    def _decode_win_size(self, size_str):
        m = self._pixel_size_re.match(size_str)
        if m:
            width = int(m.group(1))
            height = int(m.group(2))

            if not ((150 <= width <= 10000) and (150 <= height <= 10000)):
                raise ValueError("Invalid size: %d x %d"  % (width, height))
            return width, height

        # TODO: short-name sizes
        raise ValueError("Cannot parse size=\"%s\"" % size_str)

    def _release_browser(self, context):
        """Release or destroy the browser after context has finished with it
        """
        self._log.info("cleanup browser")
        context.browser.quit()

    def _event_before_feature(self, context, feature):
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'feature' or \
                (browser_launch == 'scenario' and 'serial' in feature.tags):
            self.launch_browser(context)

    def _event_before_scenario(self, context, scenario):
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'scenario' and 'serial' not in scenario.feature.tags:
            self.launch_browser(context)

    def _event_after_step(self, context, step):
        if step.status == Status.failed:
            self._log.warning("Step: \"%s\" failed.\n%s", step.name, step.exception or "no exception")
            self.events.after_step_failed(context, step)
        try:
            self.process_logs(context)
        except urllib3.exceptions.RequestError as e:
            self._log.warning("Could not fetch logs, browser closed?\n%s", e)
        except Exception as e:
            self._log.error("Could not fetch step logs: %s", e)

    def process_logs(self, context):
        for lt in self._browser_log_types:
            self._push_log_entries(lt, context.browser.get_log(lt), _cleanup_logentry)

    def _push_log_entries(self, logname, entries, fmt_func=None):
        """Push a bunch of collected log entries under some logger

        """
        if fmt_func is not None:
            entries = map(fmt_func, entries)

        log = logging.getLogger('behave.site.' + logname)
        for entry in entries:
            rec = logging.LogRecord(log.name, entry['level'], __file__, 0,
                 entry['message'], (), entry.get('exc_info'))
            ct = entry.get('timestamp', time.time())
            rec.created = ct
            rec.msecs = (ct - int(ct)) * 1000
            log.handle(rec)

    def _root_scope(self, context, do_set=True):
        """Return root-level scope, initializing if needed

            :param do_set: keep newly created scope in `context.pagelems_scope`
        """
        try:
            return context.pagelems_scope
        except AttributeError:
            new_scope = self._collection.get_root_scope()
            if do_set:
                context.pagelems_scope = new_scope
            return new_scope

    def navigate_by_title(self, context, title, force=False):
        """Open a URL, by pretty title
        """
        url = self.base_url
        page, purl = self._collection.get_by_title(title)
        if purl is None:
            raise KeyError("No url for %s" % title)
        if url.endswith('/') and purl.startswith('/'):
            url = url[:-1]
        url = url + purl
        self._log.debug("Navigating to %s", url)
        # TODO: up = urlparse.urlparse(driver.current_url)
        if force or context.browser.current_url != url:
            context.browser.get(url)
        scp = self._root_scope(context)
        context.cur_page = page.get_root(context.browser, parent_scope=scp)
        context.cur_page.wait_all('medium')

    def get_cur_title(self, context):
        #up = urlparse.urlparse()
        cur_url = context.browser.current_url
        if cur_url.startswith(self.base_url):
            cur_url = cur_url[len(self.base_url):].split('?', 1)[0]
        else:
            self._log.warning("Browser at %s, not under base url", cur_url)
            return None

        try:
            page, title, params = self._collection.get_by_url(cur_url)
            return title
        except KeyError:
            self._log.warning("No match for url: %s", cur_url)
            return None

    def navigate_by_url(self, context, url, force=False):
        # TODO: up = urlparse.urlparse(driver.current_url)
        curl = url.split('?', 1)[0]
        page, title, params = self._collection.get_by_url(curl)
        if self.base_url.endswith('/') and url.startswith('/'):
            url = self.base_url[:-1] + url
        else:
            url = self.base_url + url
        self._log.debug("Navigating to %s", url)
        if force or context.browser.current_url != url:
            context.browser.get(url)
        scp = self._root_scope(context)
        context.cur_page = page.get_root(context.browser, parent_scope=scp)
        context.cur_page.wait_all('medium')

    def validate_cur_page(self, context, max_depth=10000):
        """Validates current browser page against pagelem template

            Current page will be checked by url and the page template
            will be traversed all the way down.

        """
        from .pagelems.dom_components import PageProxy
        from .pagelems.exceptions import ElementNotFound
        cur_url = context.browser.current_url
        if not cur_url.startswith(self.base_url):
            raise AssertionError("Browser at %s, not under base url" % cur_url)
        cur_url = cur_url[len(self.base_url):].split('?', 1)[0]

        try:
            page, title, params = self._collection.get_by_url(cur_url)
            self._log.info("Resolved browser url to \"%s\" page", title)
        except KeyError:
            page = None

        errors = 0
        cur_page = getattr(context, 'cur_page', None)
        if cur_page is not None and not isinstance(cur_page, PageProxy):
            raise RuntimeError("context.cur_page is a %s object" % type(cur_page))
        if cur_page is not None and page is not None:
            if page is cur_page._pagetmpl:
                self._log.info('Perceived current page matches resolved one')
            else:
                self._log.warning("Resolved page does not match one set")
                errors += 1
        elif cur_page is None and page is not None:
            # create new Proxy
            scp = self._root_scope(context, do_set=False)
            cur_page = page.get_root(context.browser, parent_scope=scp)
            cur_page.wait_all('medium')
        elif cur_page is None and page is None:
            raise AssertionError("No current page found, no resolution from URL either")

        num_elems = 0
        stack = [((), cur_page)]
        while stack:
            path, comp = stack.pop()
            self._log.debug("Located %r under %s", comp, '/'.join(path))
            num_elems += 1
            if len(path) >= max_depth:
                break
            try:
                celems = [(path + (n,), c) for n, c in comp.items()]
                celems.reverse()
                stack += celems
            except ElementNotFound as e:
                # TODO
                self._log.error("Cannot locate element: %s under %s",
                                e.selector, e.pretty_parent)
                errors += 1

        if not errors:
            self._log.info("Validated page with %d discovered components", num_elems)
            return True
        else:
            self._log.warning("Validation disovered %d components, found %d errors",
                              num_elems, errors)
            raise AssertionError("Errors found, validation failed")

    def update_cur_page(self, context):
        """Update `context.cur_page` when URL may have changed
        """
        cur_url = context.browser.current_url
        if not cur_url.startswith(self.base_url):
            raise AssertionError("Browser at %s, not under base url" % cur_url)
        cur_url = cur_url[len(self.base_url):].split('?', 1)[0]

        try:
            page, title, params = self._collection.get_by_url(cur_url)
            self._log.debug("Resolved browser url to \"%s\" page", title)
        except KeyError:
            self._log.warning("Browser is no longer at a known page: %s", cur_url)
            page = None
        cur_page = getattr(context, 'cur_page', None)
        if cur_page is not None and page is not None:
            if page is cur_page._pagetmpl:
                return  # still on the same page

        if page is None:
            context.cur_page = None
            return

        self._log.info('Page changed to %s', title or cur_url)
        scp = self._root_scope(context)
        context.cur_page = page.get_root(context.browser, parent_scope=scp)
        context.cur_page.wait_all('medium')
        return title


_wd_loglevels = {'INFO': logging.INFO, 'WARN': logging.WARNING,
                 'SEVERE': logging.ERROR, 'CRITICAL': logging.CRITICAL
                 }

def _cleanup_logentry(rec):
    if 'timestamp' in rec:
        rec['timestamp'] /= 1000.0

    rec['level'] = _wd_loglevels.get(rec.get('level', 'INFO'), logging.INFO)

    return rec


class FakeContext(object):
    """Dummy *behave* context

        Will substitute a proper `behave` context for when manners stuff
        is run outside of a `behave` test suite.
    """
    log = logging.getLogger('context')

    class Runner(object):
        def __init__(self):
            self.hooks = {}

    class Config(object):
        def setup_logging(self):
            pass

    def __init__(self):
        self.browser = None
        self._runner = FakeContext.Runner()
        self.config = FakeContext.Config()
        self.__cleanups = []

    def add_cleanup(self, fn, *args):
        self.__cleanups.append((fn, args))

    def close(self):
        for fn, args in self.__cleanups:
            try:
                fn(*args)
            except Exception as e:
                self.log.warning("Could not cleanup: %s", e)


#eof

# -*- coding: UTF-8 -*-
"""
"""

from __future__ import absolute_import, print_function
import errno
import logging
import os
import os.path
import re
import six
import shutil
import time
import yaml
import urllib3.exceptions

from f3utils.dict_tools import merge_dict
from f3utils.service_meta import abstractmethod, _ServiceMeta

from selenium import webdriver
from behave.model_core import Status
# from six.moves.urllib import parse as urlparse
from .context import EventContext


log = logging.getLogger(__name__)

def _noop_fn(context, *args):
    pass


seconds_re = re.compile(r'([1-9]\d+)(m?)s(?:ec)?$')


class RemoteSiteError(Exception):
    """Raised on errors detected at remote (browser) side
    """
    def __init__(self, message, **kwargs):
        Exception.__init__(self, message)
        self.__dict__.update(kwargs)


class RemoteNetworkError(RemoteSiteError):
    pass


@six.add_metaclass(_ServiceMeta)
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
        self.tempdir = None
        if 'output' in config:
            if 'dir' in config['output']:
                self.output_dir = config['output']['dir']\
                        .format(pid=os.getpid(), timestamp=int(time.time()),
                                userdata=context.config.userdata)
                self._log.info("Storing all output under: %s", self.output_dir)
            if 'tempdir' in config['output']:
                self.tempdir = config['output']['tempdir']\
                        .format(pid=os.getpid(), timestamp=int(time.time()),
                                userdata=context.config.userdata)
                self._log.debug("Using temporary dir: %s", self.output_dir)
                self.tempdir = os.path.abspath(self.tempdir)
                if os.path.exists(self.tempdir):
                    raise IOError(errno.EEXIST, "Temporary directory already exists: %s" % self.tempdir)
                os.makedirs(self.tempdir)

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
            if self.tempdir:
                shutil.rmtree(self.tempdir)
        except Exception as e:
            self._log.warning("Could not cleanup tempdir: %s", e)
        try:
            del context.site
        except AttributeError:
            pass

    @classmethod
    def _load_config(cls, cfnames, loader, extra_conf=None):
        """Load one (or more) configuration files into a dict

            :param cfnames: string or list of config filenames
                in order from least to most significant (override)
            :param loader: a BaseLoader to open the files
            :param extra_conf: dict, extra configuration to apply at the end

        """
        if isinstance(cfnames, six.string_types):
            cfnames = [cfnames,]
        elif isinstance(cfnames, (tuple, list)):
            pass
        else:
            raise TypeError(type(cfnames))

        result = {}

        nloaded = 0
        for cfname_pat in cfnames:
            for cfname, fp in loader.multi_open(cfname_pat, mode='rt'):
                nloaded += 1
                config = yaml.safe_load(fp)
                if not config:
                    raise ValueError("Empty config at: %s" % cfname)
                if not isinstance(config, dict):
                    raise TypeError("Config file \"%s\" does not have a dict root" % cfname)

                includes = config.pop('include', [])
                if includes:
                    res = cls._load_config(includes, loader)
                    merge_dict(result, res, copy=False)
                merge_dict(result, config, copy=False)

        if not nloaded:
            raise IOError(errno.ENOENT, "No config file found")
        if extra_conf and callable(extra_conf):
            extra_conf(config)
        elif extra_conf:
            merge_dict(config, extra_conf, copy=False)

        return result

    @property
    def base_url(self):
        return self._config['site']['base_url']

    def init_collection(self, loader=None):
        if self._collection is not None:
            return
        from .pagelems import FSLoader, DSiteCollection
        if loader is None:
            loader = FSLoader('.')

        po_config = self._config['page_objects']
        self._collection = DSiteCollection(loader, po_config)
        index = po_config.get('index', 'index.html')
        log.debug("Loading index from %s", index)
        self._collection.load_index(index)
        self._collection.load_preloads()


class WebContext(SiteContext):
    """Site context when a browser needs to be launched
    """
    _name = 'browser'
    _log = logging.getLogger('behave.site.webcontext')
    _browser_log_types = ()

    _wd_loglevels = {'INFO': logging.INFO, 'WARN': logging.WARNING,
                    'SEVERE': logging.ERROR, 'CRITICAL': logging.CRITICAL
                    }

    fourOfours = ('/favicon.ico',)  # paths where a 404 is expected


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
        self._implicit_sec = 0
        context.add_cleanup(self.events.pop)

    def _setup_downloads(self, context):
        browser_opts = self._config['browser']
        if 'downloads' in browser_opts:
            from .downloads import DownloadManager
            if browser_opts['downloads'].get('allow', True):

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
                context.downloads = DownloadManager(context.download_dir)
                return download_dir
        return None

    def launch_browser(self, context):
        """Launch a browser, attach it to `context.browser`

        """
        browser_opts = self._config['browser']
        caps = {}
        caps['record_network'] = 'true'
        caps['take_snapshot'] = 'true'

        dwdir = self._setup_downloads(context)
        context.browser = self._launch_browser2(caps, download_dir=dwdir)
        context.add_cleanup(self._release_browser, context)

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

        if browser_opts.get('startup_url'):
            url = browser_opts['startup_url']
            if not url.startswith(('about:', 'http:', 'https:')):
                if url.startswith('/') and self.base_url.endswith('/'):
                    url = url[1:]
                url = self.base_url + url
            context.browser.get(url)

    @abstractmethod
    def _launch_browser2(self, caps):
        raise NotImplementedError('Unsupported engine')

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
        self._log.debug("cleanup browser")
        context.browser.quit()

    def _event_before_feature(self, context, feature):
        # parent_fn(context, None, feature)  must be __noop_fn
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'feature' or \
                (browser_launch == 'scenario' and 'serial' in feature.tags):
            self.launch_browser(context)

    def _event_before_scenario(self, context, scenario):
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'scenario' and 'serial' not in scenario.feature.tags:
            self.launch_browser(context)
        if hasattr(context, 'downloads'):
            self._log.debug("Resetting downloads")
            context.downloads.reset()

    def _event_after_step(self, context, step):
        if step.status == Status.failed:
            try:
                msg_url = "Browser currently at: %s\n" % context.browser.current_url
            except Exception:
                msg_url = ''
            self._log.warning("Step: \"%s\" failed.\n%s%s", step.name,
                              msg_url, step.exception or "no exception")
            self.events.after_step_failed(context, step)
        try:
            self.process_logs(context)
        except urllib3.exceptions.RequestError as e:
            self._log.warning("Could not fetch logs, browser closed?\n%s", e)
        except Exception as e:
            self._log.error("Could not fetch step logs: %s", e)

    def process_logs(self, context, consumer=None):
        """Fetch logs from browser and process them

            :param silent: suppress exceptions arising from logs
        """
        if consumer is None:
            consumer = self._consume_log
        for rec in self._get_log_entries(context):
           consumer(rec)

    def _get_log_entries(self, context):
        for lt in self._browser_log_types:
            for entry in context.browser.get_log(lt):
                if 'source' in entry:
                    log_name = '%s.%s' % (lt, entry['source'])
                else:
                    log_name =  lt
                level = self._wd_loglevels.get(entry.get('level', ''), logging.INFO)
                rec = logging.LogRecord(log_name, level, __file__, 0,
                                        entry['message'], (), entry.get('exc_info'))

                if 'timestamp' in entry:
                    ct = entry['timestamp'] / 1000.0
                else:
                    ct = time.time()
                rec.created = ct
                rec.msecs = (ct - int(ct)) * 1000

                patterns = self._log_decoders.get(log_name, {}).get(level, [])
                for pat in patterns:
                    # decode fields of that message into extra log-record attributes
                    m = pat.match(entry['message'])
                    if m:
                        rec.__dict__.update(m.groupdict())
                yield rec

    def _consume_log(self, rec):
        """Handle some log record emitted by the browser

            Override this to affect state of the browser according to log
            messages received.
        """
        rec.name = 'behave.site.' + rec.name
        log = logging.getLogger(rec.name)
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

    def navigate_by_title(self, context, title, **kwargs):
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
        self._load_url(context, page, url, **kwargs)

    def _load_url(self, context, page, url, force=False, soft=None, wait='medium'):
        """Tell the browser to navigate to some URL

            It may not always work: some race conditions with pending scripts
            also trying to set the location may contend with this one.
            So, perform a few retries to do that.
        """
        if soft is None:
            soft = self._config['browser'].get('soft_change', False)

        if force:
            cur_url = False
        else:
            cur_url = context.browser.current_url

        def consume_message(rec):
            if rec.name == 'browser.network' and rec.levelno == logging.ERROR:
                if getattr(rec, 'url', None) == url:
                    raise RemoteNetworkError(rec.message, url=rec.url,
                                            status=getattr(rec, 'status', None))
                elif getattr(rec, 'url', '').endswith(self.fourOfours):
                    return
            self._consume_log(rec)

        for x in range(self._config['browser'].get('change_retries', 3)):
            if cur_url == url:
                break
            if soft:
                r = context.browser.execute_script('window.location = arguments[0];', url)
            else:
                r = context.browser.get(url)
            self._log.debug("Load url response: %r", r)
            self.process_logs(context, consumer=consume_message)
            old_url = cur_url
            cur_url = context.browser.current_url
            if cur_url != old_url:
                # something changed, may still not be `url`
                break
            time.sleep(0.5)

        scp = self._root_scope(context)
        context.cur_page = page.get_root(context.browser, parent_scope=scp)
        if wait:
            context.cur_page.wait_all(wait)

    def get_cur_title(self, context):
        """Return pretty title of page currently loaded on the browser
        """
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

    def navigate_by_url(self, context, url, **kwargs):
        # TODO: up = urlparse.urlparse(driver.current_url)
        curl = url.split('?', 1)[0]
        page, title, params = self._collection.get_by_url(curl)
        if self.base_url.endswith('/') and url.startswith('/'):
            url = self.base_url[:-1] + url
        else:
            url = self.base_url + url
        self._log.debug("Navigating to %s", url)
        self._load_url(context, page, url, **kwargs)

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


class GenericWebContext(SiteContext):
    _name = 'browser.generic'
    _inherit = 'browser'

    def _launch_browser2(self, caps, download_dir):
        return webdriver.Remote(desired_capabilities=caps)


class ChromeWebContext(SiteContext):
    """Web context for Chromium browser
    """
    _name = 'browser.chrome'
    _inherit = 'browser'
    _browser_log_types = ('browser', 'driver')

    def _launch_browser2(self, caps, download_dir):
        """Prepare options for Chromium and call `_launch_browser3()` to start it
        """
        browser_opts = self._config['browser']
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

        if download_dir is not None:
            options.add_experimental_option("prefs", {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
                })

        for opt in ('auth-server-whitelist',):
            val = browser_opts.get(opt.replace('-', '_'), None)
            if val is not None:
                options.add_argument('%s=%s' % (opt, val))

        service_args = browser_opts.get('chromedriver_args', [])
        if browser_opts.get('debug', False):
            service_args.append('--verbose')
            service_args.append('--append-log')
            service_args.append('--log-path=%s/chromedriver.log' % (self.output_dir,))

        browser = self._launch_browser_chrome(
                        options, dcaps,
                        service_args=service_args
                        )
        try:
            self._browser_log_types = browser.log_types
        except Exception as e:
            self._log.warning("Could not retrieve browser log types: %s", e)

        # add missing support for chrome "send_command"  to selenium webdriver
        browser.command_executor._commands["send_command"] = \
                ("POST", '/session/$sessionId/chromium/send_command')

        if download_dir is not None and browser_opts.get('headless', True):
            params = {'cmd': 'Page.setDownloadBehavior',
                      'params': {'behavior': 'allow', 'downloadPath': download_dir}}
            browser.execute("send_command", params)
        return browser

    def _launch_browser_chrome(self, options, dcaps, **kwargs):
        """Launch the browser with specified options, desired_capabilities

            Hook point for last minute or after-launch setup
        """
        return webdriver.Chrome(chrome_options=options,
                                desired_capabilities=dcaps,
                                **kwargs)

    _log_console_regex =  [
        re.compile(r'(?P<url>http(:?s?)://.+?) (?P<lineno>\d+):(?P<linecol>\d+) "(?P<message>.*)"$'),
        re.compile(r'(?P<url>http(:?s?)://.+?) (?P<lineno>\d+):(?P<linecol>\d+) (?P<message>[^"].*)$'),
        ]

    _log_decoders = {
        'browser.network': { logging.ERROR: [
            re.compile(r'(?P<url>.+?) - (?P<message>Failed to load resource: '
                       r'the server responded with a status of (?P<status>\d{3}) .*)$'),
            re.compile(r'(?P<url>.+?) - (?P<message>.*)$'),  # generic
            ],
        },
        'browser.console-api': {
            logging.INFO: _log_console_regex,
            logging.WARNING: _log_console_regex,
            logging.ERROR: _log_console_regex,
        },
        # TODO: performance events
    }


class FirefoxWebContext(SiteContext):
    """Web context for Chromium browser
    """
    _name = 'browser.firefox'
    _inherit = 'browser'

    def _launch_browser2(self, caps, download_dir):
        browser_opts = self._config['browser']
        options = webdriver.FirefoxOptions()
        dcaps = webdriver.DesiredCapabilities.FIREFOX.copy()
        dcaps.update(caps)
        if 'binary_location' in browser_opts:
            options.binary_location = browser_opts['binary_location']
        options.headless = browser_opts.get('headless', True)
        profile = webdriver.FirefoxProfile()

        if download_dir is not None:
            profile.set_preference("browser.download.folderList", 2)
            profile.set_preference("browser.download.manager.showWhenStarting", False)
            profile.set_preference("browser.download.dir", download_dir)
            profile.set_preference("browser.download.loglevel", "Info")
            profile.set_preference("browser.download.forbid_open_with", True)
            # profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-gzip")

        browser = self._launch_browser_ff(profile, options, dcaps,
                                          service_args=browser_opts.get('geckodriver_args', []))
        if 'window' in browser_opts:
            w, h = self._decode_win_size(browser_opts['window'])
            browser.set_window_size(w,h)

        ''' not yet implemented for geckodriver:
        try:
            self._browser_log_types = browser.log_types
        except Exception as e:
            self._log.warning("Could not retrieve browser log types: %s", e)
        '''
        return browser

    def _launch_browser_ff(self, profile, options, dcaps, **kwargs):
        browser = webdriver.Firefox(firefox_profile=profile,
                                    firefox_options=options,
                                    desired_capabilities=dcaps,
                                    **kwargs)
        return browser


class IExploderWebContext(SiteContext):
    """Web context for Chromium browser
    """
    _name = 'browser.iexplorer'
    _inherit = 'browser'

    def _launch_browser2(self, caps, download_dir):
        browser_opts = self._config['browser']
        options = webdriver.IeOptions()
        dcaps = webdriver.DesiredCapabilities.INTERNETEXPLORER.copy()
        dcaps.update(caps)
        if 'binary_location' in browser_opts:
            options.binary_location = browser_opts['binary_location']
        browser = self._launch_browser_ie(options, dcaps)
        if 'window' in browser_opts:
            w, h = self._decode_win_size(browser_opts['window'])
            browser.set_window_size(w,h)
        return browser

    def _launch_browser_ie(self, context, options, dcaps, **kwargs):
        return webdriver.Ie(ie_options=options,
                            desired_capabilities=dcaps,
                            **kwargs)



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
        userdata = {}

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

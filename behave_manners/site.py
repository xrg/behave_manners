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
import sys
import re
from behave.model_core import Status
import logging
import urllib3.exceptions
import datetime

log = logging.getLogger(__name__)

class SiteContext(object):

    def __init__(self, context, config=None):
        self._config = config or {}
        self.__orig_hooks = {}
        context.config.setup_logging()
        self._log.debug("site setup at %s" % getattr(context, '@layer', '?'))

        context.add_cleanup(self.__cleanup_site, context)

    def _setup_hook(self, hook_key, context):
        assert hook_key not in self.__orig_hooks, "Already installed: %s" % hook_key
        rhooks = context._runner.hooks
        if hook_key in rhooks:
            self.__orig_hooks[hook_key] = rhooks[hook_key]
        rhooks[hook_key] = getattr(self, '_hook_' + hook_key)

    def __cleanup_site(self, context):
        for hkey in self.__orig_hooks:
            context._runner.hooks[hkey] = self.__orig_hooks[hkey]
        self.__orig_hooks.clear()
        del context.site

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
                config = yaml.load(fp)
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
        except IOError, e:
            raise
        finally:
            os.chdir(old_cwd)

    def _hook_before_step(self, context, step):
        if 'before_step' in self.__orig_hooks:
            self.__orig_hooks['before_step'](context, step)

    def _hook_after_step(self, context, step):
        if 'after_step' in self.__orig_hooks:
            self.__orig_hooks['after_step'](context, step)

    def _hook_before_scenario(self, context, scenario):
        if 'before_scenario' in self.__orig_hooks:
            self.__orig_hooks['before_scenario'](context, scenario)

    def _hook_before_feature(self, context, feature):
        if 'before_feature' in self.__orig_hooks:
            self.__orig_hooks['before_feature'](context, feature)

    @property
    def base_url(self):
        return self._config['site']['base_url']


class WebContext(SiteContext):
    _log = logging.getLogger('behave.site.webcontext')

    def __init__(self, context, config=None):
        super(WebContext, self).__init__(context, config)
        # install hooks
        self._setup_hook('before_feature', context)
        self._setup_hook('before_scenario', context)
        self._setup_hook('after_step', context)
        self._config.setdefault('browser', {})

    def launch_browser(self, context):
        browser_opts = self._config['browser']
        caps = {}
        caps['record_network'] = 'true'
        caps['take_snapshot'] = 'true'

        desired_engine = browser_opts.get('engine', 'chrome').lower()

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
            if 'window' in browser_opts:
                w, h = self._decode_win_size(browser_opts['window'])
                options.add_argument('window-size=%dx%d' % (w, h))
            context.browser = webdriver.Chrome(chrome_options=options,
                                               desired_capabilities=dcaps,
                                               service_args=browser_opts\
                                                   .get('chromedriver_args', []))

        elif desired_engine == 'firefox':
            raise NotImplementedError('firefox')
        else:
            raise NotImplementedError('Unsupported engine: %s' % desired_engine)

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

    def _hook_before_feature(self, context, feature):
        super(WebContext, self)._hook_before_feature(context, feature)
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'feature' or \
                (browser_launch == 'scenario' and 'serial' in feature.tags):
            self.launch_browser(context)

    def _hook_before_scenario(self, context, scenario):
        super(WebContext, self)._hook_before_scenario(context, scenario)
        browser_launch = self._config['browser'].get('launch_on', False)
        if browser_launch == 'scenario' and 'serial' not in scenario.feature.tags:
            self.launch_browser(context)

    def _hook_before_step(self, context, step):
        super(WebContext, self)._hook_before_step(context, step)
        self._log.info("Entering step: %s", step.name)

    def _hook_after_step(self, context, step):
        if step.status == Status.failed:
            self._log.warning("Step: %s failed. Taking screenshot to ./screenshot1.png", step.name)
        try:
            self.process_logs(context)
        except urllib3.exceptions.RequestError, e:
            self._log.warning("Could not fetch logs, browser closed? %s", e)
        except Exception, e:
            self._log.error("Could not fetch step logs: %s", e)
        super(WebContext, self)._hook_after_step(context, step)

    def process_logs(self, context):
        for lt in context.browser.log_types:
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
            rec.msecs = (ct - long(ct)) * 1000
            log.handle(rec)


_wd_loglevels = {'INFO': logging.INFO, 'WARN': logging.WARNING,
                 'SEVERE': logging.ERROR, 'CRITICAL': logging.CRITICAL
                 }

def _cleanup_logentry(rec):
    if 'timestamp' in rec:
        rec['timestamp'] /= 1000.0

    rec['level'] = _wd_loglevels.get(rec.get('level', 'INFO'), logging.INFO)

    return rec

#eof

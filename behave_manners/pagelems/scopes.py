# -*-coding: UTF-8 -*-

from __future__ import division, absolute_import, print_function
import time
import logging
import six

from .base_parsers import DOMScope
from .dom_components import ComponentProxy
from .exceptions import PageNotReady, Timeout
from selenium.webdriver.remote.webdriver import WebElement
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
from selenium.webdriver.common.alert import Alert


logger = logging.getLogger('behave.scopes')


class WaitScope(DOMScope):
    _name = 'wait.base'

    wait_js_conditions = ["if (document.readyState != 'complete') { return 'document'; }",
                          "if (window.jQuery && window.jQuery.active) { return 'jQuery'; }"
                          ]

    timeouts = { 'short': 2.0,
                 'medium': 10.0,
                 'long': 60.0
                }

    def isready_js(self, driver):
        """One-off check that JS is settled

            :param driver: WebDriver instance
        """
        r = driver.execute_script('\n'.join(self.wait_js_conditions))
        if r:
            raise PageNotReady(r)

    def isready_all(self, driver):
        """Signal that all actions are settled, page is ready to contine

            Override this to add any custom logic besides `isready_js()` condition.
        """
        self.isready_js(driver)

    def wait_all(self, timeout='short', welem=None, webdriver=None):
        """Waits for all conditions of `isready_all()`
        """
        return self.wait(timeout=timeout, welem=welem, webdriver=webdriver,
                         ready_fn=self.isready_all)

    def wait(self, timeout='short', ready_fn=None, welem=None, webdriver=None):
        """Waits until 'ready_fn()` signals completion, times out otherwise
        """
        tstart = time.time()
        tend = tstart + self.resolve_timeout(timeout)
        lastmsg = 'all'
        pause = 0.05
        if webdriver is None:
            if welem is None:
                webdriver = self._root_component._remote
                if isinstance(webdriver, WebElement):
                    webdriver = webdriver.parent
            else:
                webdriver = welem.parent

        if ready_fn is None:
            ready_fn = self.isready_all

        while True:
            tnow = time.time()
            if tnow > tend:
                raise Timeout("Timed out after %.2fs waiting for %s" %
                              (tnow - tstart, lastmsg))

            try:
                ready_fn(webdriver)
                break
            except PageNotReady as e:
                lastmsg = e.args[0]
            except UnexpectedAlertPresentException as e:
                logger.debug("Alert during wait: %s", e.alert_text)
                ual = Alert(webdriver)
                if not self.handle_alert(ual):
                    raise e

            time.sleep(pause)
            if pause < 0.8:
                pause *= 2.0

    def resolve_timeout(self, timeout):
        factor = self.site_config.get('time_factor', 1.0)  # global multiplier for timeouts
        if isinstance(timeout, (int, float)):
            return timeout * factor
        else:
            num = self.site_config.get('timeouts', {}).get(timeout, None)
            if num is None:
                num = self.timeouts.get(timeout, None)
            if num is None:
                raise KeyError("Unknown timeout '%s'" % timeout)
            return num * factor

    class Page(object):
        def wait_all(self, timeout):
            # the component itself is not needed
            self._scope.wait_all(timeout, webdriver=self._remote)


class RootDOMScope(DOMScope):
    """Default scope to be used as parent of all scopes
    
        Such one would be the parent of a 'page' scope.
        
        Given that scopes can use the attributes of parent ones, this
        is where global attributes (such as site-wide config) can be
        set.
    """
    _name = '.root'
    component_class = ComponentProxy

    def __init__(self, templates=None, site_config=None):
        if templates is not None:
            assert isinstance(templates, dict)
        super(RootDOMScope, self).__init__(parent=None, templates=templates)
        self.site_config = site_config or {}

    def handle_alert(self, alert):
        return


class GenericPageScope(DOMScope):
    """Default page scope

        Page scope is the one attached to the remote DOM 'page', ie the <html>
        element. A good place to define page-wide properties, such as waiting
        methods.

        Wait for JS at least
    """
    _name = 'page'
    _inherit = 'wait.base'


class AngularJSApp(DOMScope):
    """Scope of an application using AngularJS (1.x)
    """
    _name = 'app.angularjs'
    _inherit = 'wait.base'

    wait_js_conditions = [
        "if (!angular) { return 'angularjs-startup'; }",
        "if (angular.element(document).injector().get('$http').pendingRequests.length > 0)"
        " { return 'angularjs';}"
        ]


class Angular5App(DOMScope):
    """Scope of an application using Angular 5+
    """
    _name = 'app.angular'
    _inherit = 'wait.base'

    wait_js_conditions = [
        "if(!window.getAllAngularTestabilities) { return 'angular-startup';}",
        "if(window.getAllAngularTestabilities().findIndex(function(x) { return !x.isStable(); }) >= 0)"
        " {return 'angular';}"
        ]


class Fresh(object):
    """Keep a component fresh, recovering any stale children under it
    """
    def __init__(self, comp, graceful=False):
        if isinstance(comp, ComponentProxy):
            self._scope = comp._scope
        elif isinstance(comp, DOMScope):
            self._scope = comp
        elif graceful:
            self._scope = None
        else:
            raise TypeError("fresh() needs a ComponentProxy or DOMScope")
        self._old_resolve = NotImplemented

    def __enter__(self):
        if self._scope is None:
            return
        self._old_resolve = self._scope.__dict__.get('recover_stale', NotImplemented)
        self._scope.recover_stale = True
        return self._scope

    def __exit__(self, *args):
        if self._scope is None:
            return
        if self._old_resolve is NotImplemented:
            del self._scope.__dict__['recover_stale']
        else:
            self._scope.__dict__['recover_stale'] = self._old_resolve
        self._old_resolve = NotImplemented


class CatchAlert(object):
    """Context manager for handling browser pop-up alerts

        Use like::

            with CatchAlert(context.cur_page, dismiss="Are you sure?"):
                context.cur_page.wait_all('short')


        :param page: the component to be acted upon
            Must be on the same (or any parent) scope that will be acted.
            Best works with current `Page` , that is top scope.
    """
    def __init__(self, page, dismiss=True, accept=None, fn=None):
        self._scope = page._scope
        self._dismiss = dismiss
        self._accept = accept
        self._handle_fn = fn
        self._orig_fn = None
        self.seen = []

    def __enter__(self):
        if self._orig_fn is not None:
            raise RuntimeError('Dirty context manager')
        # not using 'getattr()' because scope would ascend into parents
        self._orig_fn = self._scope.__dict__.get('handle_alert', None)
        self._scope.__dict__['handle_alert'] = self._handle_alert
        return self

    def _handle_alert(self, alert, *args):
        try:
            atext = alert.text
        except NoAlertPresentException:
            atext = None

        if self._handle_fn is not None and self._handle_fn(alert):
            self.seen.append(atext)
            return True

        if atext is None:
            pass
        elif self._accept is True \
                or (hasattr(self._accept, 'match') and self._accept.match(atext)) \
                or (isinstance(self._accept, six.string_types) and self._accept == atext):
            alert.accept()
            self.seen.append(atext)
            return True
        elif self._dismiss is True \
                or (hasattr(self._dismiss, 'match') and self._dismiss.match(alert.text)) \
                or (isinstance(self._dismiss, six.string_types) and self._dismiss == atext):
            alert.dismiss()
            self.seen.append(atext)
            return True

        if self._orig_fn is not None:
            return self._orig_fn(alert)

        try:
            parent_fn = self._scope._parent.handle_alert
        except AttributeError:
            return

        return parent_fn(alert)

    def __exit__(self, *args):
        if self._orig_fn is None:
            self._scope.__dict__.pop('handle_alert')
        else:
            self._scope.__dict__['handle_alert'] = self._orig_fn

# eof

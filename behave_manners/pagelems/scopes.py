# -*-coding: UTF-8 -*-

from __future__ import division, absolute_import, print_function
import time

from .base_parsers import DOMScope
from .dom_components import ComponentProxy
from .exceptions import PageNotReady, Timeout


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

# eof

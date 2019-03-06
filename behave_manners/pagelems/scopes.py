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

    def isready_js(self, driver):
        """One-off check that JS is settled

            :param driver: WebDriver instance
        """
        r = driver.execute_script('\n'.join(self.wait_js_conditions))
        if r:
            raise PageNotReady(r)

    def isready_all(self, driver):
        self.isready_js(driver)

    def wait_all(self, welem, timeout='short'):
        """Waits for all conditions of `isready_all()`
        """
        tstart = time.time()
        tend = tstart + self.resolve_timeout(timeout)
        lastmsg = 'all'
        pause = 0.05
        
        while True:
            tnow = time.time()
            if tnow > tend:
                raise Timeout("Timed out after %.2fs waiting for %s" %
                              (tnow - tstart, lastmsg))
            
            try:
                self.isready_all(welem.parent)
                break
            except PageNotReady as e:
                lastmsg = e.args[0]
            
            time.sleep(pause)
            if pause < 0.8:
                pause *= 2.0

    def resolve_timeout(self, timeout):
        if isinstance(timeout, (int, float)):
            return timeout
        elif timeout == 'short':
            return 5.0
        else:
            # parent?
            raise NotImplementedError # TODO


class RootDOMScope(DOMScope):
    _name = '.root'
    component_class = ComponentProxy

    def __init__(self, templates=None, site_config=None):
        if templates is not None:
            assert isinstance(templates, dict)
        super(RootDOMScope, self).__init__(parent=None, templates=templates)
        self.site_config = site_config or {}



class AngularJSApp(DOMScope):
    """Scope of an application using AngularJS (1.x)
    """
    _name = 'app.angularjs'
    _inherit = 'wait.base'

    wait_js_conditions = [
        "if (angular.element(document).injector().get('$http').pendingRequests.length > 0)"
        " { return 'angularjs';}"
        ]


class Angular5App(DOMScope):
    """Scope of an application using Angular 5+
    """
    _name = 'app.angular'
    _inherit = 'wait.base'

    wait_js_conditions = [
        "if(window.getAllAngularTestabilities().findIndex(x=>!x.isStable()) >= 0)"
        " {return 'angular';}"
        ]

# eof

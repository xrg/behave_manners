# -*- coding: UTF-8 -*-

from __future__ import absolute_import, print_function
import pytest
from behave_manners.pagelems.base_parsers import HTMLParseError, DOMScope
import behave_manners.pagelems.scopes


class DummyDriver(object):
    def __init__(self):
        self.called_scripts = []

    def execute_script(self, script):
        self.called_scripts.append(script)


class TestPEScopes(object):
    
    def test_root(self):
        driver = DummyDriver()
        root_scope = DOMScope['.root']()
        scope = DOMScope['wait.base'](root_scope)
        scope.isready_all(driver)
        assert len(driver.called_scripts) == 1
        assert driver.called_scripts[0] == \
            "if (document.readyState != 'complete') { return 'document'; }\n" \
            "if (window.jQuery && window.jQuery.active) { return 'jQuery'; }", \
            driver.called_scripts[0]

    def test_angular(self):
        driver = DummyDriver()
        root_scope = DOMScope['.root']()
        scope = DOMScope['app.angular'](root_scope)

        scope.isready_all(driver)

        assert len(driver.called_scripts) == 1
        assert driver.called_scripts[0] == \
            "if (document.readyState != 'complete') { return 'document'; }\n" \
            "if (window.jQuery && window.jQuery.active) { return 'jQuery'; }\n" \
            "if(window.getAllAngularTestabilities().findIndex(function(x) { return !x.isStable(); }) >= 0) {return 'angular';}", \
            driver.called_scripts[0]

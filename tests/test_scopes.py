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


class Scope1(DOMScope):
    _name = 'scope1'

    class Component(object):
        const1 = '1'
        def method1(self, foo):
            return 'called method1'

        @property
        def length(self):
            return 42

    class Page(object):
        def get_this(self):
            return 'page'


class Scope2(DOMScope):
    _name = 'scope2'
    _inherit = 'scope1'

    class Component(object):
        const2 = '2'

        def method1(self, foo):
            return 'called method2'


class TestScopesComponents(object):
    
    webelem_methods = {'click', 'clear', 'is_displayed', 'is_enabled', 'is_selected',
                       'get_attribute', 'get_property', 'send_keys', 'submit'}

    def test_baseclass(self):
        root_scope = DOMScope['.root']()

        assert set(root_scope._comp_descriptors.keys()) == self.webelem_methods

    def test_scope1(self):
        root_scope = DOMScope['.root']()
        scope = DOMScope['scope1'](root_scope)

        assert set(scope._comp_descriptors.keys()) == self.webelem_methods | \
                {'const1', 'method1', 'length'}

    def test_scope2(self):
        root_scope = DOMScope['.root']()
        scope = DOMScope['scope2'](root_scope)

        assert set(scope._comp_descriptors.keys()) == self.webelem_methods | \
                {'const1', 'const2', 'method1', 'length'}

    def test_scope3(self):
        root_scope = DOMScope['.root']()
        mscope = DOMScope['scope1'](root_scope)
        scope = DOMScope['*'](mscope)

        assert set(scope._comp_descriptors.keys()) == self.webelem_methods

#eof

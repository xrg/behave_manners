# -*- coding: UTF-8 -*-
""" Utilities for browser screenshots, connected to events
    
"""
from __future__ import absolute_import
import os
import os.path
import logging
import time
from contextlib import contextmanager
from behave.model_core import Status, BasicStatement
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains


class Camera(object):
    """A camera takes screenshots (or element shots) of the browser view
    
        An instance will be attached to the behave context. Configured by
        site configuration. Then triggered each time a step explicitly
        wants a screenshot, or the hooks implicitly catching some failure.
    """
    _log = logging.getLogger('behave.site')
    highlight_js = '''
        var highlight = document.createElement('div');
        highlight.setAttribute('style',
            'border: 2px solid red; ' +
            'border-radius: 1px; ' +
            'background-color: rgba(255, 64, 64, 0.3); ' +
            'z-index: 9999; ' +
            'position: absolute; ' +
            'left: {x}px; top: {y}px; ' +
            'width: {width}px; height: {height}px;');
        document.body.appendChild(highlight);
        return highlight;
        '''

    def __init__(self, base_dir='.'):
        self.count = 0
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.isdir(self.base_dir):
            os.makedirs(self.base_dir)

    _name_pattern = 'shot{mode}-{pid}-{num}-{timestamp}.png'

    def _make_name(self, mode=''):
        """Generate name to use for the screenshot file
        
            Uses `_name_pattern` and formats it with:
                mode: the `mode` argument
                pid: current process id
                num: incremental counter of shots taken so far (by this process)
                timestamp: current timestamp, seconds since epoch (integer)
        """
        if mode:
            mode = '-' + mode
        self.count += 1
        return self._name_pattern.format(mode=mode, pid=os.getpid(),
                                         num=self.count, timestamp=int(time.time()))

    def take_shot(self, context, mode=''):
        """Capture the full browser viewport.
        """
        fname = self._make_name(mode)
        self._log.warning("Taking screenshot to \"%s\"", fname)
        context.browser.get_screenshot_as_file(os.path.join(self.base_dir, fname))

    def snap_success(self, context, *args):
        if args and getattr(args[0], 'status', False) == Status.passed:
            self.take_shot(context, 'success')

    def _get_elem_rect(self, webelem):
        webdriver = webelem.parent
        if True:
            try:
                rect = webelem.rect.copy()
            except WebDriverException as e:
                rect = webelem.location.copy()
                rect.update(webelem.size)

        return rect

    @contextmanager
    def highlight_element(self, context, component=None, webelem=None):
        """Perform some action with an element visually highlighted
        
            This should place a square rectangle on the DOM, around the
            element in question. The rectangle is appended into the root
            of the DOM to avoid any inheritance effects of the interesting
            element.
            After the action is performed, the highlight element is removed.

        """
        if webelem is None and component is not None:
            webelem = component._remote

        if webelem is None:
            yield
            return

        highlight = None
        webdriver = None

        try:
            webdriver = webelem.parent   # safer than using 'context.webdriver'
            ActionChains(webdriver).move_to_element(webelem).perform()
            rect = self._get_elem_rect(webelem)

            # grow the rectangle to least 30x30 or +2px than original
            dw = 30 - rect['width']
            dh = 30 - rect['height']
            if dw < 2:
                dw = 2
            if dh < 2:
                dh = 2
            rect['x'] -= dw // 2
            rect['y'] -= dh // 2
            rect['width'] += dw
            rect['height'] += dh

            highlight = webdriver.execute_script(self.highlight_js.format(**rect))
        except AttributeError as e:
            pass
        except Exception as e:
            self._log.info("Could not highlight: %s", e)

        yield

        if highlight is not None:
            try:
                webdriver.execute_script('arguments[0].remove()', highlight)
            except Exception as e:
                self._log.info("Could not remove highlight: %s", e)

    def snap_failure(self, context, *args):
        from .pagelems.exceptions import ElementNotFound, ComponentException
        failed_comp = failed_elem =  None
        try:
            if args and isinstance(args[0], BasicStatement):
                exc = getattr(args[0], 'exception', None)
                if isinstance(exc, ElementNotFound):
                    failed_elem = exc.parent
                elif isinstance(exc, (WebDriverException, ComponentException)):
                    failed_comp = exc.component
        except AttributeError:
            pass

        with self.highlight_element(context, failed_comp, failed_elem):
            self.take_shot(context, 'failure')

    def capture_missing_elem(self, context, parent, missing_path):
        """Screenshot of browser when some element is missing

            :param context: behave Context containing site and browser
            :param parent: selenium.WebElement under which other was not found
            :param missing_path: string of XPath missing
        """
        with self.highlight_element(context, webelem=parent):
            self.take_shot(context, 'missing-elem')


# eof

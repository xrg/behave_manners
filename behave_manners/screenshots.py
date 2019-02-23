# -*- coding: UTF-8 -*-
""" Utilities for browser screenshots, connected to events
    
"""
import os
import os.path
import logging
import time
from contextlib import contextmanager
from behave.model_core import Status, BasicStatement
from selenium.common.exceptions import WebDriverException


class Camera(object):
    """A camera takes screenshots (or element shots) of the browser view
    """
    _log = logging.getLogger('behave.site')
    highlight_js = '''
        var highlight = document.createElement('div');
        highlight.setAttribute('style',
            'border: 2px solid red; ' +
            'border-radius: 1px; ' +
            'background-color: rgba(255, 64, 64, 0.4); ' +
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

    def _make_name(self, mode=''):
        if mode:
            mode = '-' + mode
        self.count += 1
        return 'shot%s-%d-%d-%s.png' % (mode, os.getpid(), self.count,
                                        int(time.time()))

    def take_shot(self, context, mode=''):
        fname = self._make_name(mode)
        self._log.warning("Taking screenshot to \"%s\"", fname)
        context.browser.get_screenshot_as_file(os.path.join(self.base_dir, fname))

    def snap_success(self, context, *args):
        if args and getattr(args[0], 'status', False) == Status.passed:
            self.take_shot(context, 'success')

    @contextmanager
    def highlight_element(self, context, component):
        """Perform some action with an element visually highlighted
        
            This should place a square rectangle on the DOM, around the
            element in question. The rectangle is appended into the root
            of the DOM to avoid any inheritance effects of the interesting
            element.
            After the action is performed, the highlight element is removed.
            
        """
        if component is None:
            yield
            return

        highlight = None
        webdriver = None

        try:
            webelem = component._remote
            webdriver = webelem.parent   # safer than using 'context.webdriver'
            # print "display p:", webelem.is_displayed(), webelem.rect
            # print "display c:", webelem.value_of_css_property('display')
            rect = webelem.rect.copy()
            
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
        failed_comp = None
        try:
            if args and isinstance(args[0], BasicStatement) \
                    and isinstance(getattr(args[0], 'exception', None),
                                WebDriverException):
                failed_comp = args[0].exception.component
        except AttributeError:
            pass
        
        with self.highlight_element(context, failed_comp):
            self.take_shot(context, 'failure')

    def capture_missing_elem(self, context, parent, missing_path):
        """Screenshot of browser when some element is missing
            
            :param context: behave Context containing site and browser
            :param parent: selenium.WebElement under which other was not found
            :param missing_path: string of XPath missing
        """
        # TODO highlight
        self.take_shot(context, 'missing-elem')


# eof
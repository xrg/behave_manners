# -*- coding: utf-8 -*
from __future__ import print_function
import behave_manners.steplib.run_bg_devel

from behave import given, when, then
import time


@given(u'I am at the "{page}"')
def step_impl1(context, page):
    context.site.navigate_by_title(context, page)
    context.cur_element = context.cur_page


@when(u'I click {elem}')
def step_impl4(context, elem):
    context.cur_element[elem].click()


@then(u'I am directed to the "{page}"')
def step_impl5(context, page):
    cur_page = context.site.get_cur_title(context)
    assert cur_page == page, "Currently at %s (%s)" % (cur_page, context.browser.current_url)
    time.sleep(5)
    context.browser.get_screenshot_as_file('%s.png' % page)


# eof

# -*- coding: utf-8 -*
from __future__ import print_function
import behave_manners.steplib.run_bg_devel

from behave import given, when, then


@given(u'I am at the "{page}"')
def step_impl1(context, page):
    context.site.navigate_by_title(context, page)


@when(u'I use the {component}')
def step_impl2(context, component):
    context.cur_element = context.cur_page[component]


@when(u'I enter "{value}" in the query box')
def step_impl3(context, value):
    context.cur_element.q = value
    assert context.cur_element.q == value, context.cur_element.q


@when(u'I click {elem}')
def step_impl4(context, elem):
    context.cur_element[elem].click()


@then(u'I am directed to the "{page}"')
def step_impl5(context, page):
    cur_page = context.site.get_cur_title(context)
    assert cur_page == page, "Currently at %s (%s)" % (cur_page, context.browser.current_url)


# eof

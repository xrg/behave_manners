# -*- coding: utf-8 -*
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.step_utils import implies
from behave_manners.pagelems.scopes import DOMScope
import time


@given(u'I am at the "{page}"')
def step_impl1(context, page):
    context.site.navigate_by_title(context, page)
    context.cur_element = context.cur_page


@when(u'I click {elem}')
def step_impl4(context, elem):
    context.cur_element[elem].click()


@step('I wait for page to load')
def step_wait_page(context):
    context.cur_page.wait_all('medium')


@then(u'I am directed to the "{page}"')
@implies(u'When I wait for page to load')
def step_impl5(context, page):
    title = context.site.update_cur_page(context)
    assert title == page, "Currently at %s (%s)" % (title, context.browser.current_url)
    context.site_camera.take_shot(context)
    title_text = context.cur_page['main']['content']['title'].text
    assert title_text == 'Getting started', title_text


class soScope(DOMScope):
    _name = 'sofo'


# eof

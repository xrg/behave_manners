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


@given(u'I use the {example} example')
def use_example(context, example):
    context.cur_element = context.cur_page['examples'][example]['body']


@step(u'I use the "{comp}" in there')
def use_sub_component(context, comp):
    context.cur_element = context.cur_element[comp]


@when(u'I click option value "{value}"')
def step_impl(context, value):
    context.cur_element.value = value


@when(u'I click option labelled "{label}"')
def click_option_lbl(context, label):
    context.cur_element.set_by_label(label)


@then(u'the selected value is "{value}"')
def check_option_value(context, value):
    cur_value = context.cur_element.value
    assert cur_value == value, '%r != %r' % (cur_value, value)


@then(u'the selection is blank')
def step_blank_selection(context):
    cur_value = context.cur_element.value
    assert cur_value == None, '%r != None' % (cur_value, )


@when(u'I enter value "{value}"')
def step_enter_value(context, value):
    context.cur_element.value = value


@given(u'the material version is "{version}"')
def set_mat_version(context, version):
    context.cur_page['version'].set_version(version)  # does DRY apply to names??


# eof

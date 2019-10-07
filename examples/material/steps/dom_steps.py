# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
from behave_manners.step_utils import implies
from behave_manners.pagelems.scopes import DOMScope, Fresh
from behave_manners.pagelems.exceptions import CAssertionError
import time


@given('I am at the "{page}"')
def step_impl1(context, page):
    context.site.navigate_by_title(context, page)
    context.cur_element = context.cur_page



@when(u'I click "{something}"')
def click_on_something(context, something):
    context.cur_element[something].click()


@step('I wait for page to load')
def step_wait_page(context):
    context.cur_page.wait_all('medium')


@then('I am directed to the "{page}"')
@implies('When I wait for page to load')
def step_impl5(context, page):
    title = context.site.update_cur_page(context)
    assert title == page, "Currently at %s (%s)" % (title, context.browser.current_url)
    context.site_camera.take_shot(context)
    title_text = context.cur_page['heading'].title
    assert title_text == 'Getting started', title_text


@given('I use the {example} example')
def use_example(context, example):
    context.cur_element = context.cur_page['examples'][example]['body']


@step('I use the "{comp}" in there')
def use_sub_component(context, comp):
    context.cur_element = context.cur_element[comp]


@when('I click option value "{value}"')
def step_impl(context, value):
    context.cur_element.value = value


@when('I click option labelled "{label}"')
def click_option_lbl(context, label):
    context.cur_element.set_by_label(label)


@then('the selected value is "{value}"')
def check_option_value(context, value):
    cur_value = context.cur_element.value
    assert cur_value == value, '%r != %r' % (cur_value, value)


@then('the selection is blank')
def step_blank_selection(context):
    cur_value = context.cur_element.value
    assert cur_value == None, '%r != None' % (cur_value, )


@then('the field has no value')
def step_blank_field(context):
    cur_value = context.cur_element.value
    assert not cur_value , 'Value: %r' % (cur_value, )


@when('I enter value "{value}"')
def step_enter_value(context, value):
    context.cur_element.value = value

@given('I have loaded a long text file')
def read_long_text(context):
    with open("/usr/share/common-licenses/Artistic", 'rt') as fp:
        context.long_text = fp.read().replace('\t', '    ')


@when('I paste the long text in')
def type_long_text(context):
    context.cur_element['input'].value = context.long_text


@when('I type the long text in')
def type_long_text(context):
    inp = context.cur_element['input']._remote
    inp.click()
    inp.clear()
    inp.send_keys(context.long_text)


@then('I can read the long text back')
def validate_long_text(context):
    with Fresh(context.cur_element):
        cur_value = context.cur_element['input'].value
        if cur_value != context.long_text:
            raise CAssertionError("Text differs", component=context.cur_element['input'])


@given('the material version is "{version}"')
def set_mat_version(context, version):
    context.cur_page['version'].set_version(version)  # does DRY apply to names??


# eof

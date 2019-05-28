# -*- coding: UTF-8 -*-
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.pagelems import DOMScope
from behave_manners.action_chains import ActionChains
from behave_manners.pagelems.exceptions import CAssertionError
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException


@when(u'I click to have the dropdown visible')
def click_dropdown1(context):
    if not context.cur_element['input'].owns:
        context.cur_element.click()
        context.cur_element._scope.wait_all('short', welem=context.cur_element._remote)

    print("Owns: %s" % context.cur_element['input'].owns)

    context.cur_overlays = context.cur_element['overlays']


@when(u'I click again to hide the dropdown')
def click_hide_dropdown(context):
    input_elem = context.cur_element['input']
    if input_elem.owns:
        input_elem.send_keys(Keys.ESCAPE)
    assert not input_elem.owns


@when(u'I click again to show the dropdown')
def click_dropdown2(context):
    context.cur_element['input'].send_keys('o')
    context.cur_element._scope.wait_all('short', welem=context.cur_element._remote)
    assert context.cur_element['input'].owns, "Did not present overlay"


@then(u'the previous dropdown component resolves')
def check_resolve_dropdown1(context):
    print("Cur dropdown %s" % context.cur_element['input'].owns)
    print("Cur overlays %s" % context.cur_overlays.is_displayed())


@when(u'I enter "{value}" in the "{field}" field')
def enter_some_value(context, field, value):
    context.cur_element[field].value = value


@when(u'I click "{button}" to open the dialog')
def click_and_open_dialog(context, button):
    context.cur_element[button].click()


@when(u'I click "{button}" to close the dialog')
def click_close_dialog(context, button):
    context.cur_dialog[button].click()


@then(u'the dialog modal is displayed')
def check_modal_dialog(context):
    context.cur_dialog = context.cur_element['dialog']


@then(u'the dialog question is "{question}"')
def check_dialog_question(context, question):
    if context.cur_dialog.question != question:
        raise CAssertionError("Question is different",
                              component=context.cur_dialog)


@then(u'the dialog component becomes stale')
def check_dialog_is_stale(context):
    try:
        list(context.cur_dialog.keys())
        raise CAssertionError("Can still read it", component=context.cur_dialog)
    except StaleElementReferenceException as e:
        pass



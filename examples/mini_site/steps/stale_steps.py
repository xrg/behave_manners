# -*- coding: UTF-8 -*-
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.pagelems import DOMScope
from behave_manners.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


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
    raise AssertionError


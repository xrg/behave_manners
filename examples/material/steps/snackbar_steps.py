# -*- coding: utf-8 -*
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.step_utils import implies
from behave_manners.pagelems.scopes import DOMScope
import time


@given(u'I set duration to {num}')
def step_set_duration(context, num):
    context.cur_element['duration'].value = num


@given(u'I click the \'{button}\' button')
def click_btn(context, button):
    context.cur_element[button].click()
    context.cur_page.wait_all('short')


@then(u'I see a snack-bar-notification')
def read_snack_bar(context):
    snack = context.cur_page['snack-bar']
    context.last_snack = snack['message'].text


@then(u'last notification reads \'{text}\'')
def check_last_snack(context, text):
    assert context.last_snack == text



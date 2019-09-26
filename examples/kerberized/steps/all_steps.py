# -*- coding: utf-8 -*
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.step_utils import implies
from behave_manners.pagelems.scopes import DOMScope
from behave_manners.site import RemoteNetworkError
from behave_manners.pagelems.exceptions import ElementNotFound
import time


@given(u'I am at the "{page}"')
def step_impl1(context, page):
    context.site.navigate_by_title(context, page)
    context.cur_element = context.cur_page


@then(u'the page validates according to template')
def step_validate(context):
    context.site.validate_cur_page(context)

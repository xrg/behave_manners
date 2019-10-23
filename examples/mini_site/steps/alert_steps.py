# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
from behave_manners.pagelems.exceptions import CAssertionError
from behave_manners.pagelems.scopes import CatchAlert


@when('I press the alert "{name}" button')
def click_alert_btn(context, name):
    context.cur_element[name].click()


@then('an alert is raised')
def check_last_alert(context):
    with CatchAlert(context.cur_page) as alerts:
        context.cur_page.wait_all('medium')

        assert ('Alert test!' in alerts.seen), alerts.seen


#eof

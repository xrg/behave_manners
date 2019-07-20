# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
from behave_manners.pagelems.actions import click
import logging


@when('I hit the button')
def hit_button(context):
    orig_consume = context.site.events.consume_log
    context.messages = []
    def _consume_message(rec):
        try:
            if rec.name == 'browser.console-api' and rec.levelno == logging.INFO:
                context.messages.append(rec.message)
            else:
                print ("name:", rec.name, rec.levelno)
        except AttributeError:
            pass
        orig_consume(rec)

    context.cur_element['hitme-button'].click()
    context.site.process_logs(context, consumer=_consume_message)


@then('the button hurts')
def check_logs(context):

    assert 'ouch!' in context.messages, context.messages

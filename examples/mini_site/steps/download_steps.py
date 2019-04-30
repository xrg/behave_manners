# -*- coding: utf-8 -*
from __future__ import print_function
from behave import given, when, then, step
from behave_manners.step_utils import implies
from behave_manners.pagelems.scopes import DOMScope
import time


@when(u'I click the link to download')
def press_download(context):
    context.cur_page['download-here'].click()


@when(u'I wait for {num:d}sec')
def explicit_wait(context, num):
    time.sleep(num)


@then(u'there is a new data file')
def check_downloaded_file(context):
    for fname, fullname in context.downloads.look_for('*.data'):
        print("Got new file: %s" % fname)
        break
    else:
        raise AssertionError("No file found")

@then(u'there is no new data file')
def check_no_file(context):
    for fname, fullname in context.downloads.look_for('*.data'):
        raise AssertionError("new file: %s" % fname)


@then(u'I get a new data file')
def check_downloaded_file2(context):
    fname, fullname = context.downloads.wait_for('*.data', 23.0)
    print("Got new file: %s" % fname)


# eof

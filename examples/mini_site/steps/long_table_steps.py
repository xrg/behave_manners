# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
from behave_manners.pagelems.exceptions import CAssertionError

@given(u'I see a long table with {num:d} rows')
def goto_long(context, num):
    context.site.navigate_by_title(context, 'Long table Id Column',
                                   params=dict(limit=num))
    context.num_rows = num

@then(u'I can count the lines of that table')
def count_table(context):
    table = context.cur_page['content']['table']
    len_rows = len(table['rows'])
    if len_rows != context.num_rows:
        raise CAssertionError("Table has %d rows" % len_rows, component=table)




# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
from behave_manners.pagelems.exceptions import CAssertionError


@when(u'I look for the sections')
def lookup_sections(context):
    context.cur_group = context.cur_page['sections']


@then(u'I find {num:d} entries')
def check_cur_length(context, num):
    assert len(context.cur_group) == num, len(context.cur_group)


@then(u'the {attr:w} of {name:w} is "{value}"')
def check_one_attribute(context, attr, name, value):

    context.cur_element = context.cur_group[name]
    cval = getattr(context.cur_element, attr)
    if cval != value:
        raise CAssertionError("Bad %s.%s = %r" % (name, attr, cval),
                              component=context.cur_element)


@when(u'I look for form fields')
def lookup_fields(context):
    context.cur_group = context.cur_page['form']['fields']

@when(u'I look for inactive fields')
def lookup_fields(context):
    context.cur_group = context.cur_page['form']['inactive-fields']


@then(u'these entries are called')
def names_of_items(context):
    expected = [ r['Name'] for r in context.table]
    found = list(context.cur_group.items())

    while expected and found:
        ei = expected.pop(0)
        fi = found.pop(0)
        if fi[0] != ei:
            raise CAssertionError("Bad component \"%s\" instead of \"%s\"" %(fi[0], ei),
                                  component=fi[1])
    if expected:
        raise CAssertionError("Expected more components: %s" % expected,
                              component=fi[1])
    if found:
        raise CAssertionError("Found more components: %s" % [f[0] for f in found],
                              component=found[0][1])

# eof

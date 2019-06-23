# -*- coding: utf-8 -*
from __future__ import print_function, unicode_literals
from behave import given, when, then, step
import tempfile
import logging
import os
from behave_manners.pagelems.exceptions import CAssertionError


logger = logging.getLogger('upload-steps')


@when('I upload some random file')
def upload_tmp_file(context):
    fd, path = tempfile.mkstemp(dir=context.site.output_dir)
    try:
        fp = os.fdopen(fd, 'w')
        fp.write('foo bar')
        fp.close()
    except Exception:
        logger.exception("Could not write tmp file")
        raise
    context.add_cleanup(lambda *c: os.unlink(path))

    logger.info("Uploading file from: %s", path)
    context.cur_element.file = path   # this is where file is passed to browser!
    logger.info("Files now have: %r", context.cur_element.file)
    context.cur_element['submit'].click()

    context.cur_page.wait_all('medium')
    context.cur_element = None  # upload area should be gone
    context.site.update_cur_page(context)


@then('I can see "{sub}" under the "{upload_area}"')
def check_upload_ok(context, upload_area, sub):
    context.cur_element = context.cur_page[upload_area]
    assert context.cur_element[sub]


@then('the payload reads "{expected}"')
def check_payload(context, expected):
    if context.cur_element['payload'].text != expected:
        raise CAssertionError("Payload does not match!",
                              component=context.cur_element['payload'])


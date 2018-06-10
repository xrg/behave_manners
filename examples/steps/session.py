import uuid
import random
import time

@given(u'I open the mini application')
def go_to_login_form(context):
    context.browser.get('http://192.168.125.1:5000/')

@then('the title should be "{text}"')
def verify_title(context, text):
    title = context.browser.title
    assert title == text, title

@when('I enter a random string')
def enter_random_str(context):
    context.random_str = uuid.uuid4().get_hex()
    input_elem = context.browser.find_element_by_xpath('//form/input[@name="number"]')
    input_elem.clear()
    input_elem.send_keys(context.random_str)

@when('I click submit')
def click_submit(context):
    context.browser.find_element_by_xpath('//form/input[@type="submit"]').click()

@then('I should read the random string')
def see_random_number(context):
    context.browser.get('http://192.168.125.1:5000/')
    context.browser.implicitly_wait(5)
    # time.sleep(3.0* random.random())
    elem = context.browser.find_element_by_xpath('//span[@id=\'number\']')
    web_number = elem.text
    assert web_number == context.random_str, web_number



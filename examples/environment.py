import time
from selenium import webdriver
import os

def before_all(context):
    options = webdriver.ChromeOptions()
    # options.binary_location = '/usr/lib64/chromium-browser/headless_shell'
    options.add_argument('headless')
    options.add_argument('window-size=1200x800')
    caps = {}
    caps['record_network'] = 'true'
    caps['take_snapshot'] = 'true'
    context.browser = webdriver.Chrome(chrome_options=options,
                                       desired_capabilities=caps)

def after_all(context):
    context.browser.quit()

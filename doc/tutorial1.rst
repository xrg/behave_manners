.. _tutorial1:

Tutorial
=========

A short tutorial on how to get started (from scratch) using `behave_manners`.

.. note:: The need to keep this tutorial simple and small contradicts with
    the core purpose of `manners`. Manners are designed for the complex case,
    for large sites, while the examples below are over-simplified. Please,
    keep that in mind. Gains from `manners` come when the site is much harder
    than this example.


1. Project setup
-----------------

A minimal project for behave_manners should have the following files:

  environment.py
    Standard `behave` script for setting up configuration defaults

  config.yaml
    Recommended configuration file with project defaults, base settings.

  requirements.txt
    Recommended to have a file listing all python dependencies used for
    this project. Should contain a line for `behave-manners`

  site/index.html
    Required, mapping of URLs to template files & titles

  site/first-page.html
    At least one template file (to cover one or multiple site URLs)

  first-page.feature
    At least one feature file with scenarios

  steps/first_page_steps.py
    At least one python script with implementations of the feature steps


Having a `setup.py` is not really needed: think of the tests project as a
collection of data files; they should be runable from a simple checkout.

Behave-manners should only need minimal content in the above files; tries
to fill-in reasonable defaults for most un-mentioned values.


Examples of project files
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. highlight:: python

*environment.py* ::

    from behave_manners import site_setup


    def before_all(context):
        site_setup(context, config='config.yaml')


This is the only line needed for behave-manners to set-up everything: the browser,
load the page templates (lazily) and set the base-url for all your site.


.. highlight:: yaml

*config.yaml* ::

    site:
        base_url: https://material.angular.io

    browser:
        engine: chrome
        launch_on: feature

        screenshots:
            dir: screenshots

    page_objects:
        index: site/index.html


As names suggest, contains settings for the site, browser tuning and points
to the page templates that should be used.


.. highlight:: none

*requirements.txt* ::

    behave-manners


.. highlight:: html

*site/index.html* ::

    <html>
    <head>
        <link rel="next" href="first-page.html" title="Home Page" url="/">
        <link rel="next" href="quickstart.html" title="Quick Start" url="/guide/getting-started">
    </head>
    </html>


`index.html` is a special file. Can only have a `<head>` containing `<link>` elements,
to establish the mapping of URLs to the page templates and optionally titles.
It is only a table; could have been in any other format, yet done in html for symmetry
with the rest of page templates.


*site/first-page.html* ::

    <html>
    <body>
    <material-docs-app ng-version="[ng-version]">
        <div pe-deep class="docs-header-start">
            <a this="get-started-button">
                <span>Get started</span>
            </a>
            <pe-not>
                <div class="bad-section">Foo
                </div>
            </pe-not>
        </div>
    </material-docs-app>
    </body>
    </html>


Each page template file should match the remote DOM of the site being tested. See
documentation for further explanation of the page template format.


.. highlight:: gherkin

*first-page.feature* ::

    Feature: Check home page

    Scenario: Use the search form

      Given I am at the "Home Page"
       When I click get-started-button
       Then I am directed to "Quick Start"


Feature files describe the desired tests in an abstract, high-level way.


.. highlight:: python

*steps/first_page_steps.py* ::

    from behave import given, when, then, step


    @given(u'I am at the "{page}"')
    def step_impl1(context, page):
        context.site.navigate_by_title(context, page)
        context.cur_element = context.cur_page

    @when(u'I click {button}')
    def click_a_button(self, button):
        context.cur_element[button].click()

    @then(u'I am directed to "{page}"')
    def check_this_page(self, page):
        title = context.site.update_cur_page(context)
        assert title == page, "Currently at %s (%s)" % (title, context.browser.current_url)


Python implementations of steps is the 'glue' between features and the abstract
Component tree that `behave-manners` can provide. Here, page elements (and nested
sub-elements of) can be referenced like simple Python objects, also interacted with.


2. Python setup
----------------

Assuming that python is installed and operational, it is highly recommended
that your project uses a dedicated virtual environment.

Within that virtualenv, only need to install ``behave-manners`` . Or, even better,
call:

    ``pip install -r requirements.txt``

to cover any other dependencies your project may desire.



Chromedriver
~~~~~~~~~~~~~

The browser driver (chromedriver, here) needs to be installed separately, as
a binary, into your system.

Calling ``which chromedriver`` within the virtualenv should verify if it is 
properly placed (and executable).



3. Verifying page templates
----------------------------

After the `index.html` and page templates are written, they can be tested
independently of feature files (and step definitions).
For this, `behave-manners` provides with a pair of utilities:

    - behave-run-browser
    - behave-validate-remote

Which are complementary: 'run-browser' will launch a browser with the settings
as specified in 'config.yaml' . Then 'validate-remote' can be called repeatedly
against that browser, to scan the page on that browser and print the Components
that are discoverable in it.

.. highlight:: none

Example from the above settings, in 'https://material.angular.io' ::

    $ behave-run-browser .
    INFO:main:Entering main phase, waiting for browser to close
    INFO:main:Browser changed to: Angular Material
    ...

    $ behave-validate-remote 
    INFO:site_collection:Read index from 'site/index.html'
    INFO:site_collection:Read page from 'site/first-page.html'
    INFO:main:Got page First Page ()

        <Page "https://material.angular.io/">
          get-started-button <a class="docs-button mat-raised-button">

    INFO:main:Validation finished, no errors


The standard output of the second is the Page component, and within it, that
'get-started' button. Real-life examples should be much more deep than that.


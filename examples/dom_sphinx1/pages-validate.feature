Feature: All known pages in the site match the schema

Scenario: Index page validates

Given I am at the "Index Page"
Then the page validates according to template


  Scenario Outline: Other pages validates
    When Browser URL is "<url>"
    Then the page validates according to template


  Examples: Selenium URLs
    | url                                                        |
    | /common/selenium.common.exceptions.html                    |
    | /webdriver/selenium.webdriver.common.keys.html             |
    | /webdriver_remote/selenium.webdriver.remote.command.html   |
    | /webdriver_remote/selenium.webdriver.remote.webdriver.html |


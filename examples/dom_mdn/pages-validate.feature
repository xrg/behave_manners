Feature: All known pages in the site match the schema

Scenario: Index page validates

Given I am at the "Index Page"
Then the page validates according to template


  Scenario Outline: Other pages validates
    When Browser URL is "<url>"
    Then the page validates according to template


  Examples: Mozilla Dev Network URLs
    | url                                         |
    | /HTML/Element/html                          |
    | /HTML/Element                               |
    | /HTML/Element/link                          |
    | /JavaScript/About_JavaScript                |
    | /Web_Components/Using_templates_and_slots   |


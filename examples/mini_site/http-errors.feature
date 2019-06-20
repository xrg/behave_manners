Feature: Check behavior of error pages

    Scenario: Handle normal page

        When I try to load "Index Page"
        Then the page loads

    Scenario: Handle missing page

        When I try to load "Missing page"
        Then I get a 404 error

    Scenario: Handle forbidden page

        When I try to load "Private page"
        Then I get a 403 error

    Scenario: Handle broken page

        When I try to load "Broken page"
        Then I get a 500 error

    Scenario: Page with bad link
        When I try to load "Bad-link page"
        Then the page loads

    Scenario: Page with bad JS
        When I try to load "Bad-js page"
        Then the page loads

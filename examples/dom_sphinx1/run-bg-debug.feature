Feature: Run browser until elements can be developed

Scenario: Run browser as server
    When I launch a browser in foreground
    And I save the session to 'dbg-browser.session'
    Then I wait for the browser to close itself


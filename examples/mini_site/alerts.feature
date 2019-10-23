Feature: test non-html alerts and notifications

  Macro: I see the Alerts content
    Given I am at the "Alerts"
    And I wait for page to load
    And I use the "content" in there

  @wip
  Scenario: plain browser alert
    Given I see the Alerts content
    When I press the alert "OK alert" button
    Then an alert is raised



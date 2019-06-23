Feature: test file uploads

  Scenario: send a random file up
    Given I am at the "Upload page"
    And I use the "upload-area" in there
    And I use the "form" in there
    When I upload some random file
    Then I can see "ok" under the "upload-area"
    And the payload reads "foo bar"

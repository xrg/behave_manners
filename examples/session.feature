Feature: Test a session

Scenario: Test Session
  Given I open the mini application
  Then the title should be "Mini-application"
  When I enter a random string
  When I click submit
  Then I should read the random string

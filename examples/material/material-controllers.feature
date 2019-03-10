Feature: Check operation of Angular-Material controllers

    Scenario: Radio buttons, initial state

        Given I am at the "Radio button overview"
          and I use the radio-overview example
          and I use the "radio-group" in there
        Then the selection is blank

    Scenario: Radio buttons

        Given I am at the "Radio button overview"
          and I use the radio-overview example
          and I use the "radio-group" in there
        When I click option labelled "Option 1"
        Then the selected value is "1"
        When I click option value "2"
        Then the selected value is "2"



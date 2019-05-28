Feature: Cause a stale component and recover it

    Scenario: Dialog becomes stale after closing
        Given I am at the "Dialog overview"
          and I use the dialog-overview example
         When I enter "My name" in the "name-input" field
          and I click "Pick one" to open the dialog
         Then the dialog modal is displayed
          and the dialog question is "What's your favorite animal?"
         When I click "No Thanks" to close the dialog
         Then the dialog component becomes stale


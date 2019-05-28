Feature: Cause a stale component and recover it

    Scenario: Stale Autocomplete dropdown
        Given I am at the "Autocomplete overview"
          and I use the autocomplete-filter example
          and I use the "autocomplete" in there
         When I click to have the dropdown visible
          And I click again to hide the dropdown
          And I click again to show the dropdown
         Then the previous dropdown component resolves

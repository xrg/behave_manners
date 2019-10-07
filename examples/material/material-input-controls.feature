Feature: Check Angular-Material input controls

    Scenario: Type into input box

        Given I am at the "Input Examples"
          and I use the example_0 example
          and I use the "Leave a comment" in there
        Then the field has no value
        When I enter value "123 abc"
        Then the selected value is "123 abc"
    
    

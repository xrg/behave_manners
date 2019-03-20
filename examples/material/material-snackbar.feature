Feature: Check operation of Snack bar

    Scenario: Fire message, read it

        Given I am at the "Snack Bar example"
          and I use the example_0 example
          and I set duration to 2
          and I click the 'show-btn' button
        Then I see a snack-bar-notification
         and last notification reads 'Pizza party!!! 🍕'

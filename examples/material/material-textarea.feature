Feature: Check performance of textarea

    Scenario: Fill a textarea using send_keys

        Given I am at the "Input overview"
          and I have loaded a long text file
          and I use the input-overview example
          and I use the "Leave a comment" in there
        When I type the long text in
        Then I can read the long text back

    Scenario: Fill a textarea using .value

        Given I am at the "Input overview"
          and I have loaded a long text file
          and I use the input-overview example
          and I use the "Leave a comment" in there
        When I paste the long text in
        Then I can read the long text back


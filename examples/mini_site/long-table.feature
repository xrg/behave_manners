Feature: Long-table operations

    @wip
    Scenario: read a table of 100 rows
        Given I see a long table with 100 rows
        Then I can count the lines of that table

    Scenario: read a table of 200 rows
        Given I see a long table with 200 rows
        Then I can count the lines of that table

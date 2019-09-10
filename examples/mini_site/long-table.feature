Feature: Long-table operations

    Scenario: read a table of 100 rows
        Given I see a long table with 100 rows
        Then I can count the lines of that table

    Scenario: read a table of 200 rows
        Given I see a long table with 200 rows
        Then I can count the lines of that table

    Scenario: locate row in 200
        Given I see a long table with 300 rows
        When I find the line with Cell="C56"
        Then That line has Name="Foo 38"

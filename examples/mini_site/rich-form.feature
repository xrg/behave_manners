Feature: corner cases of components

    Background:
     Given I am at the "Rich Form"

    Scenario: Test sections
     When I look for the sections
     Then I find 4 entries
     And the id of section_0 is "section1"
     And the title of section_0 is "Title 1"
     And the id of section_1 is "section2"
     And the id of section_2 is "section3"
     And the id of section_3 is "section4"

    Scenario: Test the form
    When I look for form fields
    Then I find 5 entries
    And these entries are called
        | Name    |
        | Field A |
        | Field B |
        | Field D |
        | Field F |
        | Field H |

    Scenario: Test inactive fields
    When I look for inactive fields
    Then I find 3 entries
    And these entries are called
        | Name    |
        | Field C |
        | Field E |
        | Field G |

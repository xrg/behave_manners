Feature: Check download of files

Scenario: Download a file, explicit wait

    Given I am at the "Download Page"
     When I click the link to download
      And I wait for 21sec
     Then there is a new data file

Scenario: Start downloading, look too early

    Given I am at the "Download Page"
     When I click the link to download
      And I wait for 5sec
     Then there is no new data file

Scenario: Look for file before downloading

    Given I am at the "Download Page"
     When I wait for 15sec
     Then there is no new data file

Scenario: Download, implicit wait
    Given I am at the "Download Page"
     When I click the link to download
     Then I get a new data file

@wip
Scenario: Download same file twice
   Given I am at the "Download Page"
     When I click the fixed download
     Then I get a new data file
     When I click the fixed link again
     Then I get a new data file
     When I click the fixed link again
     Then I get a new data file

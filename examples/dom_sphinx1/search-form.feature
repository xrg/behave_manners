Feature: Check trivial functionality of the site

Scenario: Use the search form

Given I am at the "Index Page"
When I use the search_form
And I enter "Foo bar" in the query box
And I click submit
Then I am directed to the "Results Page"

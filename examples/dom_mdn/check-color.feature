Feature: Check trivial functionality of the site

Scenario: Use the search form

Given I am at the "Index Page"
When I use the search_form
Then I check that its color is blue

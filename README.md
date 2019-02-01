===============
Behave manners
===============

```Gherkin

  Given: that real-world scenarios are more complicated than examples
    and: sites are now bloated with many layers of components
   When: I write feature tests
   Then: I want them to be simple, abstract
    and: I want them to be thorough and precise
```

A set of utility methods, on top of `behave` test framework.
This goes further than the Gherkin language, implementing a more rich
set of operators and testing flows.


1. Standard web (browser) calls
  Binds to `selenium` in a consistent way

2. Inventory of web components
  Allows web elements to be referenced, discovered and grouped in a
  declarative way
  
3. Method steps
  Makes Gherkin scenarios re-usable through abstracting in a *step*

4. Test flows
  Implement branching and looping within Gherkin scenarios.
  



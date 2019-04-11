pagelems: Page Elements
========================

Page elements (or pagelems) is a custom html-like language of defining patterns
for **matching** remote DOM trees. This language is designed to resemble HTML
as much as possible, but is NOT the kind of html that would render into the DOM
of a page.

Rather, it is the inverse: it is a declarative language of *parsing* that DOM.


Rules/principles
-----------------

Understanding the design of page elements comes after considering the following:

Principles

 * Markup shall be as simple as possible
 * Markup must resemble HTML, share concepts/features of HTML5
 * developer should write enough markup to uniquely identify components
 * Markup shall provide a way to *mark* components discovered, and their
   attributes
 * Markup is by design nested, a lot
 * Markup shall provide ways to share blocks and refer back and forth to
   others


Rules

#. plain markup should match the same markup on the remote
   eg. ``<div class="foo"><span>Text</span></div>`` should match a DIV
   containing a span with text="Text" etc.
#. attributes and elements not mentioned DO match
   In the example above, all other attributes of the ``<div>`` or some other
   element within that should be allowed.
#. children elements match children in the DOM, *direct* descendants unless
   explicitly decorated (with ``pe-deep`` )
#. some special elements+attributes, all decorated with the **pe-** prefix
   may modify this straightforward HTML matching
#. the special ``this`` attribute defines a component. All other elements
   are just matched, harvested for attributes, but not exposed.
#. attributes defined multiple times may be OR-ed together


Special elements
-----------------

Define constructs that modify the way DOM is structured.

``<pe-repeat>``

   Causes its contents to be matched multiple times, repeated naturally.

   .. note:: this is implied if ``this`` has a flexible definition, see below.
   
``<pe-choice>``

    Attempts to match the first of the contained components. Any of them may
    match.

``<pe-any>``

    Matches any html element. Otherwise its attributes and children match
    like any plain element.

``<pe-regex>``

    Matches element text by regular expression; then assigns attributes from
    named members of that expression

``<pe-deep>``

    Matches (its children) at any level deep from the parent element

``<pe-root>``

    Resets nesting to the DOM document root, matches children down from the root

``<pe-slotcontent>``

    Points back to the original content of the `slot`. See :ref:`Templates and Slots`

``<pe-group>``

    Matches all of the contained elements, in order. `pe-group` itself needs not
    match any element. Useful for ``<pe-choice>`` and repetitions


Special attributes
-------------------

``pe-deep``

    Matches this element any level down from the parent, not just direct ancestors

``pe-optional``

    Makes this element (and all contents) optional. No error if cannot match

``pe-controller``
``pe-ctrl``

    Picks an alternate controller, defines a scope at that level.
    See `Scopes and Controllers`

``slot``

    Defines slot name. See :ref:`Templates and Slots`


Special attribute: this
------------------------

``this`` deserves a section of its own.

It defines a component in the matched tree.

In its simplest form: ``this="egg"`` , it would define a component named "egg"
In the attribute form: ``this="[title]"`` it will scan the contents, then resolve
the `title` attribute, use the title's value as a name.
In the parametric form: ``this="col_%d"`` it may produce more than one components
using the integer count of matches.

.. highlight:: html

Example::

    <div class="chapter" this="first-chapter"> 
        <section this="[title]">
            <h3>[title]</h3>

            <p this="par_%d">
                [content]
            </p>
        </section>
    </div>


.. highlight:: none

The above would produce a Component tree like::

    first-chapter/
        Some Title/
            par_0/
              content="..."
            par_1/
              content="..."
        Other Title/
            par_0/
              content="..."


.. highlight:: python

Which exposes, say, that second content in python as::

    root['first-chapter']['Some Title']['par_1'].content


Templates and Slots
--------------------

TBD


Scopes and Controllers
-----------------------

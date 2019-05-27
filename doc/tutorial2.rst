.. _tutorial1:

Tutorial 2: writing page elements
==================================

Step-by-step demonstration on how page elements work and get related to the
target DOM.


.. note:: The example below includes code snippets from MDN site, by Mozilla
  Contributors and licensed under CC-BY-SA 2.5.


.. note:: MDN site's HTML is too good for `manners`. It is well written, clean
  and structured. Manners can do much worse than that.


HTML vs HTML
--------------

Open MDN in the `div element <https://developer.mozilla.org/en-US/docs/Web/HTML/Element/div>`_  .
Open the inspector to examine the DOM of that page.

.. highlight:: html

The body of the page, contracted, looks like this::

    <body data-slug="Web/HTML/Element/div" contextmenu="edit-history-menu" data-search-url="" class="document">

    <script>... </script>
        <ul id="nav-access">... </ul>

        <header id="main-header" class="header-main">...</header>

        <main id="content" role="main">...</main>
        <footer id="nav-footer" class="nav-footer">...</footer>
    </body>


And, focusing a part of the ``<main>`` element we could see a snippet like::

    <div id="toc" class="toc">
        <div class="center">
        <div class="toc-head">Jump to:</div>
            <ol class="toc-links">
            <li><a href="#Attributes" rel="internal" class="">Attributes</a></li>
            <li><a href="#Usage_notes" rel="internal" class="">Usage notes</a></li>
            <li><a href="#Examples" rel="internal" class="">Examples</a></li>
            <li><a href="#Specifications" rel="internal" class="">Specifications</a></li>
            <li><a href="#Browser_compatibility" rel="internal" class="">Browser compatibility</a></li>
            <li><a href="#See_also" rel="internal" class="toc-current">See also</a>
            </li></ol>
        </div>
    </div>


In principle, pasting the above section into a pagelem template file, should work. It
would match 1:1 to the MDN site DOM, that page.


Removing redundant elements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Not all html elements are worth matching. Say, that ``<div class="center">`` needs
not be that specific, nor the "Jump to:" text is any more specific than the ``id="toc"``
of the outer ``<div>``

So, the above snippet could be cleaned like::

    <div id="toc">
        <div>
        <ol class="toc-links">
            <li><a href="#Attributes">Attributes</a></li>
            <li><a href="#Usage_notes">Usage notes</a></li>
            <li><a href="#Examples">Examples</a></li>
            <li><a href="#Specifications">Specifications</a></li>
            <li><a href="#Browser_compatibility">Browser compatibility</a></li>
            <li><a href="#See_also" class="toc-current">See also</a>
            </li>
        </ol>
        </div>
    </div>


Adding components
~~~~~~~~~~~~~~~~~~~

The above will not `emit` any matched components, until ``this`` attributes are
set in the interesting elements::

    <div id="toc" this="page-toc">
        <div>
        <ol class="toc-links" this="links">
            <li this="Attributes"><a href="#Attributes">Attributes</a></li>
            <li><a href="#Usage_notes">Usage notes</a></li>
            <li><a href="#Examples">Examples</a></li>
            <li this="Specifications"><a href="#Specifications">Specifications</a></li>
            <li><a href="#Browser_compatibility">Browser compatibility</a></li>
            <li><a href="#See_also" class="toc-current">See also</a>
            </li>
        </ol>
        </div>
    </div>


That would produce a structure of components like::

    [page-toc]
      - [links]
          - [Attributes]
          - [Specifications]


Generalizing
~~~~~~~~~~~~~

Then, the indidual ``<li>`` elements should be covered all with one rule, rather
than hard-coding their exact attributes. This allows the same `toc` code to match
any table of contents that conforms to this layout.

Pagelem code now can be simplified like::

    <div id="toc" this="page-toc">
        <div>
        <ol class="toc-links" this="links">
            <li this="[title]"><a href="[href]">[title]</a></li>
        </ol>
        </div>
    </div>

Getting simpler, and will also match all entries in the TOC this way.

``href="[href]"`` syntax means that the value of ``href=`` attribute will be assigned
to a ``href`` attribute of the resulting component. Will match anything in there.
Likewise ``[title]`` as text of an element will copy whatever text into a ``title``
attribute.

Then, ``this="[title]"`` means that the value assigned to ``title`` becomes the name
of the resulting component.

Thus, the resulting component structure after this generalisation should now be::

    [page-toc]
      - [links]
          - [Attributes]
              href = #Attributes
              title = Attributes
          - [Usage notes]
              href = #Usage_notes
              title = Usage notes
          - [Examples]
              href = #Examples
              title = Examples
          ...


Full page
----------

The above example cannot work standalone; rather it needs to be put in context of
a full HTML page. Assuming the earlier structure, it would need to be written as::

    <html>
    <body>
        <main id="content" role="main">
            <div id="toc" this="page-toc">
                <div>
                <ol class="toc-links" this="links">
                    <li this="[title]"><a href="[href]">[title]</a></li>
                </ol>
                </div>
            </div>
        </main>
    </body>
    </html>


This works for the MDN case, because "toc" is just one level down from "main". But
would become worse if "toc" had been somewhere deep within the page DOM.

In that case, intermediate levels could be skipped with::

    <html>
    <body>
            <div pe-deep id="toc" this="page-toc">
                <ol pe-deep class="toc-links" this="links">
                    <li this="[title]"><a href="[href]">[title]</a></li>
                </ol>
            </div>
    </body>
    </html>


making code now more compact.


Templating
------------

Since the TOC, footer and menu of this site are expected to be re-occuring across
all pages, makes sense to write them as re-usable templates

*gallery.html* ::

    <html>
    <body>
        <template id="toc">
            <div pe-deep id="toc" this="page-toc">
                <ol pe-deep class="toc-links" this="links">
                    <li this="[title]"><a href="[href]">[title]</a></li>
                </ol>
            </div>
        </template>

        <template id="header">
            <header id="main-header" class="header-main">...</header>
        </template>

        <template id="footer">
            <footer id="nav-footer" class="nav-footer">... </footer>
        </template>
    </body>
    </html>


*div-element.html* ::

    <html>
    <head>
        <link rel="import" href="gallery.html">
    </head>
    <body>
        <use-template id="header"/>

        <main id="content" role="main">
            <use-template id="toc"/>

            <!--custom code for catching the div-element page content -->
        </main>

        <use-template id="footer"/>
    </body>
    </html>


Templates may be called repeatedly in some page, even recursively.


Attribute matching
-------------------

Attributes of pagelems will match same attributes on remote DOM, by default.

Example::

    <div class="toc">

will match a `div` only if it's class equals to "toc". That's not always convenient,
since other classes may exist along "toc", that matching should ignore.

::

    <div class="+toc">


will then match if the div's class *contains* "toc".

Then, several values could be or-ed by mentioning them each::

    <div role="document" role="article">


Writing ``title="[tooltip]"`` will NOT attempt any match, but transfer the value
of remote DOM attribute ``title`` to Component attribute ``.tooltip`` . That can
co-exist with a matcher, like::

    <div class="[class_]" class="+important">


Note here the underscore after ``class_`` , because attribute names need to be
valid Python variable names, ``class`` is a reserved word.

Attribute matching can be negated with the ``!`` operator::

    <div role="!contentinfo">


or, when the element should not contain a class::

    <div class="!+hidden">




Other pagelems
---------------

The `pagelem` HTML-like language offers some other extra elements and attributes
that help match remote DOM with less code on the testing side.

Components may be tagged as ``pe-optional`` rather than failing the match. Pagelem
can match regardless of DOM tag with ``<pe-any>`` element.

Alternate structures may be matched with ``<pe-choice>`` .
Within a repetition or ``<pe-choice>`` , collections of elements can be forced to
go together in a ``<pe-group>``.

More about them can be read in the reference and supplied examples.

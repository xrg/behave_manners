
Built-in page elements Reference
==================================


.. highlight:: html

.. py:currentmodule:: behave_manners.pagelems.page_elements


Standard HTML elements
------------------------

Some of the standard HTML elements need special handling, therefore
they have corresponding classes defined in pagelems.

**Otherwise, any other elements will be matched verbatim**

.. autoclass:: DHtmlObject(tag: <html>)

.. autoclass:: DHeadElement(tag: <head>)

.. autoclass:: DLinkObject(tag: <link>)

.. autoclass:: DBodyElement(tag: <body>)

.. autoclass:: ScriptElement(tag: <script>)

.. autoclass:: InputElement(tag: <input>)

.. autoclass:: TextAreaObj(tag: <textarea>)

.. autoclass:: GHtmlObject(tag: <html> * in gallery )


Templates and slots
---------------------

Templates and slots are defined in HTML5. This concept is re-used in pagelems,
but as a means of parsing. See: :ref:`templates-and-slots`

.. autoclass:: DTemplateElement(tag: <template>)

.. autoclass:: DSlotElement(tag: <slot>)

.. autoclass:: DSlotContentElement(tag: <pe-slotcontent>)

.. autoclass:: DUseTemplateElem(tag: <use-template>)



Pagelem flow elements
-----------------------

.. autoclass:: DeepContainObj(tag: <pe-deep>)


.. autoclass:: RootAgainElem(tag: <pe-root>)


.. autoclass:: RepeatObj(tag: <pe-repeat>)


.. autoclass:: PeChoiceElement(tag: <pe-choice>)


.. autoclass:: PeGroupElement(tag: <pe-group>)


.. autoclass:: PeMatchIDElement(tag: <pe-matchid>)



Pagelem match elements
------------------------

.. autoclass:: AnyElement(tag: <pe-any>)

    .. py:data:: this="name"

        Exposes the element as a component under that name

    .. py:data:: slot="name"

        Attaches this element into a `<slot>` of a `<template>`

        *Only valid within* ``<use-template>`` *blocks*

    .. py:data:: pe-deep

        Matches that element at any nested level under the parent.
        Equivalent of puting that element within a `<pe-deep>` tag

    .. py:data:: pe-optional

        Makes matching optional, this element and any children may
        not exist.

    .. py:data:: pe-controller="some.controller"

        Uses `some.controller` to complement functionality of this
        component.

    .. py:data:: pe-ctrl

        Synonym of ``pe-controller``


.. autoclass:: PeNotElement(tag: <pe-not>)


.. autoclass:: RegexElement(tag: <pe-regex>)



Pagelem data elements
-----------------------


.. autoclass:: PeDataElement(tag: <pe-data>)


.. autoclass:: PEScopeDataElement(tag: <pe-scopedata>)


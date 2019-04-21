.. _scopes-controllers:

Scopes and Controllers
=======================

Scopes and Controllers are a way to inject extra behaviour onto components, from
code written in Python. They are able to abstract non-trivial interactions as if
they were instance methods to the component objects.

Scopes have their own tree (hierarchy) are deliberately *not* 1:1 with components.
Reason is to keep code minimal, not to mandate extra code per each component.
In practice, few of the components, only, will ever need their own controller.

.. note:: *scopes* and *controllers* are used as terms interchangeably, they 
    are the same thing. A `controller` is the class that defines custom behaviour,
    a `scope` is the instantiated object of that class, that could also have state.


Service Metaclass
------------------

Controller classes are using the `Service Meta` class, derive from :py:class:`DOMScope` .
This means that they can be referenced by ``_name``, and can be overriden by defining
the same name in some custom python module.


Inheritance
------------

Apart from python (or rather service-meta) inheritance, scopes also hold a reference
of their parent in the Component Tree. By default, they *inherit* the attributes of
that parent scope. This allows nested components to call parent scope's methods, or
even to modify that parent's state.

In the example below, suppose that there is a minimal HTML document (into components)
with one component calling a custom controller (the 'fld-ctrl' one).

.. highlight:: python

In python, suppose the following code defines the controller classes::

    class MyScope(DOMScope):
        _name = 'page'

        def hello(self):
            return "Hello!"

    class FldCtrl(DOMScope):
        _name = 'fld-ctrl'

        def check_field(self, field):
            return field.value == 'ham'

Scope inheritance would look like this diagram:

.. image:: scopes-inheritance.svg

There is always a root scope (usually the ``.root`` class) [1] and a page one[2].
Also, all scopes inherit :py:class:`DOMScope` which is
denoted by ``[*]``.
But our ``MyScope`` class redefines the page, so it would have methods from both
'page' classes. So, anywhere in the document, components could say::

    content._scope.hello()
    
and use that method. Including the 'field' component.

Then, the field component has its own controller [3], hence scope. This means that
the field component, including any sub-components there, can say::

    field_component._scope.check_field(sub_component)


Controllers of components
--------------------------

But calling ``_scope`` of a component, then passing the component as an argument
is not trivial, is it? In fact, by design, this is meant only for some inter-component
methods.

Component methods can be defined within a controller class through the **Component**
special class::

    class FldCtrl(DOMScope):
        _name = 'fld-ctrl'
    
        class Component(object):
            def check(self):
                assert self.value == 'ham'

In the previous example, this means that the 'field' component would be decorated
with that extra ``check()`` method.

Rules are:

#. the special class must be called `Component`
#. that class should derive from `object` (but :py:class:`ComponentProxy` is also allowed)
#. the component will still be a `ComponentProxy` , will *never* really inherit that
   special `Component` class
#. methods of the `Component` class will be bound to the `ComponentProxy`, hence
   ``self`` will refer to the `ComponentProxy` instance
#. `Component` may also have properties, static methods
#. private members are **not** copied to the `ComponentProxy`. They are discarded.
#. that applies to ``__init__()`` too. Components are volatile, they have no ordinary
   object lifecycle
#. if ``MyScope`` were to define a `Component` class, this would *not* apply to
   the "fld" component
#. but, if 'fld-ctrl' class is overriden, and the overriding class also defines
   a `Component` subclass, then *both* will have their members decorating "fld"
   component.


# -*- coding: UTF-8 -*-

from abc import abstractmethod

""" Pseudo-objects of 'actions' that can be /assigned/ to components

    Since the components and their attributes may be virtual (ie. dynamic
    attribute that returns its value as scalar), there must be a way to
    expose the object on the remote side and act on it (rather than just
    assigning a scalar value to it).
    
    Pseudo-objects allow it::
        
    >>> from behave_manners.pagelems.actions import click
    >>> form = page['The form']
    >>> form.name = 'Some name'
    >>> assert form.date == '2019-01-01'   # it would be a string
    >>> form.date = click()   # assign an action, ie. click the field!

"""

class Action(object):
    def __init__(self):
        pass

    @abstractmethod
    def act_on_descriptor(self, descr, elem):
        """Perform this action on some remote element

            :param descr: the descriptor instance of that attribute
            :type descr: .dom_descriptors.DomDescriptor
            :param elem: remote web element
        """
        pass


class click(Action):
    def act_on_descriptor(self, descr, elem):
        elem.click()



# eof

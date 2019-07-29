# -*- coding: UTF-8 -*-

from __future__ import absolute_import
import logging
from abc import abstractmethod
import copy
from .exceptions import CAttributeError, CAttributeNoElementError
from .actions import Action
# from selenium.webdriver.remote.webdriver import WebElement
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
import six


class DomDescriptor(object):
    """Base class for descriptors
    """
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def _elem(self, comp):
        """Locate the web element from given component
        """
        raise NotImplementedError


class AttrGetter(DomDescriptor):
    """Descriptor to get some attribute of a `ComponentProxy`
    """
    __slots__ = ('xpath', 'name', 'optional')
    logger = logging.getLogger(__name__ + '.attrs')

    def __init__(self, name, xpath=None, optional=False):
        super(AttrGetter, self).__init__(name)
        self.xpath = xpath
        self.optional = optional

    def for_xpath(self, xpath):
        """Return a copy of this descriptor, for a given xpath

            If `xpath` is same as ours, return `self`
        """
        if xpath == self.xpath:
            return self
        else:
            c = copy.copy(self)
            c.xpath = xpath
            return c

    def for_optional(self):
        """Return copy of self with `optional` set
        """
        if self.optional:
            return self
        else:
            c = copy.copy(self)
            c.optional = True
            return c

    def _elem(self, comp):
        """Locate the web element from given component
        """
        try:
            elem = comp._remote
            if self.xpath:
                elem = elem.find_element_by_xpath(self.xpath)
        except NoSuchElementException as e:
            if self.optional:
                self.logger.debug("Attribute %r.%s could not be found, returning None",
                                  comp, self.name)
                return None
            else:
                raise CAttributeNoElementError(six.text_type(e), component=comp)
        return elem

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        return elem.get_attribute(self.name)

    def __set__(self, comp, value):
        if isinstance(value, Action):
            elem = self._elem(comp)
            if elem is None:
                raise CAttributeError("Cannot set value of missing element", component=comp)
            return value.act_on_descriptor(self, elem)
        raise CAttributeError("%s is readonly" % self.name, component=comp)

    def __delete__(self, comp):
        raise CAttributeError("%s is readonly" % self.name, component=comp)


class AttrEqualsGetter(AttrGetter):
    """Finds a word inside remote attribute, as boolean local

        Example::

            <a class="[is_blue]:blue">

        will set `component.is_blue = True` if anchor is like `<a class="blue">`

    """

    __slots__ = ('xpath', 'name', 'optional', 'token')

    def __init__(self, name, token='', xpath=None, optional=False):
        super(AttrEqualsGetter, self).__init__(name, xpath=xpath, optional=optional)
        self.token = token

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        return elem.get_attribute(self.name) == self.token

    def __set__(self, comp, value):
        raise CAttributeError("%s is readonly" % self.name, component=comp)


class AttrContainsGetter(AttrEqualsGetter):
    """Finds a word inside remote attribute, as boolean local

        Example::

            <a class="[is_blue]:+blue">

        will set `component.is_blue = True` if anchor is like `<a class="foo blue bar">`

    """

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        value = elem.get_attribute(self.name)
        return value and (self.token in value.split(' '))


class AttrAnyChoiceGetter(AttrGetter):
    """Finds any of given words inside remote attribute, as a single local word

        Example::

            <a class="[color]:{blue|red|green|magenta}">

        will set `component.color = 'blue'` if anchor is like `<a class="foo blue bar">`

    """

    __slots__ = ('xpath', 'name', 'optional', 'tokens')

    def __init__(self, name, tokens='', xpath=None, optional=False):
        super(AttrAnyChoiceGetter, self).__init__(name, xpath=xpath, optional=optional)
        if isinstance(tokens, list):
            self.tokens = tokens
        else:
            self.tokens = tokens.split('|')

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        val = elem.get_attribute(self.name)
        if not val:
            return None
        val = val.split()
        for t in self.tokens:  # ordered!
            if t in val:
                return t
        return None

    def __set__(self, comp, value):
        raise CAttributeError("%s is readonly" % self.name, component=comp)


class TextAttrGetter(AttrGetter):
    """Descriptor that returns the text of some DOM element
    """
    def __init__(self, xpath, optional=False, do_strip=False):
        super(TextAttrGetter, self).__init__('text', xpath, optional=optional)
        self._do_strip = do_strip

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        ret = elem.text
        if not ret:
            ret = elem.get_attribute('innerText')
        if ret and self._do_strip:
            ret = ret.strip()
        return ret


class PartialTextAttrGetter(TextAttrGetter):
    """Obtain the text of some DOM element, excluding text of sub-elements
    """
    def __init__(self, xpath, before_elem=None, after_elem=None, **kwargs):
        super(PartialTextAttrGetter, self).__init__(xpath, **kwargs)
        self._after_elem = after_elem
        self._before_elem = before_elem

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        js = 'let cnodes = arguments[0].childNodes;\n' \
             'let i = 0; let ret = "";\n'
        if self._after_elem == '*':
            js += '''
                for (;i<cnodes.length;i++){
                    if (cnodes[i].nodeType == 3) break;
                }
                '''
        elif self._after_elem:
            js += '''
                for (;i<cnodes.length;i++){
                    if ((cnodes[i].nodeType == 1) && (cnodes[i].tagName == arguments[1])) break;
                }
                '''
        js += 'for(;i<cnodes.length; i++){ \n'
        if self._before_elem == '*':
            js += '  if (cnodes[i].nodeType == 1) break; '
        elif self._before_elem:
            js += '  if ((cnodes[i].nodeType == 1) && (cnodes[i].tagName == arguments[2])) break;\n'
        js += '  if (cnodes[i].nodeType == 3) { ret += cnodes[i].nodeValue; }\n}\nreturn ret;'

        ret = elem.parent.execute_script(js, elem, self._after_elem, self._before_elem)
        if ret and self._do_strip:
            ret = ret.strip()
        return ret


class RegexAttrGetter(AttrGetter):
    """Obtain text, resolve it with regular expression into attribute
    """
    def __init__(self, regex, xpath, group=None, optional=False):
        super(RegexAttrGetter, self).__init__('text', xpath, optional=optional)
        self._regex = regex
        self._group = group

    def __get__(self, comp, type=None):
        elem = self._elem(comp)
        if elem is None:
            return None

        m = self._regex.match(elem.text or '')
        if not m:
            return None

        if self._group:
            return m.group(self._group)
        else:
            return m.group()


class InputCompatDescr(AttrGetter):
    """Get/set the value of `<input>` element. Use 'send_keys()' for the setter
    """
    def __init__(self, xpath):
        super(InputCompatDescr, self).__init__('value', xpath)

    def __delete__(self, comp):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        elem.clear()

    def __set__(self, comp, value):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        if isinstance(value, Action):
            return value.act_on_descriptor(self, elem)
        elem.clear()
        elem.send_keys(value)


class InputValueDescr(InputCompatDescr):
    """Get/set the value of input. Use direct JS setter

        This is way more efficient than `send_keys()`, but known to have issues
        with elements that have JS validators etc.
    """
    def __set__(self, comp, value):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        if isinstance(value, Action):
            return value.act_on_descriptor(self, elem)
        driver = elem.parent
        driver.execute_script("arguments[0].value = arguments[1];", elem, value)


class InputCombiDescr(InputCompatDescr):
    def __set__(self, comp, value):
        elem = self._elem(comp)
        if elem is None:
            raise CAttributeError("Cannot set value of missing element", component=comp)
        if isinstance(value, Action):
            return value.act_on_descriptor(self, elem)
        driver = elem.parent
        driver.execute_script("arguments[0].focus(); "
                              "arguments[0].value = arguments[1];",
                              elem, value[:-1])
        elem.send_keys(Keys.END, value[-1])


class InputFileDescr(InputCompatDescr):
    class File(object):
        def __init__(self, name, **kwargs):
            self.name = name
            self.__dict__.update(kwargs)

        def __str__(self):
            return self.name

        def __repr__(self):
            return "<File: %s>" % self.name

        def __eq__(self, other):
            if isinstance(other, six.string_types):
                return self.name == other
            elif isinstance(other, InputFileDescr.File):
                return self.name == other.name
            else:
                return False

    def __get__(self, comp):
        elem = self._elem(comp)
        if elem is None:
            return None

        return [InputFileDescr.File(**f) for f in elem.get_property('files')]

#eof

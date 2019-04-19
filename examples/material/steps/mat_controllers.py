# -*- coding: UTF-8 -*-

import time
from behave_manners.pagelems import DOMScope
from behave_manners.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class MatRadioCtrl(DOMScope):
    _name = 'mat-radio'

    class Component(object):

        @property
        def value(self):
            for k, it in self.items():
                if 'mat-radio-checked' in it.class_.split(' '):
                    return it.value
            return None

        @value.setter
        def value(self, val):
            for k, it in self.items():
                if it.value == val:
                    ActionChains(it).move_to_element(it).click().perform()
                    break
            else:
                raise ValueError("Value '%s' not in radio-group options" % val)

        def set_by_label(self, label):
            for k, it in self.items():
                if it.text == label:
                    it.click()
                    #time.sleep(0.1)
                    it.click()  # FIXME
                    break
            else:
                raise ValueError("Label '%s' not in radio-group options" % label)
            self._scope.wait_all('short', welem=self._remote)


class MatAutocompleteCtrl(DOMScope):
    _name = 'mat-autocomplete'

    class Component(object):
        @property
        def value(self):
            return self['input'].value

        @value.setter
        def value(self, val):
            if not val:
                self['input'].value = ''
                return

            # for testing only
            ActionChains(self).move_to_element(self).perform()

            # Type (fast) most of the string inside the input
            self['input'].value = val[:-1]
            # Then, click the last letter to let the dropdown open
            self['input'].send_keys(Keys.END, val[-1])
            self._scope.wait_all('short', welem=self._remote)
            self['panel'][val].click()
            self._scope.wait_all('short', welem=self._remote)
            assert self['input'].value == val


#eof

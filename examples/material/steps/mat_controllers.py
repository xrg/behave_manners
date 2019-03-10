# -*- coding: UTF-8 -*-

import time
from behave_manners.pagelems import DOMScope
from behave_manners.action_chains import ActionChains


class MatRadioCtrl(DOMScope):
    _name = 'mat-radio'
    
    def _cwrap_get_value(self, comp, name):
        """Defines method 'comp.get_value()' on the radio-group component
        """
        
        def _get_value():
            for k, it in comp.items():
                if 'mat-radio-checked' in it.class_.split(' '):
                    return it.value
            return None

        return _get_value

    def _cwrap_set_value(self, comp, name):
        def _set_value(val):
            for k, it in comp.items():
                if it.value == val:
                    ActionChains(it).move_to_element(it).click().perform()
                    break
            else:
                raise ValueError("Value '%s' not in radio-group options" % val)
        return _set_value

    def _cwrap_set_by_label(self, comp, name):
        def _set_value(label):
            for k, it in comp.items():
                if it.text == label:
                    it.click()
                    #time.sleep(0.1)
                    it.click()  # FIXME
                    break
            else:
                raise ValueError("Label '%s' not in radio-group options" % label)
            comp._scope.wait_all('short', welem=comp._remote)
        return _set_value


#eof
# -*-coding: UTF-8 -*-

from selenium.common.exceptions import NoSuchElementException


class ElementNotFound(NoSuchElementException):
    def __init__(self, msg=None, screen=None, stacktrace=None, 
                 parent=None, selector=None):
        if not msg:
            msg = "No such element: %s" % selector
        super(ElementNotFound, self).__init__(msg, screen=screen, stacktrace=stacktrace)
        self.parent = parent
        self.selector = selector


#eof

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

    @property
    def pretty_parent(self):
        """String of parent element, in pretty format
        """
        if self.parent is None:
            return '<unknown>'
        try:
            parent_id = self.parent.get_attribute('id')
            if parent_id:
                return '<%s id="%s">' % (self.parent.tag_name, parent_id)
            else:
                return '<%s>' % self.parent.tag_name
        except Exception:
            return repr(self.parent)


#eof
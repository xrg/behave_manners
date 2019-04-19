# -*- coding: UTF-8 -*-

from __future__ import absolute_import
from f3utils.service_meta import _ServiceMeta


class DOM_Meta(_ServiceMeta):
    """Metaclass for `DOMScope` ones.
    
        Prepares a dictionary of descriptors that the scope can apply
        to components or pages under it.
        Operates at class initialization phase,
    """
    
    def __new__(mcls, name, bases, namespace):
        namespace.setdefault('_page_descriptors', {})
        namespace.setdefault('_comp_descriptors', {})
        comp_cls = namespace.get('Component', None)
        page_cls = namespace.get('Page', None)

        # here, _ServiceMeta will juggle with baseclasses etc.:
        newcls = super(DOM_Meta, mcls).__new__(mcls, name, bases, namespace)

        # start with same descriptors as baseclass(es)
        for baseclass in newcls.__bases__:   # different from `bases` above
            if hasattr(baseclass, '_page_descriptors'):
                newcls._page_descriptors.update(baseclass._page_descriptors)
            if hasattr(baseclass, '_comp_descriptors'):
                newcls._comp_descriptors.update(baseclass._comp_descriptors)

        for dcls, ddir in [(comp_cls, newcls._comp_descriptors),
                           (page_cls, newcls._page_descriptors)]:
            if dcls is None or type(dcls) is not type:
                # namespace does not have 'Component' or 'Page' *class*
                continue

            for k, descr in dcls.__dict__.items():
                if k.startswith('__') or k.startswith('_%s__' % dcls.__name__):
                    continue
                if not (hasattr(descr, '__get__') or hasattr(descr, '__set__')):
                    # not a descriptor, may be a static value or anything
                    descr = staticmethod(descr)     # works for anything, converts to descriptor
                ddir[k] = descr

        return newcls

# eof

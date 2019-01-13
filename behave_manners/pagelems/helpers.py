# -*-coding: UTF-8 -*-

import re


word_re = re.compile(r'\w+$')

def textescape(tstr):
    if "'" not in tstr:
        return "'%s'" % tstr
    elif '"' not in tstr:
        return '"%s"' % tstr
    else:
        return "concat('" + "', '\"', '".join(tstr.split('"')) + "')"  # Perl alert!


def prepend_xpath(pre, xpath):
    """Prepend some xpath to another, properly joining the slashes
    
    """

    if pre.endswith('./'):
        if xpath.startswith('./'):
            return pre[:-2] + xpath
        elif xpath.startswith('/'):  # including '//'
            return pre[:-1] + xpath
    elif pre.endswith('//'):
        return pre + xpath.lstrip('/')
    elif pre.endswith('/') and xpath.startswith('/'):
        return pre[:-1] + xpath

    return pre + xpath

# eof

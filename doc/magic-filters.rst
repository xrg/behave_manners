.. _magic-filters:

Magic filters
==============

Locating a particular row in some long list (table) of data would be very
inefficient with manners. Reason is, the lazy way manners build/discover
sub-components and attributes.

.. highlight:: python

Consider the following snippet::

    table = context.cur_page['section']['story']['haystack']

    for row in table['rows']:
        if row['col_4'].text == 'needle':
            needle_row = row
            break
    else:
        raise CAssertionError("Cannot find needle in haystack",
                              component=table)


Manners up to v0.11 would need to iterate over all rows, and for each one
of those compute all columns (up to 'col_4'), then go back and retrieve
the 'text' attribute of that element, to compare with 'needle'. Each of
those steps would involve 1-3 selenium commands to achieve. It would take
a few seconds (depending on the position of that row) to reach there.

Magic filters can provide a much faster solution to this case.

Assuming that code can be refactored as::

    table = context.cur_page['section']['story']['haystack']

    for row in table['rows'].filter(lambda r: r['col_4'].text == 'needle'):
        needle_row = row
        break
    else:
        raise CAssertionError("Cannot find needle in haystack",
                              component=table)

then this loop could be resolved in as little as *one* Selenium call.
See, magic filters operate on that `lambda` function and can reduce it to
an XPath locator, before rows of the table would be iterated over. Thus,
the expensive part is pushed from Python (manners) up to the browser (XPath)
to locate and match.

Not all operators are currently supported in that lambda. It /could/ even be
a named function or object method. But can only refer to sub-items using `[]`,
attributes and equality checks. This is work in progress.

Note:: in situations like the above example, if 'rows' were to be called like
`row_%d` after their position, `.filter()` would never get that number right,
since it locates the desired one by skipping any non-matching ones (but cannot
count the skipped ones).



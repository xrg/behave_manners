#!/usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import print_function
from __future__ import absolute_import
import logging
from behave_manners.pagelems.loaders import FSLoader
from behave_manners.pagelems.index_elems import DSiteCollection


def cmdline_main():
    """when sun as a script, this behaves like a syntax checker for DPO files
    """
    import argparse
    parser = argparse.ArgumentParser(description='check validity of DPO template files')
    parser.add_argument('-N', '--no-preloads', action='store_true',
                        help='check only the index file')
    parser.add_argument('index', metavar='index.html',
                        help="path to 'index.html' file")
    parser.add_argument('inputs', metavar='page.html', nargs='*',
                        help='input files')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    site = DSiteCollection(FSLoader('.'))
    log = logging.getLogger('main')
    if args.index:
        log.debug("Loading index from %s", args.index)
        site.load_index(args.index)
        if not args.no_preloads:
            site.load_preloads()

    for pfile in args.inputs:
        site.load_pagefile(pfile)

    if not args.no_preloads:
        site.load_preloads()
        
    log.info("Site collection contains %d pages, %d files",
             len(site.page_dir), len(site.file_dir))
    
    print("Site files:")
    for trg, content in site.file_dir.items():
        print("    ", trg, content and '*' or '')
    
    print("\nSite pages:")
    for page, trg in site.page_dir.items():
        print("    %s: %s" % (page, trg))

    for fname in args.inputs:
        pagetmpl = site.get_by_file(fname)
        print("\nTemplate: %s" % fname)
        for lvl, name, details in pagetmpl.pretty_dom():
            print('  '* lvl, name, details)


if __name__ == '__main__':
    cmdline_main()


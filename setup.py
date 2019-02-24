#!/usr/bin/env python
# -*- coding: utf-8 -*

import sys
import os.path
from setuptools import find_packages, setup

setup(
    name='behave-manners',
    version="0.1",
    description="web testing extensions to behave",
    long_description="""
    """,
    author="Panos Christeas",
    author_email="xrg@pefnos.com",
    url="http://github.com/xrg/behave_manners",
    provides = ["behave_manners"],
    packages = ["behave_manners"],
    entry_points={
        'console_scripts': [
            'behave-test-sitelems=behave_manners.pagelems.main:cmdline_main',
            'behave-run-browser=behave_manners.dpo_run_browser:cmdline_main',
            'behave-validate-remote=behave_manners.dpo_validator:cmdline_main'
            ]
    },
    install_requires=[
        "behave >= 1.2.6",
        "f3utils",
        "pyyaml",
        "selenium",
    ],
    cmdclass = {
    },
    extras_require={
        'docs': ["sphinx >= 1.6", "sphinx_bootstrap_theme >= 0.6"],
        'develop': [
        ],
    },
    license="BSD",
    classifiers=[
        # "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: BSD License",
    ],
    zip_safe = True,
)



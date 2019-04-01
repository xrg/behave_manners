#!/usr/bin/env python
# -*- coding: utf-8 -*

import sys
import os.path
from setuptools import find_packages, setup

try:
    with open('README.md', 'rt') as fp:
        long_description = fp.read()
except Exception:
    long_description = ''

setup(
    name='behave-manners',
    version="0.3",
    description="A layer of abstraction on top of `behave` for web-UI testing,"
                " designed to handle complexity of large sites",
    long_description=long_description,
    author="Panos Christeas",
    author_email="xrg@pefnos.com",
    url="http://github.com/xrg/behave_manners",
    provides = ["behave_manners"],
    packages = ["behave_manners", "behave_manners.pagelems", "behave_manners.steplib"],
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
        # 'docs': ["sphinx >= 1.6", "sphinx_bootstrap_theme >= 0.6"],
        'develop': [
        ],
    },
    license="BSD",
    classifiers=[
        "Development Status :: 3 - Alpha",
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


# eof

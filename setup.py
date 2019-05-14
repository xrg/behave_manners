#!/usr/bin/env python
# -*- coding: utf-8 -*

import sys
import os.path
from setuptools import find_packages, setup

try:
    with open('README.txt', 'rt') as fp:
        long_description = fp.read()
except Exception:
    long_description = ''

try:
    import subprocess
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.git')):
        git_ver = subprocess.check_output(['git', 'describe', '--tags',
                                           '--match', r'v[0-9]*\.[0-9]*'])
        version = git_ver[1:].strip().split('-', 2)[0]
except Exception as e:
    print("Could not get version: %s" % e)
    version = '0.5'

setup(
    name='behave-manners',
    version=version,
    description="A layer of abstraction on top of behave for web-UI testing,"
                " designed to handle complexity of large sites",
    long_description=long_description,
    long_description_content_type="text/markdown",
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

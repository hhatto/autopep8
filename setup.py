#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Setup for autopep8."""

import ast
import io
import sys

from setuptools import setup


INSTALL_REQUIRES = (
    ['pep8 >= 1.5.7'] +
    (['argparse'] if sys.version_info < (2, 7) else [])
)


def version():
    """Return version string."""
    with io.open('autopep8.py') as input_file:
        for line in input_file:
            if line.startswith('__version__'):
                return ast.parse(line).body[0].value.s


with io.open('README.rst') as readme:
    setup(
        name='autopep8',
        version=version(),
        description='A tool that automatically formats Python code to conform '
                    'to the PEP 8 style guide',
        long_description=readme.read(),
        license='Expat License',
        author='Hideo Hattori',
        author_email='hhatto.jp@gmail.com',
        url='https://github.com/hhatto/autopep8',
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: Console',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Software Development :: Quality Assurance',
        ],
        keywords='automation, pep8, format',
        install_requires=INSTALL_REQUIRES,
        test_suite='test.test_autopep8',
        py_modules=['autopep8'],
        zip_safe=False,
        entry_points={'console_scripts': ['autopep8 = autopep8:main']},
    )

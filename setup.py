#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import autopep8

setup(
    name='autopep8',
    version=autopep8.__version__,
    description="Automatic generated to pep8 checked code.",
    long_description=open("README.rst").read(),
    license='Expat License',
    author='Hideo Hattori',
    author_email='hhatto.jp@gmail.com',
    url='https://github.com/hhatto/autopep8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Unix Shell',
    ],
    keywords="automation pep8",
    install_requires=['pep8'],
    py_modules=['autopep8'],
    zip_safe=False,
    entry_points={'console_scripts': ['autopep8 = autopep8:main']},
)

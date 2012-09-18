autopep8
========
.. image:: https://secure.travis-ci.org/hhatto/autopep8.png?branch=master
   :target: https://secure.travis-ci.org/hhatto/autopep8
   :alt: Build status


About
-----
autopep8 automatically formats Python code to conform to the `PEP 8`_ style
guide. It uses the pep8_ utility to determine what parts of the code needs to
be formatted. autopep8 is capable of fixing most of the formatting issues_ that
can be reported by pep8.

.. _PEP 8: http://www.python.org/dev/peps/pep-0008
.. _issues: https://github.com/jcrocholl/pep8/wiki/ErrorCodes


Installation
------------
from pip::

    pip install --upgrade autopep8

from easy_install::

    easy_install -ZU autopep8


Requirements
------------
autopep8 requires pep8_ (>= 1.3.2). Older versions of pep8 will also work, but
autopep8 will run pep8 in a subprocess in that case (for compatibility
purposes).

.. _pep8: https://github.com/jcrocholl/pep8


Usage
-----
execute tool::

    $ autopep8 TARGET.py

before::

    import sys, os;
    print(                'hello' );

    def someone_likes_semicolons(                             foo  = None                          ,\
    bar='bar'):
        """Hello; bye."""; 1; 2;3
        print( 'A'<>foo)            #<> is a deprecated form of !=
        return 0;
    def func11():
        a=(   1,2, 3,"a"  );
        b  =[100,200,300  ,9876543210,'This is my very long string that goes on and on and on'  ]
        return (a, b)
    def func2(): total =(324942324324+32434234234234 -23423234243/ 324342342.+324234223432423412191) /12345.
    def func22(): return {True: True}.has_key({'foo': 2}.has_key('foo'));
    class UselessClass(object):
        def __init__    ( self, bar ):
         if bar : bar+=1;  bar=bar* bar   ; return bar
         else: raise ValueError, 'I am an error'
        def my_method(self):
                                                  print(self);

after::

    import sys
    import os
    print('hello')


    def someone_likes_semicolons(foo=None,
                                 bar='bar'):
        """Hello; bye."""
        1
        2
        3
        print('A' != foo)  # <> is a deprecated form of !=
        return 0


    def func11():
        a = (1, 2, 3, "a")
        b = [100, 200, 300, 9876543210,
             'This is my very long string that goes on and on and on']
        return (a, b)


    def func2():
        total = (324942324324 + 32434234234234 - 23423234243 / 324342342. +
                 324234223432423412191) / 12345.


    def func22():
        return ('foo' in {'foo': 2}) in {True: True}


    class UselessClass(object):
        def __init__(self, bar):
            if bar:
                bar += 1
                bar = bar * bar
                return bar
            else:
                raise ValueError('I am an error')

        def my_method(self):
            print(self)


options::

    Usage: autopep8 [options] [filename [filename ...]]

     A tool that automatically formats Python code to conform to the PEP 8 style
    guide.

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -v, --verbose         print verbose messages; multiple -v result in more
                            verbose messages
      -d, --diff            print the diff for the fixed source
      -i, --in-place        make changes to files in place
      -r, --recursive       run recursively; must be used with --in-place or
                            --diff
      -p PEP8_PASSES, --pep8-passes=PEP8_PASSES
                            maximum number of additional pep8 passes (default:
                            100)
      --ignore=IGNORE       do not fix these errors/warnings (e.g. E4,W)
      --select=SELECT       fix only these errors/warnings (e.g. E4,W)


Testing
-------
Test cases are in ``test/test_autopep8.py``. They can be run directly via
``python test/test_autopep8.py`` or via tox_. The latter is useful for
testing against multiple Python interpreters.

.. _`tox`: http://pypi.python.org/pypi/tox

Broad spectrum testing is available via ``test/acid.py``. This script runs
autopep8 against Python code and checks for correctness and completeness of
the code fix transformations. ``test/acid_pypi.py`` makes use of
``acid.py`` to test against the latest released packages on PyPi. In a similar
fashion, ``test/acid_github.py`` tests against Python code in Github
repositories.


Links
-----
* PyPI_
* GitHub_
* `Travis-CI`_
* Jenkins_

.. _PyPI: http://pypi.python.org/pypi/autopep8/
.. _GitHub: https://github.com/hhatto/autopep8
.. _`Travis-CI`: https://secure.travis-ci.org/hhatto/autopep8
.. _Jenkins: http://jenkins.hexacosa.net/job/autopep8/

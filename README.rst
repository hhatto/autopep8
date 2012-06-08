autopep8
========
.. image:: https://secure.travis-ci.org/hhatto/autopep8.png?branch=master
   :target: https://secure.travis-ci.org/hhatto/autopep8
   :alt: Build status


About
-----
autopep8 formats Python code based on the output of the pep8_ utility.


Installation
------------
from pip::

    pip install --upgrade autopep8

from easy_install::

    easy_install -ZU autopep8


Requirements
------------
autopep8 requires pep8_.

.. _pep8: https://github.com/jcrocholl/pep8


Usage
-----
execute tool::

    $ autopep8 TARGET.py

before::

    import sys, os


    print('hello' );


    def func1(   foo  ):
        print( 'A'+ foo);
            
        return 0



    def func11():
        a = (1,2, 3,"a");
        b = [100,200,300,9876543210,'This is my very long string that goes on and one and on']



        return (a, b)





    def func2():
    	pass
    def func22():
        pass

    def func3(bar):
        if bar : bar+=1;  bar=bar*bar   ; return bar
        else: raise ValueError, 'I am an error'

after::

    import sys
    import os


    print('hello')


    def func1(foo):
        print('A' + foo)

        return 0


    def func11():
        a = (1, 2, 3, "a")
        b = [100, 200, 300, 9876543210,
            'This is my very long string that goes on and one and on']

        return (a, b)


    def func2():
        pass


    def func22():
        pass


    def func3(bar):
        if bar:
            bar += 1
            bar = bar * bar
            return bar
        else:
            raise ValueError('I am an error')

options::

    Usage: autopep8 [options] [filename [filename ...]]

     A tool that automatically formats Python code to conform to the PEP 8 style
    guide.

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -v, --verbose         print verbose messages
      -d, --diff            print the diff for the fixed source
      -i, --in-place        make changes to files in place
      -p PEP8_PASSES, --pep8-passes=PEP8_PASSES
                            maximum number of additional pep8 passes (default:
                            100)
      --ignore=IGNORE       do not fix these errors/warnings (e.g. E4,W)
      --select=SELECT       select errors/warnings (e.g. E4,W)


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

About
=====
autopep8 formats Python code based on the output of the pep8_ utility.


Installation
============
from pip::

    pip install --upgrade autopep8

from easy_install::

    easy_install -ZU autopep8

Requirements
============
autopep8 requires pep8_.

.. _pep8: https://github.com/jcrocholl/pep8


Usage
=====
execute tool::

    $ autopep8 TARGET.py

before::

    import sys, os


    print 1 


    def func1():
        print "A"
        
        return 0



    def func11():
        a = (1,2, 3,"a")
        b = [1, 2, 3,"b"]
        return 1





    def func2():
        pass
    def func22():
        pass

    def func3():
        pass


after::

    import sys
    import os


    print 1


    def func1():
        print "A"

        return 0


    def func11():
        a = (1, 2, 3, "a")
        b = [1, 2, 3, "b"]
        return 1


    def func2():
        pass


    def func22():
        pass


    def func3():
        pass

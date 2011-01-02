About
=====
autopep8 is automatic generated to pep8 checked code.
This is old style tool, wrapped pep8_ via subprocess module.


Install
=======

from pip::

    pip install --upgrade autopep8

from easy_install::

    easy_install -ZU autopep8

Require
=======
autopep8 is used pep8_ (via subprocess).

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

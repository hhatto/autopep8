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
autopep8 requires pep8_ (>= 1.3). Older versions of pep8 will also work, but
autopep8 will run pep8 in a subprocess in that case (for compatibility
purposes).

.. _pep8: https://github.com/jcrocholl/pep8


Usage
-----
execute tool::

    $ autopep8 TARGET.py

before::

    import sys, os;;;;
    print(                `'hello'` );

    def someone_likes_semicolons(                             foo  = None                          ,
    bar='bar'):
        print( 'A'<>foo)            #<> is a deprecated form of !=
        return 0;;
    def func11():
        a=(   1,2, 3,"a"  );
        b  =[100,200,300  ,9876543210,'This is my very long string that goes on and one and on'  ]
        return (a, b)
    def func2(): total =(324942324324+32434234234234 -23423234243/ 324342342.+324234223432423412191) /12345.
    def func22(): pass;
    class UselessClass(object):
        def __init__    ( self, bar ):
         if bar : bar+=1;  bar=bar* bar   ; return bar
         else: raise ValueError, 'I am an error'
        def my_method(self):
          print(self);;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

after::

    import sys
    import os
    print(repr('hello'))


    def someone_likes_semicolons(foo=None,
                                 bar='bar'):
        print('A' != foo)  # <> is a deprecated form of !=
        return 0


    def func11():
        a = (1, 2, 3, "a")
        b = [100, 200, 300, 9876543210,
             'This is my very long string that goes on and one and on']
        return (a, b)


    def func2():
        total = (324942324324 + 32434234234234 - 23423234243 / 324342342. +
                 324234223432423412191) / 12345.


    def func22():
        pass


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


diff::

    --- original
    +++ fixed
    @@ -1,19 +1,38 @@
    -import sys, os;;;;
    -print(                `'hello'` );
    +import sys
    +import os
    +print(repr('hello'))
     
    -def someone_likes_semicolons(                             foo  = None                          ,
    -bar='bar'):
    -    print( 'A'<>foo)            #<> is a deprecated form of !=
    -    return 0;;
    +
    +def someone_likes_semicolons(foo=None,
    +                             bar='bar'):
    +    print('A' != foo)  # <> is a deprecated form of !=
    +    return 0
    +
    +
     def func11():
    -    a=(   1,2, 3,"a"  );
    -    b  =[100,200,300  ,9876543210,'This is my very long string that goes on and one and on'  ]
    +    a = (1, 2, 3, "a")
    +    b = [100, 200, 300, 9876543210,
    +         'This is my very long string that goes on and one and on']
         return (a, b)
    -def func2(): total =(324942324324+32434234234234 -23423234243/ 324342342.+324234223432423412191) /12345.
    -def func22(): pass;
    +
    +
    +def func2():
    +    total = (324942324324 + 32434234234234 - 23423234243 / 324342342. +
    +             324234223432423412191) / 12345.
    +
    +
    +def func22():
    +    pass
    +
    +
     class UselessClass(object):
    -    def __init__    ( self, bar ):
    -     if bar : bar+=1;  bar=bar* bar   ; return bar
    -     else: raise ValueError, 'I am an error'
    +    def __init__(self, bar):
    +        if bar:
    +            bar += 1
    +            bar = bar * bar
    +            return bar
    +        else:
    +            raise ValueError('I am an error')
    +
         def my_method(self):
    -      print(self);;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
    +        print(self)


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
      -r, --recursive       run recursively; must be used with --in-place or
                            --diff
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

autopep8
========
.. image:: https://travis-ci.org/hhatto/autopep8.png?branch=master
   :target: https://travis-ci.org/hhatto/autopep8
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
To modify a file in place::

    $ autopep8 -i <filename>

Before::

    import sys, os;

    def someone_likes_semicolons(                             foo  = None            ,\
    bar='bar'):
        """Hello; bye."""; 1; 2;3
        print( 'A'<>foo)            #<> is a deprecated form of !=
        return 0;
    def func11():
        a=(   1,2, 3,"a"  );
        ####This is a long comment. This should be wrapped to fit within 72 characters.
        x = [a,[100,200,300,9876543210,'This is a long string that goes on and on']]
    def func2(): total =324942324324+32434234234234-(23423234243/324342342.+32423/123.)
    def func22(): return {True: True}.has_key({'foo': 2}.has_key('foo'));
    class UselessClass(object):
        def __init__    ( self, bar ):
         #Comments should have a space after the hash.
         if bar : bar+=1;  bar=bar* bar   ; return bar
         else:
                        indentation_in_strings_should_not_be_touched = """
    		           hello
    world
    """
                        raise ValueError, indentation_in_strings_should_not_be_touched
        def my_method(self):
                                                  print(self);

After::

    import sys
    import os


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
        # This is a long comment. This should be wrapped to fit within 72
        # characters.
        x = [a, [100, 200, 300, 9876543210,
                 'This is a long string that goes on and on']]


    def func2():
        total = 324942324324 + 32434234234234 - (23423234243 / 324342342. +
                                                 32423 / 123.)


    def func22():
        return ('foo' in {'foo': 2}) in {True: True}


    class UselessClass(object):
        def __init__(self, bar):
            # Comments should have a space after the hash.
            if bar:
                bar += 1
                bar = bar * bar
                return bar
            else:
                indentation_in_strings_should_not_be_touched = """
    		           hello
    world
    """
                raise ValueError(indentation_in_strings_should_not_be_touched)

        def my_method(self):
            print(self)


Options::

    Usage: autopep8 [options] [filename [filename ...]]

    Automatically formats Python code to conform to the PEP 8 style guide.

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
      --list-fixes          list codes for fixes; used by --ignore and --select
      --ignore=IGNORE       do not fix these errors/warnings (e.g. E4,W)
      --select=SELECT       fix only these errors/warnings (e.g. E4,W)
      --max-line-length=MAX_LINE_LENGTH
                            set maximum allowed line length (default: 79)
      --aggressive          enable possibly unsafe changes (E711, E712)


Features
--------
autopep8 fixes the following issues_ reported by pep8_::

    E101 - Reindent all lines.
    E111 - Reindent all lines.
    E121 - Fix indentation to be a multiple of four.
    E122 - Add absent indentation for hanging indentation.
    E123 - Align closing bracket to match opening bracket.
    E124 - Align closing bracket to match visual indentation.
    E125 - Indent to distinguish line from next logical line.
    E126 - Fix over-indented hanging indentation.
    E127 - Fix visual indentation.
    E128 - Fix visual indentation.
    E20  - Remove extraneous whitespace.
    E211 - Remove extraneous whitespace.
    E22  - Fix extraneous whitespace around keywords.
    E231 - Add missing whitespace.
    E241 - Fix extraneous whitespace around keywords.
    E242 - Remove extraneous whitespace around operator.
    E251 - Remove whitespace around parameter '=' sign.
    E26  - Fix spacing after comment hash.
    E27  - Fix extraneous whitespace around keywords.
    E301 - Add missing blank line.
    E302 - Add missing 2 blank lines.
    E303 - Remove extra blank lines.
    E304 - Remove blank line following function decorator.
    E401 - Put imports on separate lines.
    E501 - Try to make lines fit within --max-line-length characters.
    E502 - Remove extraneous escape of newline.
    E701 - Put colon-separated compound statement on separate lines.
    E702 - Put semicolon-separated compound statement on separate lines.
    E711 - Fix comparison with None.
    E712 - Fix comparison with boolean.
    E721 - Switch to use isinstance().
    W191 - Reindent all lines.
    W291 - Remove trailing whitespace.
    W293 - Remove trailing whitespace on blank line.
    W391 - Remove trailing blank lines.
    W601 - Replace the {}.has_key() form with 'in'.
    W602 - Fix deprecated form of raising exception.
    W603 - Replace <> with !=.
    W604 - Replace backticks with repr().

autopep8 also fixes some issues not found by pep8_.

- Format block comments. (This is triggered if ``E26`` is enabled.)
- Correct some non-idiomatic Python code (via ``2to3 -f idioms``). (This is
  triggered if ``E712`` is enabled.)
- Normalize files with mixed line endings.


More advanced usage
-------------------
To enable only a subset of the fixes, use the ``--select`` option. For example,
to fix various types of indentation issues::

    $ autopep8 --select=E1,W1 <filename>

If the file being fixed is large, you may want to enable verbose progress
messages::

    $ autopep8 -v <filename>

Large files may also take many more iterations to completely fix. Thus, you may
need to increase the maximum number of passes::

    $ autopep8 -p 1000 <filename>

By default autopep8 makes only safe changes. Thus, by default, it does not fix
``E711`` and ``E712``. (Changing ``x == None`` to ``x is None`` may change the
meaning of the program if ``x`` has its ``__eq__`` method overridden.) To
enable these sort of aggressive fixes, use the ``--aggressive`` option::

    $ autopep8 --aggressive <filename>


Testing
-------
Test cases are in ``test/test_autopep8.py``. They can be run directly via
``python test/test_autopep8.py`` or via tox_. The latter is useful for
testing against multiple Python interpreters. (We currently test against
CPython versions 2.6, 2.7, 3.2, and 3.3. We also test against PyPy.)

.. _`tox`: http://pypi.python.org/pypi/tox

Broad spectrum testing is available via ``test/acid.py``. This script runs
autopep8 against Python code and checks for correctness and completeness of the
code fixes. It can check that the bytecode remains identical.
``test/acid_pypi.py`` makes use of ``acid.py`` to test against the latest
released packages on PyPi. In a similar fashion, ``test/acid_github.py`` tests
against Python code in Github repositories.


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

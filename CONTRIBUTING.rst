============
Contributing
============

Contributions are appreciated.


Issues
======

When submitting a bug report, please provide the following:

1. Does the ``pycodestyle`` tool behave correctly? If not, then the bug
   report should be filed at the pycodestyle_ repository instead.
2. ``autopep8 --version``
3. ``pycodestyle --version``
4. ``python --version``
5. ``uname -a`` if on Unix.
6. The example input that causes the bug.
7. The ``autopep8`` command-line options used to cause the bug.
8. The expected output.
9. Does the bug happen with the latest version of autopep8? To upgrade::

    $ pip install --upgrade git+https://github.com/hhatto/autopep8


Pull requests
=============

When submitting a pull request, please do the following.

1. Does the ``pycodestyle`` tool behave correctly? If not, then a pull request
   should be filed at the pycodestyle_ repository instead.
2. Add a test case to ``test/test_autopep8.py`` that demonstrates what your
   change does.
3. Make sure all tests pass.

.. _pycodestyle: https://github.com/PyCQA/pycodestyle

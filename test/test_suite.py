#!/usr/bin/env python

"""Run autopep8 against test file and check against expected output."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys

import autopep8


def check(expected_filename, input_filename):
    """Test and compare output.

    Return True on success.

    """
    got = autopep8.fix_file(
        input_filename,
        options=autopep8.parse_args(['', '--aggressive'])[0])

    try:
        with autopep8.open_with_encoding(expected_filename) as expected_file:
            expected = expected_file.read()
    except IOError:
        expected = None

    if expected == got:
        return True
    else:
        got_filename = expected_filename + '.err'
        encoding = autopep8.detect_encoding(input_filename)

        with autopep8.open_with_encoding(got_filename,
                                         encoding=encoding,
                                         mode='w') as got_file:
            got_file.write(got)

        print('{} does not match expected {}'.format(got_filename,
                                                     expected_filename),
              file=sys.stderr)
        return False


def run(filename):
    """Test against a specific file.

    Return True on success.
    
    Expected output should have the same base filename, but live in an "out"
    directory:

        foo/bar.py
        foo/out/bar.py

    Failed output will go to:

        foo/out/bar.py.err

    """
    return check(
        expected_filename=os.path.join(
            os.path.dirname(filename),
            'out',
            os.path.basename(filename)
        ),
        input_filename=filename
    )


def suite():
    result = True
    path = os.path.join(os.path.dirname(__file__), 'suite')
    for filename in os.listdir(path):
        filename = os.path.join(path, filename)

        print(filename, file=sys.stderr)

        if filename.endswith('.py'):
            result = run(filename) and result

    return result


def main():
    return int(not suite())


if __name__ == '__main__':
    sys.exit(main())

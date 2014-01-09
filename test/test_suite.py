#!/usr/bin/env python

"""Run autopep8 against test file and check against expected output."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import sys

ROOT_DIR = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

sys.path.insert(0, ROOT_DIR)
import autopep8


if sys.stdout.isatty():
    GREEN = '\x1b[32m'
    RED = '\x1b[31m'
    END = '\x1b[0m'
else:
    GREEN = ''
    RED = ''
    END = ''


def check(expected_filename, input_filename, aggressive):
    """Test and compare output.

    Return True on success.

    """
    got = autopep8.fix_file(
        input_filename,
        options=autopep8.parse_args([''] + aggressive * ['--aggressive']))

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

        print(
            '{begin}{got} does not match expected {expected}{end}'.format(
                begin=RED,
                got=got_filename,
                expected=expected_filename,
                end=END),
            file=sys.stdout)

        return False


def run(filename, aggressive):
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
        input_filename=filename,
        aggressive=aggressive
    )


def suite(aggressive):
    """Run against pep8 test suite."""
    result = True
    path = os.path.join(os.path.dirname(__file__), 'suite')
    for filename in os.listdir(path):
        filename = os.path.join(path, filename)

        if filename.endswith('.py'):
            print(filename, file=sys.stderr)
            result = run(filename, aggressive=aggressive) and result

    if result:
        print(GREEN + 'Okay' + END)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aggression-level', default=2, type=int,
                        help='run autopep8 in aggression level')
    args = parser.parse_args()

    return int(not suite(aggressive=args.aggression_level))


if __name__ == '__main__':
    sys.exit(main())

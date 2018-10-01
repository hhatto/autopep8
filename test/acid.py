#!/usr/bin/env python
"""Test that autopep8 runs without crashing on various Python files."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import random
import shlex
import sys
import subprocess
import tempfile


try:
    basestring
except NameError:
    basestring = str


ROOT_PATH = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

# Override system-installed version of autopep8.
sys.path = [ROOT_PATH] + sys.path
import autopep8


if sys.stdout.isatty():
    YELLOW = '\x1b[33m'
    END = '\x1b[0m'
else:
    YELLOW = ''
    END = ''


RANDOM_MAX = 1000


def colored(text, color):
    """Return color coded text."""
    return color + text + END


def run(filename, command, max_line_length=79,
        ignore='', check_ignore='', verbose=False,
        comparison_function=None,
        aggressive=0, experimental=False, line_range=None, random_range=False,
        pycodestyle=True):
    """Run autopep8 on file at filename.

    Return True on success.

    """
    if random_range:
        if not line_range:
            line_range = [1, RANDOM_MAX]
        first = random.randint(*line_range)
        line_range = [first, random.randint(first, line_range[1])]

    command = (shlex.split(command) + (['--verbose'] if verbose else []) +
               ['--max-line-length={}'.format(max_line_length),
                '--ignore=' + ignore, filename] +
               aggressive * ['--aggressive'] +
               (['--experimental'] if experimental else []) +
               (['--line-range', str(line_range[0]), str(line_range[1])]
                if line_range else []))

    print(' '.join(command), file=sys.stderr)

    with tempfile.NamedTemporaryFile(suffix='.py') as tmp_file:
        if subprocess.call(command, stdout=tmp_file) != 0:
            sys.stderr.write('autopep8 crashed on ' + filename + '\n')
            return False

        if pycodestyle and subprocess.call(
            [pycodestyle,
             '--ignore=' + ','.join([x for x in ignore.split(',') +
                                     check_ignore.split(',') if x]),
             '--show-source', tmp_file.name],
                stdout=sys.stdout) != 0:
            sys.stderr.write('autopep8 did not completely fix ' +
                             filename + '\n')

        try:
            if check_syntax(filename):
                try:
                    check_syntax(tmp_file.name, raise_error=True)
                except (SyntaxError, TypeError,
                        UnicodeDecodeError) as exception:
                    sys.stderr.write('autopep8 broke ' + filename + '\n' +
                                     str(exception) + '\n')
                    return False

                if comparison_function:
                    if not comparison_function(filename, tmp_file.name):
                        return False
        except IOError as exception:
            sys.stderr.write(str(exception) + '\n')

    return True


def check_syntax(filename, raise_error=False):
    """Return True if syntax is okay."""
    with autopep8.open_with_encoding(filename) as input_file:
        try:
            compile(input_file.read(), '<string>', 'exec', dont_inherit=True)
            return True
        except (SyntaxError, TypeError, UnicodeDecodeError):
            if raise_error:
                raise
            else:
                return False


def process_args():
    """Return processed arguments (options and positional arguments)."""
    compare_bytecode_ignore = 'E71,E721,W'

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--command',
        default='{} {}'.format(sys.executable,
                               os.path.join(ROOT_PATH, 'autopep8.py')),
        help='autopep8 command (default: %(default)s)')
    parser.add_argument('--ignore',
                        help='comma-separated errors to ignore',
                        default='')
    parser.add_argument('--check-ignore',
                        help='comma-separated errors to ignore when checking '
                        'for completeness (default: %(default)s)',
                        default='')
    parser.add_argument('--max-line-length', metavar='n', default=79, type=int,
                        help='set maximum allowed line length '
                        '(default: %(default)s)')
    parser.add_argument('--compare-bytecode', action='store_true',
                        help='compare bytecode before and after fixes; '
                        'sets default --ignore=' + compare_bytecode_ignore)
    parser.add_argument('-a', '--aggressive', action='count', default=0,
                        help='run autopep8 in aggressive mode')
    parser.add_argument('--experimental', action='store_true',
                        help='run experimental fixes')
    parser.add_argument('--line-range', metavar='line',
                        default=None, type=int, nargs=2,
                        help='pass --line-range to autope8')
    parser.add_argument('--random-range', action='store_true',
                        help='pass random --line-range to autope8')
    parser.add_argument('--pycodestyle', default='pycodestyle',
                        help='location of pycodestyle; '
                             'set to empty string to disable this check')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print verbose messages')
    parser.add_argument('paths', nargs='*',
                        help='paths to use for testing')

    args = parser.parse_args()

    if args.compare_bytecode and not args.ignore:
        args.ignore = compare_bytecode_ignore

    return args


def compare_bytecode(filename_a, filename_b):
    try:
        import pydiff
    except ImportError:
        raise SystemExit('pydiff required for bytecode comparison; '
                         'run "pip install pydiff"')

    diff = pydiff.diff_bytecode_of_files(filename_a, filename_b)

    if diff:
        sys.stderr.write('New bytecode does not match original:\n' +
                         diff + '\n')
    return not diff


def check(paths, args):
    """Run recursively run autopep8 on directory of files.

    Return False if the fix results in broken syntax.

    """
    if paths:
        dir_paths = paths
    else:
        dir_paths = [path for path in sys.path
                     if os.path.isdir(path)]

    filenames = dir_paths
    completed_filenames = set()

    if args.compare_bytecode:
        comparison_function = compare_bytecode
    else:
        comparison_function = None

    while filenames:
        try:
            name = os.path.realpath(filenames.pop(0))
            if not os.path.exists(name):
                # Invalid symlink.
                continue

            if name in completed_filenames:
                sys.stderr.write(
                    colored(
                        '--->  Skipping previously tested ' + name + '\n',
                        YELLOW))
                continue
            else:
                completed_filenames.update(name)
            if os.path.isdir(name):
                for root, directories, children in os.walk(name):
                    filenames += [os.path.join(root, f) for f in children
                                  if f.endswith('.py') and
                                  not f.startswith('.')]

                    directories[:] = [d for d in directories
                                      if not d.startswith('.')]
            else:
                verbose_message = '--->  Testing with ' + name
                sys.stderr.write(colored(verbose_message + '\n', YELLOW))

                if not run(os.path.join(name),
                           command=args.command,
                           max_line_length=args.max_line_length,
                           ignore=args.ignore,
                           check_ignore=args.check_ignore,
                           verbose=args.verbose,
                           comparison_function=comparison_function,
                           aggressive=args.aggressive,
                           experimental=args.experimental,
                           line_range=args.line_range,
                           random_range=args.random_range,
                           pycodestyle=args.pycodestyle):
                    return False
        except (UnicodeDecodeError, UnicodeEncodeError) as exception:
            # Ignore annoying codec problems on Python 2.
            print(exception)
            continue

    return True


def main():
    """Run main."""
    args = process_args()
    return 0 if check(args.paths, args) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

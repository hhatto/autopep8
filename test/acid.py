#!/usr/bin/env python
"""Test that autopep8 runs without crashing on various Python files."""

from __future__ import print_function

import contextlib
import os
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


def colored(text, color):
    """Return color coded text."""
    return color + text + END


def run(filename, command, max_line_length=79,
        ignore='', check_ignore='', verbose=False,
        comparison_function=None,
        aggressive=0):
    """Run autopep8 on file at filename.

    Return True on success.

    """
    command = (shlex.split(command) + (['--verbose'] if verbose else []) +
               ['--max-line-length={0}'.format(max_line_length),
                '--ignore=' + ignore, filename] +
               aggressive * ['--aggressive'])

    with tempfile.NamedTemporaryFile(suffix='.py') as tmp_file:
        if 0 != subprocess.call(command, stdout=tmp_file):
            sys.stderr.write('autopep8 crashed on ' + filename + '\n')
            return False

        if 0 != subprocess.call(
            ['pep8',
             '--ignore=' + ','.join([x for x in ignore.split(',') +
                                     check_ignore.split(',') if x]),
             '--show-source', tmp_file.name],
                stdout=sys.stdout):
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

    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--command',
                      default=os.path.join(ROOT_PATH, 'autopep8.py'),
                      help='autopep8 command (default: %default)')
    parser.add_option('--ignore',
                      help='comma-separated errors to ignore',
                      default='')
    parser.add_option('--check-ignore',
                      help='comma-separated errors to ignore when checking '
                           'for completeness (default: %default)',
                      default='')
    parser.add_option('--max-line-length', metavar='n', default=79, type=int,
                      help='set maximum allowed line length '
                           '(default: %default)')
    parser.add_option('--compare-bytecode', action='store_true',
                      help='compare bytecode before and after fixes; '
                           'sets default --ignore=' + compare_bytecode_ignore)
    parser.add_option('-a', '--aggressive', action='count', default=0,
                      help='run autopep8 in aggressive mode')

    parser.add_option(
        '--timeout',
        help='stop testing additional files after this amount of time '
             '(default: %default)',
        default=-1,
        type=float)

    parser.add_option('-v', '--verbose', action='store_true',
                      help='print verbose messages')

    (opts, args) = parser.parse_args()

    if opts.compare_bytecode and not opts.ignore:
        opts.ignore = compare_bytecode_ignore

    return (opts, args)


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


def check(opts, args):
    """Run recursively run autopep8 on directory of files.

    Return False if the fix results in broken syntax.

    """
    if args:
        dir_paths = args
    else:
        dir_paths = [path for path in sys.path
                     if os.path.isdir(path)]

    filenames = dir_paths
    completed_filenames = set()

    if opts.compare_bytecode:
        comparison_function = compare_bytecode
    else:
        comparison_function = None

    with timeout(opts.timeout):
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
                               command=opts.command,
                               max_line_length=opts.max_line_length,
                               ignore=opts.ignore,
                               check_ignore=opts.check_ignore,
                               verbose=opts.verbose,
                               comparison_function=comparison_function,
                               aggressive=opts.aggressive):
                        return False
            except (UnicodeDecodeError, UnicodeEncodeError) as exception:
                # Ignore annoying codec problems on Python 2.
                print(exception)
                continue

    return True


@contextlib.contextmanager
def timeout(seconds):
    if seconds > 0:
        try:
            import signal
            signal.signal(signal.SIGALRM, _timeout)
            signal.alarm(int(seconds))
            yield
        finally:
            signal.alarm(0)
    else:
        yield


class TimeoutException(Exception):

    """Timeout exception."""


def _timeout(_, __):
    raise TimeoutException()


def main():
    """Run main."""
    return 0 if check(*process_args()) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except TimeoutException:
        sys.stderr.write('Timed out\n')
    except KeyboardInterrupt:
        sys.exit(1)

#!/usr/bin/env python
"""Test that autopep8 runs without crashing on various Python files."""

import difflib
import os
import pprint
import shlex
import sys
import subprocess
import tempfile
import types


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


def run(filename, command, fast_check=False, passes=2000, max_line_length=79,
        ignore='', check_ignore='', verbose=False,
        comparison_function=None,
        aggressive=False):
    """Run autopep8 on file at filename.

    Return True on success.

    """
    command = (shlex.split(command) + (['--verbose'] if verbose else []) +
               ['--pep8-passes={0}'.format(passes),
                '--max-line-length={0}'.format(max_line_length),
                '--ignore=' + ignore, filename] +
               (['--aggressive'] if aggressive else []))

    if fast_check:
        if 0 != subprocess.call(command + ['--diff']):
            sys.stderr.write('autopep8 crashed on ' + filename + '\n')
            return False
    else:
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
            compile(input_file.read(), '<string>', 'exec')
            return True
        except (SyntaxError, TypeError, UnicodeDecodeError):
            if raise_error:
                raise
            else:
                return False


def compare_bytecode(old_filename, new_filename):
    """Return True if bytecode of the two files are equivalent."""
    before_bytecode = disassemble(old_filename)
    after_bytecode = disassemble(new_filename)

    if before_bytecode != after_bytecode:
        sys.stderr.write(
            'New bytecode does not match original ' +
            old_filename + '\n' +
            ''.join(difflib.unified_diff(
                pprint.pformat(before_bytecode).splitlines(True),
                pprint.pformat(after_bytecode).splitlines(True))) + '\n')
        return False
    return True


def disassemble(filename):
    """Return dictionary of disassembly."""
    with autopep8.open_with_encoding(filename) as f:
        return tree(compile(f.read(), '<string>', 'exec'))


def is_bytecode_string(text):
    """Return True if this is a bytecode string."""
    assert text.startswith('(')
    text = text[1:]
    for prefix in ['ur', 'br', 'u', 'b', 'r']:  # Longer one first.
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    for symbol in ['"', "'"]:
        if text.startswith(symbol):
            return True
    return False


def tree(code):
    """Return dictionary representation of the code object."""
    dictionary = {'co_consts': []}
    for name in dir(code):
        if name.startswith('co_') and name not in ['co_code',
                                                   'co_consts',
                                                   'co_lnotab',
                                                   'co_filename',
                                                   'co_firstlineno']:
            dictionary[name] = getattr(code, name)

    for index, _object in enumerate(code.co_consts):
        if isinstance(_object, types.CodeType):
            _object = tree(_object)

        # Filter out indentation in docstrings.
        if index == 0 and isinstance(_object, basestring):
            _object = '\n'.join(
                [line.lstrip() for line in _object.splitlines()])

        dictionary['co_consts'].append(_object)

    return dictionary


def process_args():
    """Return processed arguments (options and positional arguments)."""
    compare_bytecode_ignore = 'E71,E721,W'

    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--command',
                      default=os.path.join(ROOT_PATH, 'autopep8.py'),
                      help='autopep8 command (default: %default)')
    parser.add_option('--fast-check', action='store_true',
                      help='ignore incomplete PEP8 fixes and broken files')
    parser.add_option('--ignore',
                      help='comma-separated errors to ignore',
                      default='')
    parser.add_option('--check-ignore',
                      help='comma-separated errors to ignore when checking '
                           'for completeness (default: %default)',
                      default='')
    parser.add_option('-p', '--pep8-passes',
                      help='maximum number of additional pep8 passes'
                           ' (default: %default)',
                      default=2000)
    parser.add_option('--max-line-length', metavar='n', default=79, type=int,
                      help='set maximum allowed line length '
                           '(default: %default)')
    parser.add_option('--compare-bytecode', action='store_true',
                      help='compare bytecode before and after fixes; '
                           'sets default --ignore=' + compare_bytecode_ignore)
    parser.add_option('--aggressive', action='store_true',
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


class TimeoutException(Exception):

    """Timeout exception."""


def timeout(_, __):
    raise TimeoutException()


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

    try:
        import signal
        if opts.timeout > 0:
            signal.signal(signal.SIGALRM, timeout)
            signal.alarm(int(opts.timeout))

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
                               fast_check=opts.fast_check,
                               passes=opts.pep8_passes,
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
    except TimeoutException:
        sys.stderr.write('Timed out\n')
    finally:
        if opts.timeout > 0:
            signal.alarm(0)

    return True


def main():
    """Run main."""
    return 0 if check(*process_args()) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

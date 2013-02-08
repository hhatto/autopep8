#!/usr/bin/env python
"""Test that autopep8 runs without crashing on various Python files."""

import ast
import difflib
import dis
import os
import re
import sys
import subprocess
import tempfile

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


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


def run(filename, fast_check=False, passes=2000,
        ignore='', check_ignore='', verbose=False,
        comparison_function=None,
        aggressive=False):
    """Run autopep8 on file at filename.

    Return True on success.

    """
    autopep8_bin = os.path.join(ROOT_PATH, 'autopep8.py')
    command = ([autopep8_bin] + (['--verbose'] if verbose else []) +
               ['--pep8-passes={p}'.format(p=passes),
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


def compare_ast(old_filename, new_filename):
    """Return True if AST of the two files are equivalent."""
    return ast_dump(old_filename) == ast_dump(new_filename)


def ast_dump(filename):
    with autopep8.open_with_encoding(filename) as f:
        return ast.dump(ast.parse(f.read(), '<string>', 'exec'))


def compare_bytecode(old_filename, new_filename):
    """Return True if bytecode of the two files are equivalent."""
    before_bytecode = disassemble(old_filename)
    after_bytecode = disassemble(new_filename)
    if before_bytecode != after_bytecode:
        sys.stderr.write(
            'New bytecode does not match original ' +
            old_filename + '\n' +
            ''.join(difflib.unified_diff(
                before_bytecode.splitlines(True),
                after_bytecode.splitlines(True))) + '\n')
        return False
    return True


def disassemble(filename):
    """dis, but without line numbers."""
    with autopep8.open_with_encoding(filename) as f:
        code = compile(f.read(), '<string>', 'exec')

    return filter_disassembly('\n'.join(_disassemble(code)))


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


def filter_disassembly(text):
    """Filter out innocuous differences."""
    # Ignore formatting of docstrings. We modify docstrings for indentation and
    # trailing whitespace.
    lines = text.splitlines()
    for index, current_line in enumerate(lines):
        tokens = current_line.split()
        if len(tokens) <= 3:
            continue

        if tokens[1] == 'STORE_NAME' and tokens[3] == '(__doc__)':
            fixed = re.sub(r'\s', '', lines[index - 1])
            lines[index - 1] = fixed.replace(
                r'\n', '').replace(r'\r', '').replace(r'\t', '')

        if tokens[1] == 'LOAD_CONST' and is_bytecode_string(tokens[3]):
            # We do this for LOAD_CONST too due to false positives on Travis
            # CI. It somehow isn't enough to just remove the trailing
            # whitespace.
            fixed = re.sub(r'\s', '', lines[index])
            lines[index] = fixed.replace(
                r'\n', '').replace(r'\r', '').replace(r'\t', '')

        # BUILD_TUPLE and LOAD_CONST are sometimes used interchangeably.
        if tokens[1] == 'LOAD_CONST' and tokens[3] == '(())':
            lines[index] = lines[index].replace(
                'LOAD_CONST               8 (())',
                'BUILD_TUPLE              0')

        # LOAD_NAME and LOAD_CONST are sometimes used interchangeably.
        if tokens[1] == 'LOAD_NAME':
            if tokens[3] == '(False)':
                lines[index] = lines[index].replace(
                    'LOAD_NAME               21 (False)',
                    'LOAD_CONST              12 (False)')
            elif tokens[3] == '(None)':
                # TODO: Strip number and just leave human-readable name?
                lines[index] = lines[index].replace(
                    'LOAD_NAME               14 (None)',
                    'LOAD_CONST               5 (None)')
                lines[index] = lines[index].replace(
                    'LOAD_NAME               17 (None)',
                    'LOAD_CONST               2 (None)')

    return '\n'.join(lines)


def _disassemble(code):
    """Disassemble a code object."""
    sio = StringIO()

    findlinestarts = dis.findlinestarts
    dis.findlinestarts = lambda _: {}

    findlabels = dis.findlabels
    dis.findlabels = lambda _: {}

    sys.stdout, sio = sio, sys.stdout

    try:
        dis.dis(code)
    finally:
        sys.stdout, sio = sio, sys.stdout
        dis.findlinestarts = findlinestarts
        dis.findlabels = findlabels

    disassembled_code = [
        re.sub('<code object .* line [0-9]+>',
               '<code object>', sio.getvalue())]

    for c in code.co_consts:
        if hasattr(c, 'co_code'):
            disassembled_code += _disassemble(c)

    return disassembled_code


def process_args():
    """Return processed arguments (options and positional arguments)."""
    compare_bytecode_ignore = 'E71,E721,W601,W602,W604'

    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--fast-check', action='store_true',
                      help='ignore incomplete PEP8 fixes and broken files')
    parser.add_option('--ignore',
                      help='comma-separated errors to ignore',
                      default='')
    parser.add_option('--check-ignore',
                      help='comma-separated errors to ignore when checking '
                           'for completeness (default: %default)',
                      default='E501')
    parser.add_option('-p', '--pep8-passes',
                      help='maximum number of additional pep8 passes'
                           ' (default: %default)',
                      default=2000)
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
        comparison_function = lambda x, y: (compare_ast(x, y) or
                                            compare_bytecode(x, y))
    else:
        comparison_function = None

    try:
        import signal
        if opts.timeout > 0:
            signal.signal(signal.SIGALRM, timeout)
            signal.alarm(int(opts.timeout))

        while filenames:
            name = os.path.realpath(filenames.pop(0))
            if not os.path.exists(name):
                # Invalid symlink.
                continue

            if name in completed_filenames:
                sys.stderr.write(
                    colored('--->  Skipping previously tested ' + name + '\n',
                            YELLOW))
                continue
            else:
                completed_filenames.update(name)

            try:
                is_directory = os.path.isdir(name)
            except UnicodeEncodeError:
                continue

            if is_directory:
                for root, directories, children in os.walk(name):
                    filenames += [os.path.join(root, f) for f in children
                                  if f.endswith('.py') and
                                  not f.startswith('.')]
                    for d in directories:
                        if d.startswith('.'):
                            directories.remove(d)
            else:
                verbose_message = '--->  Testing with '
                try:
                    verbose_message += name
                except UnicodeEncodeError:
                    verbose_message += '...'
                sys.stderr.write(colored(verbose_message + '\n', YELLOW))

                if not run(os.path.join(name),
                           fast_check=opts.fast_check,
                           passes=opts.pep8_passes,
                           ignore=opts.ignore,
                           check_ignore=opts.check_ignore,
                           verbose=opts.verbose,
                           comparison_function=comparison_function,
                           aggressive=opts.aggressive):
                    return False
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

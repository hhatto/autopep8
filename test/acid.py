#!/usr/bin/env python
"""Test that autopep8 runs without crashing on various Python files."""

import os
import sys
import subprocess
import tempfile
import tokenize


def run(filename, fast_check=False, passes=2000,
        ignore=''):
    """Run autopep8 on file at filename.
    Return True on success.
    """
    ignore_option = '--ignore=' + ignore

    autopep8_path = os.path.split(os.path.abspath(
        os.path.dirname(__file__)))[0]
    autoppe8_bin = os.path.join(autopep8_path, 'autopep8.py')
    command = [autoppe8_bin, '--pep8-passes={p}'.format(p=passes),
               ignore_option, filename]

    if fast_check:
        if 0 != subprocess.call(command + ['--diff']):
            sys.stderr.write('autopep8 crashed on ' + filename + '\n')
            return False
    else:
        with tempfile.NamedTemporaryFile(suffix='.py') as tmp_file:
            if 0 != subprocess.call(command, stdout=tmp_file):
                sys.stderr.write('autopep8 crashed on ' + filename + '\n')
                return False

            if 0 != subprocess.call(['pep8', ignore_option,
                                     '--show-source', tmp_file.name],
                                    stderr=tmp_file):
                sys.stderr.write('autopep8 did not completely fix ' +
                                 filename + '\n')

            try:
                if _check_syntax(filename):
                    try:
                        _check_syntax(tmp_file.name, raise_error=True)
                    except (SyntaxError, TypeError,
                            UnicodeDecodeError) as exception:
                        sys.stderr.write('autopep8 broke ' + filename + '\n' +
                                         str(exception) + '\n')
                        return False
            except IOError as exception:
                sys.stderr.write(str(exception) + '\n')

    return True


def _detect_encoding(filename):
    """Return file encoding."""
    try:
        # Python 3
        try:
            with open(filename, 'rb') as input_file:
                encoding = tokenize.detect_encoding(input_file.readline)[0]

                # Check for correctness of encoding
                import io
                with io.TextIOWrapper(input_file, encoding) as wrapper:
                    wrapper.read()

            return encoding
        except (SyntaxError, LookupError, UnicodeDecodeError):
            return 'latin-1'
    except AttributeError:
        return 'utf-8'


def _open_with_encoding(filename, encoding, mode='r'):
    """Open file with a specific encoding."""
    try:
        # Python 3
        return open(filename, mode=mode, encoding=encoding)
    except TypeError:
        return open(filename, mode=mode)


def _check_syntax(filename, raise_error=False):
    """Return True if syntax is okay."""
    with _open_with_encoding(
            filename, _detect_encoding(filename)) as input_file:
        try:
            compile(input_file.read(), '<string>', 'exec')
            return True
        except (SyntaxError, TypeError, UnicodeDecodeError):
            if raise_error:
                raise
            else:
                return False


def process_args():
    """Return processed arguments (options and positional arguments)."""
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--fast-check', action='store_true',
                      help='ignore incomplete PEP8 fixes and broken files')
    parser.add_option('--ignore',
                      help='comma-separated errors to ignore',
                      default='')
    parser.add_option('-p', '--pep8-passes',
                      help='maximum number of additional pep8 passes'
                           ' (default: %default)',
                      default=2000)
    parser.add_option(
        '--timeout',
        help='stop testing additional files after this amount of time '
             '(default: %default)',
        default=-1,
        type=float)
    return parser.parse_args()


def check(opts, args):
    """Run recursively run autopep8 on directory of files.

    Return False if the fix results in broken syntax.

    """
    if args:
        dir_paths = args
    else:
        dir_paths = sys.path

    filenames = dir_paths
    completed_filenames = set()

    import time
    start_time = time.time()

    while filenames:
        if opts.timeout > 0 and time.time() - start_time > opts.timeout:
            break

        name = os.path.realpath(filenames.pop(0))
        if name in completed_filenames:
            sys.stderr.write('--->  Skipping previously tested ' + name + '\n')
            continue
        else:
            completed_filenames.update(name)

        if os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                for d in directories:
                    if d.startswith('.'):
                        directories.remove(d)
        else:
            sys.stderr.write('--->  Testing with ')
            try:
                sys.stderr.write(name)
            except UnicodeEncodeError:
                sys.stderr.write('...')
            sys.stderr.write('\n')

            if not run(os.path.join(name),
                       fast_check=opts.fast_check,
                       ignore=opts.ignore,
                       passes=opts.pep8_passes):
                return False

    return True


def main():
    """Run main."""
    return 0 if check(*process_args()) else 1


if __name__ == '__main__':
    sys.exit(main())

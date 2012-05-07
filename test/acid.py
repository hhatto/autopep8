#!/usr/bin/env python
"""
Test that autopep8 runs without crashing on various Python files.
"""
import os
import sys
import subprocess
import tempfile


def run(filename, log_file, slow_check=False, passes=2000,
        ignore_list=['E501']):
    """Run autopep8 on file at filename.
    Return True on success.
    """
    ignore_option = '--ignore=' + ','.join(ignore_list)

    autopep8_path = os.path.split(os.path.abspath(
            os.path.dirname(__file__)))[0]
    autoppe8_bin = os.path.join(autopep8_path, 'autopep8.py')
    command = [autoppe8_bin, '--pep8-passes={p}'.format(p=passes),
               ignore_option, filename]

    if slow_check:
        with tempfile.NamedTemporaryFile(suffix='.py') as tmp_file:
            if 0 != subprocess.call(command, stdout=tmp_file, stderr=log_file):
                log_file.write('autopep8 crashed on ' + filename + '\n')
                return False

            if 0 != subprocess.call(['pep8', ignore_option,
                                     '--show-source', tmp_file.name],
                                    stderr=tmp_file):
                log_file.write('autopep8 did not completely fix ' +
                               filename + '\n')

            if _check_syntax(filename) and not _check_syntax(tmp_file.name):
                log_file.write('autopep8 broke ' + filename + '\n')
                return False
    else:
        if 0 != subprocess.call(command + ['--diff'], stderr=log_file):
            log_file.write('autopep8 crashed on ' + filename + '\n')
            return False

    return True


def _check_syntax(filename):
    """Return True if syntax is okay."""
    tmp_dir = tempfile.mkdtemp()
    import shutil
    try:
        tmp_filename = os.path.join(tmp_dir,
                                    os.path.basename(filename))
        shutil.copyfile(src=filename, dst=tmp_filename)
        # Doing this as a subprocess to avoid crashing
        import py_compile
        try:
            py_compile.compile(tmp_filename, doraise=True)
            return True
        except py_compile.PyCompileError:
            return False
    finally:
        shutil.rmtree(tmp_dir)


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--slow-check', action='store_true',
                      help='report incomplete PEP8 fixes and broken files')
    parser.add_option('--log-errors',
                      help='log autopep8 errors instead of exiting')
    opts, args = parser.parse_args()

    if opts.log_errors:
        log_file = open(opts.log_errors, 'w')
    else:
        log_file = sys.stderr

    if args:
        dir_paths = args
        for d in dir_paths:
            if not os.path.isdir(d):
                sys.stderr.write(d + ' is not a directory\n')
                sys.exit(1)
    else:
        dir_paths = sys.path

    try:
        for p in dir_paths:
            for root, dirnames, filenames in os.walk(p):
                import fnmatch
                for f in fnmatch.filter(filenames, '*.py'):
                    sys.stderr.write('--->  Testing with ' + f + '\n')

                    if not run(os.path.join(root, f),
                            log_file=log_file,
                            slow_check=opts.slow_check):
                        if not opts.log_errors:
                            sys.exit(1)
    finally:
        # Only close if it is an actual log file
        if opts.log_errors:
            log_file.close()


if __name__ == '__main__':
    main()

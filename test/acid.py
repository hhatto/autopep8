#!/usr/bin/env python
"""
Test that autopep8 runs without crashing on various Python files.
"""
import sys


def run(filename, log_file, report_incomplete_fix=False, passes=2000):
    """Run autopep8 on file at filename.
    Return True on success.
    """
    import os
    autopep8_path = os.path.split(os.path.abspath(
            os.path.dirname(__file__)))[0]
    autoppe8_bin = os.path.join(autopep8_path, 'autopep8.py')
    command = [autoppe8_bin, '--pep8-passes={p}'.format(p=passes),
               filename]

    import subprocess
    if report_incomplete_fix:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py') as f:
            if 0 != subprocess.call(command, stdout=f, stderr=log_file):
                log_file.write('autopep8 crashed on ' + filename + '\n')
                return False

            if 0 != subprocess.call(['pep8', '--ignore=E501',
                                     '--show-source', f.name],
                                    stderr=f):
                log_file.write('autopep8 did not completely fix ' +
                               filename + '\n')
    else:
        if 0 != subprocess.call(command + ['--diff'], stderr=log_file):
            log_file.write('autopep8 crashed on ' + filename + '\n')
            return False

    return True


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--report-incomplete-fix', action='store_true',
                      help='report incomplete PEP8 fixes')
    parser.add_option('--log-errors',
                      help='log autopep8 errors instead of exiting')
    opts, args = parser.parse_args()

    if opts.log_errors:
        log_file = open(opts.log_errors, 'w')
    else:
        log_file = sys.stderr

    try:
        import os
        for p in sys.path:
            for root, dirnames, filenames in os.walk(p):
                import fnmatch
                for f in fnmatch.filter(filenames, '*.py'):
                    sys.stderr.write('--->  Testing with ' + f + '\n')

                    if not run(os.path.join(root, f),
                               log_file=log_file,
                               report_incomplete_fix=
                                       opts.report_incomplete_fix):
                        if not opts.log_errors:
                            sys.exit(1)
    finally:
        log_file.close()


if __name__ == '__main__':
    main()

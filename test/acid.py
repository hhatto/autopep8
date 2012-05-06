#!/usr/bin/env python
"""
Test that autopep8 runs without crashing on various Python files.
"""
import sys


def run(filename, report_incomplete_fix=False):
    """Run autopep8 on file at filename.
    Return True on success.
    """
    import os
    autopep8_path = os.path.split(os.path.abspath(
            os.path.dirname(__file__)))[0]
    autoppe8_bin = os.path.join(autopep8_path, 'autopep8.py')

    import subprocess
    if report_incomplete_fix:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py') as f:
            if 0 != subprocess.call([autoppe8_bin, filename], stdout=f):
                sys.stderr.write('autopep8 crashed on ' + filename + '\n')
                return False

            if 0 != subprocess.call(['pep8', '--ignore=E501',
                                     '--show-source', f.name]):
                sys.stderr.write('autopep8 did not completely fix ' +
                                 filename + '\n')
    else:
        if 0 != subprocess.call([autoppe8_bin, '--diff', filename]):
            sys.stderr.write('autopep8 crashed on ' + filename + '\n')
            return False

    return True


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--report-incomplete-fix', action='store_true',
                      help='report incomplete PEP8 fixes')
    opts, args = parser.parse_args()

    import os
    for p in sys.path:
        for root, dirnames, filenames in os.walk(p):
            import fnmatch
            for f in fnmatch.filter(filenames, '*.py'):
                sys.stderr.write('--->  Testing with ' + f + '\n')

                if not run(os.path.join(root, f),
                           opts.report_incomplete_fix):
                    sys.exit(1)


if __name__ == '__main__':
    main()

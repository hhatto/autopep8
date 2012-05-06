#!/usr/bin/env python
"""
Test that autopep8 runs without crashing on various Python files.
"""

def run(filename):
    """Run autopep8 on file at filename.
    Return True on success.
    """
    import os
    autopep8_path = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

    import subprocess
    return 0 == subprocess.call([os.path.join(autopep8_path, 'autopep8.py'),
                                 '--diff', filename])


def main():
    import sys
    import os
    for p in sys.path:
        for root, dirnames, filenames in os.walk(p):
            import fnmatch
            for f in fnmatch.filter(filenames, '*.py'):
                full_filename = os.path.join(root, f)
                del f
                if not run(full_filename):
                    print('autopep8 crashed on "{filename}"'.format(
                            filename=full_filename))
                    sys.exit(1)


if __name__ == '__main__':
    main()

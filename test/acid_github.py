#!/usr/bin/env python
"""Run acid test against latest packages on Github."""

import os
import subprocess
import sys

import acid


TMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                       'github_tmp')


def latest_packages():
    """Return names of latest released packages on Github."""
    import requests

    for result in requests.get('https://github.com/timeline.json').json:
        try:
            repository = result['repository']
            size = repository['size']
            if 0 < size < 1000 and repository['language'] == 'Python':
                yield repository['url']
        except KeyError:
            continue


def download_package(name, output_directory):
    """Download package to output_directory.

    Raise CalledProcessError on failure.

    """
    original_path = os.getcwd()
    os.chdir(output_directory)
    try:
        subprocess.check_call(
            ['git', 'clone', name])
    finally:
        os.chdir(original_path)


def main():
    """Run main."""
    try:
        os.mkdir(TMP_DIR)
    except OSError:
        pass

    opts, args = acid.process_args()
    if args:
        # Copy
        names = list(args)
    else:
        names = None

    import time
    start_time = time.time()

    checked_packages = []
    skipped_packages = []
    while True:
        if opts.timeout > 0 and time.time() - start_time > opts.timeout:
            break

        if args:
            if not names:
                break
        else:
            while not names:
                # Continually populate if user did not specify a package
                # explicitly.
                names = [p for p in latest_packages()
                         if p not in checked_packages and
                         p not in skipped_packages]

                if not names:
                    import time
                    time.sleep(1)

        package_name = names.pop(0)
        print(package_name)

        user_tmp_dir = os.path.join(
            TMP_DIR,
            os.path.basename(os.path.split(package_name)[0]))
        try:
            os.mkdir(user_tmp_dir)
        except OSError:
            pass

        package_tmp_dir = os.path.join(
            user_tmp_dir,
            os.path.basename(package_name))
        try:
            os.mkdir(package_tmp_dir)
        except OSError:
            print('Skipping already checked package')
            skipped_packages.append(package_name)
            continue

        try:
            download_package(package_name, output_directory=package_tmp_dir)
        except subprocess.CalledProcessError:
            print('ERROR: git clone failed')
            continue

        if acid.check(opts, [package_tmp_dir]):
            checked_packages.append(package_name)
        else:
            return 1

    if checked_packages:
        print('\nTested packages:\n    ' + '\n    '.join(checked_packages))

if __name__ == '__main__':
    sys.exit(main())

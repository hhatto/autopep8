#!/usr/bin/env python
#
# Run acid test against latest packages on PyPi.

import os
import subprocess
import sys

import acid


# Check all packages released in the last $LAST_HOURS hours
LAST_HOURS=500

TMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                       'pypi_tmp')


def latest_packages():
    """Return names of latest released packages on PyPi."""
    process = subprocess.Popen(['yolk', '-L', str(LAST_HOURS)],
                               stdout=subprocess.PIPE)

    for line in process.communicate()[0].decode('utf-8').split('\n'):
        if line:
            yield line.split()[0]


def download_package(name, output_directory):
    """Download package to output_directory.

    Raise CalledProcessError on failure.

    """
    original_path = os.getcwd()
    os.chdir(output_directory)
    try:
        subprocess.check_call(
            ['yolk', '--fetch-package={name}'.format(name=name)])
    finally:
        os.chdir(original_path)


def extract_package(path, output_directory):
    """Extract package at path."""
    if path.lower().endswith('.tar.gz'):
        original_path = os.getcwd()
        os.chdir(output_directory)
        try:
            import tarfile
            tar = tarfile.open(path)
            tar.extractall()
            tar.close()
            return True
        finally:
            os.chdir(original_path)
    elif path.lower().endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(path) as archive:
            archive.extractall(path=output_directory)
        return True

    return False


def main():
    try:
        os.mkdir(TMP_DIR)
    except OSError:
        pass

    opts, names = acid.process_args()
    if not names:
        names = latest_packages()

    if opts.log_errors:
        log_file = open(opts.log_errors, 'w')
    else:
        log_file = sys.stderr

    for package_name in names:
        print(package_name)

        package_tmp_dir = os.path.join(TMP_DIR, package_name)
        try:
            os.mkdir(package_tmp_dir)
        except OSError:
            print('Skipping already checked package')
            continue

        try:
            download_package(package_name, output_directory=package_tmp_dir)
        except subprocess.CalledProcessError:
            print('ERROR: yolk fetch failed')
            continue

        for download_name in os.listdir(package_tmp_dir):
            if not extract_package(
                    os.path.join(package_tmp_dir, download_name),
                    output_directory=package_tmp_dir):
                print('ERROR: Could not extract package')
                continue

            if not acid.check(opts, [package_tmp_dir], log_file=log_file):
                sys.exit(1)


if __name__ == '__main__':
    main()

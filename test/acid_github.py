#!/usr/bin/env python
"""Run acid test against latest repositories on Github."""

import os
import re
import subprocess
import sys

import acid


TMP_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                       'github_tmp')


def latest_repositories():
    """Return names of latest released repositories on Github."""
    import requests

    try:
        for result in requests.get('https://github.com/timeline.json').json():
            try:
                repository = result['repository']
                size = repository['size']
                if 0 < size < 1000 and repository['language'] == 'Python':
                    yield repository['url']
            except KeyError:
                continue
    except (requests.exceptions.RequestException, ValueError):
        # Ignore GitHub server flakiness.
        pass


def download_repository(name, output_directory):
    """Download repository to output_directory.

    Raise CalledProcessError on failure.

    """
    subprocess.check_call(['git', 'clone', name],
                          cwd=output_directory)


def interesting(repository_path):
    """Return True if interesting."""
    print(repository_path)
    process = subprocess.Popen(['git', 'log'],
                               cwd=repository_path,
                               stdout=subprocess.PIPE)
    try:
        return len(re.findall(
            'pep8',
            process.communicate()[0].decode('utf-8'))) > 2
    except UnicodeDecodeError:
        return False


def complete(repository):
    """Fill in missing paths of URL."""
    if ':' in repository:
        return repository
    else:
        assert '/' in repository
        return 'https://github.com/' + repository.strip()


def main():
    """Run main."""
    try:
        os.mkdir(TMP_DIR)
    except OSError:
        pass

    args = acid.process_args()
    if args.paths:
        names = [complete(a) for a in args.paths]
    else:
        names = None

    checked_repositories = []
    skipped_repositories = []
    interesting_repositories = []
    while True:
        if args.paths:
            if not names:
                break
        else:
            while not names:
                # Continually populate if user did not specify a repository
                # explicitly.
                names = [p for p in latest_repositories()
                         if p not in checked_repositories and
                         p not in skipped_repositories]

                if not names:
                    import time
                    time.sleep(1)

        repository_name = names.pop(0)
        print(repository_name)

        user_tmp_dir = os.path.join(
            TMP_DIR,
            os.path.basename(os.path.split(repository_name)[0]))
        try:
            os.mkdir(user_tmp_dir)
        except OSError:
            pass

        repository_tmp_dir = os.path.join(
            user_tmp_dir,
            os.path.basename(repository_name))
        try:
            os.mkdir(repository_tmp_dir)
        except OSError:
            print('Skipping already checked repository')
            skipped_repositories.append(repository_name)
            continue

        try:
            download_repository(repository_name,
                                output_directory=repository_tmp_dir)
        except subprocess.CalledProcessError:
            print('ERROR: git clone failed')
            continue

        if acid.check([repository_tmp_dir], args):
            checked_repositories.append(repository_name)

            if interesting(
                os.path.join(repository_tmp_dir,
                             os.path.basename(repository_name))):
                interesting_repositories.append(repository_name)
        else:
            return 1

    if checked_repositories:
        print('\nTested repositories:')
        for name in checked_repositories:
            print('    ' + name +
                  (' *' if name in interesting_repositories else ''))

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

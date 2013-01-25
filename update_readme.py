#!/usr/bin/env python
"""Update example in readme."""

import autopep8


def split_readme(readme_path, before_key, after_key, end_key):
    """Return split readme."""
    with open(readme_path) as readme_file:
        readme = readme_file.read()

    top, rest = readme.split(before_key)
    before, rest = rest.split(after_key)
    _, bottom = rest.split(end_key)

    return (top.rstrip('\n'),
            before.strip('\n'),
            end_key + '\n\n' + bottom.lstrip('\n'))


def indent_line(line):
    """Indent non-empty lines."""
    if line:
        return 4 * ' ' + line
    else:
        return line


def indent(text):
    """Indent text by four spaces."""
    return '\n'.join([indent_line(line) for line in text.split('\n')])


def main():
    README_PATH = 'README.rst'
    BEFORE_KEY = 'Before running autopep8.\n\n.. code-block:: python'
    AFTER_KEY = 'After running autopep8.\n\n.. code-block:: python'

    (top, before, bottom) = split_readme(README_PATH,
                                         before_key=BEFORE_KEY,
                                         after_key=AFTER_KEY,
                                         end_key='Options::')

    import textwrap
    new_readme = '\n\n'.join([
        top,
        BEFORE_KEY, before,
        AFTER_KEY, indent(autopep8.fix_string(textwrap.dedent(before))),
        bottom])

    with open(README_PATH, 'w') as output_file:
        output_file.write(new_readme)


if __name__ == '__main__':
    main()

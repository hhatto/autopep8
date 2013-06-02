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
    readme_path = 'README.rst'
    before_key = 'Before running autopep8.\n\n.. code-block:: python'
    after_key = 'After running autopep8.\n\n.. code-block:: python'

    (top, before, bottom) = split_readme(readme_path,
                                         before_key=before_key,
                                         after_key=after_key,
                                         end_key='Options::')

    import textwrap
    new_readme = '\n\n'.join([
        top,
        before_key, before,
        after_key, indent(autopep8.fix_string(
            textwrap.dedent(before),
            options=autopep8.parse_args(['', '--aggressive'])[0])),
        bottom])

    with open(readme_path, 'w') as output_file:
        output_file.write(new_readme)


if __name__ == '__main__':
    main()

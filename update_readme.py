#!/usr/bin/env python

"""Update example in readme."""

import io
import os
import sys
import textwrap

import pyflakes.api
import pyflakes.messages
import pyflakes.reporter

import autopep8


def split_readme(readme_path, before_key, after_key, options_key, end_key):
    """Return split readme."""
    with open(readme_path) as readme_file:
        readme = readme_file.read()

    top, rest = readme.split(before_key)
    before, rest = rest.split(after_key)
    _, rest = rest.split(options_key)
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
    return '\n'.join(indent_line(line) for line in text.split('\n'))


def help_message():
    """Return help output."""
    parser = autopep8.create_parser()
    string_io = io.StringIO()
    parser.print_help(string_io)
    # Undo home directory expansion.
    return string_io.getvalue().replace(os.path.expanduser('~'), '~')


def check(source):
    """Check code."""
    compile(source, '<string>', 'exec', dont_inherit=True)
    reporter = pyflakes.reporter.Reporter(sys.stderr, sys.stderr)
    pyflakes.api.check(source, filename='<string>', reporter=reporter)


def main():
    readme_path = 'README.rst'
    before_key = 'Before running autopep8.\n\n.. code-block:: python'
    after_key = 'After running autopep8.\n\n.. code-block:: python'
    options_key = 'Options::'

    (top, before, bottom) = split_readme(readme_path,
                                         before_key=before_key,
                                         after_key=after_key,
                                         options_key=options_key,
                                         end_key='Features\n========')

    input_code = textwrap.dedent(before)

    output_code = autopep8.fix_code(
        input_code,
        options={'aggressive': 2})

    check(output_code)

    new_readme = '\n\n'.join([
        top,
        before_key, before,
        after_key, indent(output_code).rstrip(),
        options_key, indent(help_message()),
        bottom])

    with open(readme_path, 'w') as output_file:
        output_file.write(new_readme)


if __name__ == '__main__':
    main()

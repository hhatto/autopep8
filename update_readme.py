#!/usr/bin/env python
"""Update example in readme."""

try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO


def split_readme(readme_path, before_key, after_key, diff_key, end_key):
    """Return split readme."""
    with open(readme_path) as readme_file:
        readme = readme_file.read()

    top, rest = readme.split(before_key)
    before, rest = rest.split(after_key)
    _, rest = rest.split(diff_key)
    _, bottom = rest.split(end_key)

    return (top.rstrip('\n'),
            before.strip('\n'),
            end_key + '\n\n' + bottom.lstrip('\n'))


def run_autopep8(source, options=()):
    """Return source code formatted with autopep8."""
    import tempfile
    temp = tempfile.mkstemp(dir='.')
    with open(temp[1], 'w') as temp_file:
        temp_file.write(source)

    try:
        import autopep8
        opts, _ = autopep8.parse_args(list(options) + [temp[1]])
        sio = StringIO()
        autopep8.fix_file(filename=temp[1],
                          opts=opts,
                          output=sio)
        output = sio.getvalue()
        if source.strip() and not output.strip():
            raise ValueError('autopep8 failed')
        return output
    finally:
        import os
        os.remove(temp[1])


def indent_line(line):
    """Indent non-empty lines."""
    if line:
        return 4 * ' ' + line
    else:
        return line


def indent(text):
    """Indent text by four spaces."""
    return '\n'.join([indent_line(line) for line in text.split('\n')])


def clean_diff(diff_text):
    """Remove non-deterministic stuff from diff."""
    clean_lines = []
    for line in diff_text.split('\n'):
        if line.startswith('---') or line.startswith('+++'):
            clean_lines.append(line.split('/')[0])
        else:
            clean_lines.append(line)
    return '\n'.join(clean_lines)


def main():
    README_PATH = 'README.rst'
    BEFORE_KEY = 'before::'
    AFTER_KEY = 'after::'
    DIFF_KEY = 'diff::'

    (top, before, bottom) = split_readme(README_PATH,
                                         before_key=BEFORE_KEY,
                                         after_key=AFTER_KEY,
                                         diff_key=DIFF_KEY,
                                         end_key='options::')

    import textwrap
    new_readme = '\n\n'.join([
        top,
        BEFORE_KEY, before,
        AFTER_KEY, indent(run_autopep8(textwrap.dedent(before))),
        DIFF_KEY, indent(
            clean_diff(run_autopep8(textwrap.dedent(before),
                                    options=['--diff']))),
        bottom])

    with open(README_PATH, 'w') as output_file:
        output_file.write(new_readme)


if __name__ == '__main__':
    main()

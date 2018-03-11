"""Run autopep8 on the selected buffer in Vim.

map <C-I> :pyfile <path_to>/vim_autopep8.py<CR>

Replace ":pyfile" with ":py3file" if Vim is built with Python 3 support.

"""

from __future__ import unicode_literals

import sys

import vim


ENCODING = vim.eval('&fileencoding')


def encode(text):
    if sys.version_info.major >= 3:
        return text
    else:
        return text.encode(ENCODING)


def decode(text):
    if sys.version_info.major >= 3:
        return text
    else:
        return text.decode(ENCODING)


def main():
    if vim.eval('&syntax') != 'python':
        return

    source = '\n'.join(decode(line)
                        for line in vim.current.buffer) + '\n'

    import autopep8
    formatted = autopep8.fix_code(
        source,
        options={'line_range': [1 + vim.current.range.start,
                                1 + vim.current.range.end]})

    if source != formatted:
        if formatted.endswith('\n'):
            formatted = formatted[:-1]

        vim.current.buffer[:] = [encode(line)
                                 for line in formatted.splitlines()]


if __name__ == '__main__':
    main()

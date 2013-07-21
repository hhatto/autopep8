"""Run autopep8 on the selected buffer in Vim.

map <C-I> :pyf <path_to>/autopep8_vim.py<CR>

"""

import autopep8
import vim

# TODO: Find out how to get the actual encoding from Vim.
encoding = 'utf-8'
options = autopep8.parse_args(['--range',
                               str(vim.current.range.start),
                               str(vim.current.range.end),
                               ''])[0]

source = '\n'.join(vim.current.buffer).decode(encoding) + '\n'
formatted = autopep8.fix_string(source, options=options)

if source != formatted:
    vim.current.buffer[:] = [line.encode(encoding)
                             for line in formatted.splitlines()]

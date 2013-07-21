"""Run autopep8 on the selected buffer in Vim.

map <C-I> :pyf <path_to>/autopep8_vim.py<CR>

"""

import autopep8
import vim


encoding = vim.eval('&fileencoding')
options = autopep8.parse_args(['--range',
                               str(1 + vim.current.range.start),
                               str(1 + vim.current.range.end),
                               ''])[0]

source = '\n'.join(line.decode(encoding)
                   for line in vim.current.buffer) + '\n'

formatted = autopep8.fix_string(source, options=options)

if source != formatted:
    vim.current.buffer[:] = [line.encode(encoding)
                             for line in formatted.splitlines()]

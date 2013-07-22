"""Run autopep8 on the selected buffer in Vim.

map <C-I> :pyfile <path_to>/autopep8_vim.py<CR>

"""

import vim
if vim.eval('&syntax') == 'python':
    encoding = vim.eval('&fileencoding')
    source = '\n'.join(line.decode(encoding)
                       for line in vim.current.buffer) + '\n'

    import autopep8
    options = autopep8.parse_args(['--range',
                                   str(1 + vim.current.range.start),
                                   str(1 + vim.current.range.end),
                                   ''])[0]

    formatted = autopep8.fix_string(source, options=options)
    if formatted.endswith('\n'):
        formatted = formatted[:-1]

    if source != formatted:
        vim.current.buffer[:] = [line.encode(encoding)
                                 for line in formatted.splitlines()]

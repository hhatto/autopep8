"""Run autopep8 on the selected buffer in Vim.

map <C-I> :pyfile <path_to>/vim_autopep8.py<CR>

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
                                   ''])

    formatted = autopep8.fix_code(source, options=options)

    if source != formatted:
        if formatted.endswith('\n'):
            formatted = formatted[:-1]

        vim.current.buffer[:] = [line.encode(encoding)
                                 for line in formatted.splitlines()]

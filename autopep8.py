#!/usr/bin/env python
"""
A tool that automatically formats Python code to conform to the PEP 8 style
guide.
"""
import copy
import os
import re
import sys
try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO
import token
import tokenize
from optparse import OptionParser
from subprocess import Popen, PIPE
from difflib import unified_diff
import tempfile
import ast

from distutils.version import StrictVersion
try:
    import pep8
    if StrictVersion(pep8.__version__) < StrictVersion('1.3a2'):
        pep8 = None
except ImportError:
    pep8 = None


__version__ = '0.7.1'


PEP8_BIN = 'pep8'
PEP8_PASSES_MAX = 100
CR = '\r'
LF = '\n'
CRLF = '\r\n'
MAX_LINE_WIDTH = 79


def open_with_encoding(filename, encoding, mode='r'):
    """Return opened file with a specific encoding."""
    try:
        # Python 3
        return open(filename, mode=mode, encoding=encoding)
    except TypeError:
        return open(filename, mode=mode)


def detect_encoding(filename):
    """Return file encoding."""
    try:
        # Python 3
        try:
            with open(filename, 'rb') as input_file:
                encoding = tokenize.detect_encoding(input_file.readline)[0]

                # Check for correctness of encoding
                import io
                with io.TextIOWrapper(input_file, encoding) as wrapper:
                    wrapper.read()

            return encoding
        except (SyntaxError, LookupError, UnicodeDecodeError):
            return 'latin-1'
    except AttributeError:
        return 'utf-8'


def read_from_filename(filename, readlines=False):
    """Return contents of file."""
    with open_with_encoding(filename,
                            encoding=detect_encoding(filename)) as input_file:
        return input_file.readlines() if readlines else input_file.read()


class FixPEP8(object):

    """Fix invalid code.

    [fixed method list]
        - e111
        - e121,e122,e123,e124,e125,e126,e127,e128
        - e201,e202,e203
        - e211
        - e221,e222,e223,e224,e225
        - e231
        - e251
        - e261,e262
        - e271,e272,e273,e274
        - e301,e302,e303
        - e401
        - e502
        - e701,e702
        - w291,w293
        - w391
        - w602,w603,w604

    """

    def __init__(self, filename, options, contents=None):
        self.filename = filename
        if contents is None:
            self.source = read_from_filename(filename, readlines=True)
        else:
            sio = StringIO(contents)
            self.source = sio.readlines()
        self.original_source = copy.copy(self.source)
        self.newline = find_newline(self.source)
        self.options = options
        self.indent_word = _get_indentword("".join(self.source))
        self.logical_start = None
        self.logical_end = None
        # method definition
        self.fix_e111 = self.fix_e101
        self.fix_e202 = self.fix_e201
        self.fix_e203 = self.fix_e201
        self.fix_e211 = self.fix_e201
        self.fix_e221 = self.fix_e271
        self.fix_e222 = self.fix_e271
        self.fix_e223 = self.fix_e271
        self.fix_e241 = self.fix_e271
        self.fix_e242 = self.fix_e224
        self.fix_e261 = self.fix_e262
        self.fix_e272 = self.fix_e271
        self.fix_e273 = self.fix_e271
        self.fix_e274 = self.fix_e271
        self.fix_w191 = self.fix_e101

    def _fix_source(self, results):
        completed_lines = []
        global_read_fixes = ['e12']
        for result in sorted(results, key=_priority_key):
            # Some fixes read all lines and thus will break if other fixes
            # modify the lines.
            is_global_read_fix = False
            for prefix in global_read_fixes:
                if result['id'].lower().startswith(prefix):
                    is_global_read_fix = True

            # Do not run global fix if any lines have been modified.
            if is_global_read_fix and completed_lines:
                continue

            if result['line'] in completed_lines:
                continue
            fixed_methodname = "fix_%s" % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)
                modified_lines = fix(result)
                if modified_lines:
                    completed_lines += modified_lines
                elif modified_lines == []:  # Empty list means no fix
                    if self.options.verbose:
                        sys.stderr.write('Not fixing {f} on line {l}\n'.format(
                            f=result['id'], l=result['line']))
                else:  # We assume one-line fix when None
                    completed_lines.append(result['line'])
            else:
                if self.options.verbose:
                    sys.stderr.write("'%s' is not defined.\n" %
                                     fixed_methodname)
                    info = result['info'].strip()
                    sys.stderr.write("%s:%s:%s:%s\n" % (self.filename,
                                                        result['line'],
                                                        result['column'],
                                                        info))

    def fix(self):
        """Return a version of the source code with PEP 8 violations fixed."""
        if pep8:
            pep8_options = {
                'ignore':
                self.options.ignore and self.options.ignore.split(','),
                'select':
                self.options.select and self.options.select.split(','),
            }
            results = _execute_pep8(pep8_options, self.source)
        else:
            if self.options.verbose:
                sys.stderr.write('Running in compatibility mode. Consider '
                                 'upgrading to the latest pep8.\n')
            results = _spawn_pep8((["--ignore=" + self.options.ignore]
                                   if self.options.ignore else []) +
                                  (["--select=" + self.options.select]
                                   if self.options.select else []) +
                                  [self.filename])
        self._fix_source(results)
        return "".join(self.source)

    def fix_e101(self, _):
        """Reindent all lines."""
        reindenter = Reindenter(self.source)
        if reindenter.run():
            original_length = len(self.source)
            self.source = reindenter.fixed_lines()
            return range(1, 1 + original_length)
        else:
            return []

    def find_logical(self, force=False):
        # make a variable which is the index of all the starts of lines
        if not force and self.logical_start is not None:
            return
        logical_start = []
        logical_end = []
        last_newline = True
        sio = StringIO("".join(self.source))
        parens = 0
        for t in tokenize.generate_tokens(sio.readline):
            if t[0] in [tokenize.COMMENT, tokenize.DEDENT,
                        tokenize.INDENT, tokenize.NL,
                        tokenize.ENDMARKER]:
                continue
            if not parens and t[0] in [
                tokenize.NEWLINE, tokenize.SEMI
            ]:
                last_newline = True
                logical_end.append((t[3][0] - 1, t[2][1]))
                continue
            if last_newline and not parens:
                logical_start.append((t[2][0] - 1, t[2][1]))
                last_newline = False
            if t[0] == tokenize.OP:
                if t[1] in '([{':
                    parens += 1
                elif t[1] in '}])':
                    parens -= 1
        self.logical_start = logical_start
        self.logical_end = logical_end

    def get_logical(self, result):
        """Return the logical line corresponding to the result.

        Assumes input is already E702-clean.

        """
        self.find_logical()
        row = result['line'] - 1
        col = result['column'] - 1
        ls = None
        le = None
        for i in range(0, len(self.logical_start), 1):
            x = self.logical_end[i]
            if x[0] > row or (x[0] == row and x[1] > col):
                le = x
                ls = self.logical_start[i]
                break
        if ls is None:
            return None
        original = self.source[ls[0]:le[0] + 1]
        return ls, le, original

    def _fix_reindent(self, result, fix_distinct=False):
        """Fix a badly indented line.

        This is done by adding or removing from its initial indent only.

        """
        logical = self.get_logical(result)
        if not logical:
            return []
        ls, _, original = logical
        try:
            rewrapper = Wrapper(original, hard_wrap=MAX_LINE_WIDTH)
        except (tokenize.TokenError, IndentationError):
            return []
        valid_indents = rewrapper.pep8_expected()
        if not rewrapper.rel_indent:
            return []
        if result["line"] > ls[0]:
            # got a valid continuation line number from pep8
            row = result["line"] - ls[0] - 1
            # always pick the first option for this
            valid = valid_indents[row]
            got = rewrapper.rel_indent[row]
        else:
            # line number from pep8 isn't a continuation line.  instead,
            # compare our own function's result, look for the first mismatch,
            # and just hope that we take fewer than 100 iterations to finish.
            for row in range(0, len(original), 1):
                valid = valid_indents[row]
                got = rewrapper.rel_indent[row]
                if valid != got:
                    break
        line = ls[0] + row
        orig_line = self.source[line]
        # always pick the expected indent, for now.
        indent_to = valid[0]
        if fix_distinct and indent_to == 4:
            if len(valid) == 1:
                return []
            else:
                indent_to = valid[1]

        if got != indent_to:
            self.source[line] = (
                " " * (indent_to) + orig_line.lstrip()
            )
            return [line + 1]  # Line indexed at 1
        else:
            return []

    def fix_e121(self, result):
        """The 'peculiar indent' error for hanging indents."""
        # fix by adjusting initial indent level
        return self._fix_reindent(result)

    def fix_e122(self, result):
        """The 'absent indent' error for hanging indents."""
        # fix by adding an initial indent
        return self._fix_reindent(result)

    def fix_e123(self, result):
        """The 'loose fingernails' indentation level error for hanging
        indents."""
        # fix by deleting whitespace to the correct level
        return self._fix_reindent(result)

    def fix_e124(self, result):
        """The 'loose fingernails' indentation level error for visual
        indents."""
        # fix by inserting whitespace before the closing bracket
        return self._fix_reindent(result)

    def fix_e125(self, result):
        """The 'often not visually distinct' error."""
        # fix by indenting the line in error to the next stop.
        return self._fix_reindent(result, fix_distinct=True)

    def fix_e126(self, result):
        """The 'spectacular indent' error for hanging indents."""
        # fix by deleting whitespace to the left
        return self._fix_reindent(result)

    def fix_e127(self, result):
        """The 'interpretive dance' indentation error."""
        # fix by deleting whitespace to the correct level
        return self._fix_reindent(result)

    def fix_e128(self, result):
        """The 'I just wrap long lines with a line break in the middle of my
        argument list' indentation error."""
        # fix by deleting whitespace to the correct level
        return self._fix_reindent(result)

    def fix_e201(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        self.source[line_index] = fix_whitespace(target,
                                                 offset=offset,
                                                 replacement='')

    def fix_e224(self, result):
        target = self.source[result['line'] - 1]
        offset = result['column'] - 1
        fixed = target[:offset] + target[offset:].replace('\t', ' ')
        self.source[result['line'] - 1] = fixed

    def fix_e225(self, result):
        """Fix whitespace around operator."""
        target = self.source[result['line'] - 1]
        offset = result['column'] - 1
        fixed = target[:offset] + ' ' + target[offset:]

        # Only proceed if non-whitespace characters match.
        # And make sure we don't break the indentation.
        if (fixed.replace(' ', '') == target.replace(' ', '') and
                _get_indentation(fixed) == _get_indentation(target)):
            self.source[result['line'] - 1] = fixed
        else:
            return []

    def fix_e231(self, result):
        """Add missing whitespace."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column']
        fixed = target[:offset] + ' ' + target[offset:]
        self.source[line_index] = fixed

    def fix_e251(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column'] - 1
        if target[c].strip():
            fixed = target
        else:
            fixed = target[:c].rstrip() + target[c:].lstrip()

        # There could be an escaped newline
        #
        #     def foo(a=\
        #             1)
        if (fixed.endswith('=\\\n') or
                fixed.endswith('=\\\r\n') or
                fixed.endswith('=\\\r')):
            self.source[line_index] = fixed.rstrip('\n\r \t\\')
            self.source[line_index + 1] = \
                self.source[line_index + 1].lstrip()
            return [line_index + 1, line_index + 2]  # Line indexed at 1

        self.source[result['line'] - 1] = fixed

    def fix_e262(self, result):
        """Fix spacing after comment hash."""
        target = self.source[result['line'] - 1]
        offset = result['column']

        code = target[:offset].rstrip(' \t#')
        comment = target[offset:].lstrip(' \t#')

        fixed = code + ('  # ' + comment if comment.strip()
                        else self.newline)

        self.source[result['line'] - 1] = fixed

    def fix_e271(self, result):
        """Fix extraneous whitespace around keywords."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        self.source[line_index] = fix_whitespace(target,
                                                 offset=offset,
                                                 replacement=' ')

    def fix_e301(self, result):
        cr = self.newline
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e302(self, result):
        add_linenum = 2 - int(result['info'].split()[-1])
        cr = self.newline * add_linenum
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e304(self, result):
        line = result['line'] - 2
        if not self.source[line].strip():
            self.source[line] = ''

    def fix_e303(self, result):
        delete_linenum = int(result['info'].split("(")[1].split(")")[0]) - 2
        delete_linenum = max(1, delete_linenum)

        # We need to count because pep8 reports an offset line number if there
        # are comments.
        cnt = 0
        line = result['line'] - 2
        modified_lines = []
        while cnt < delete_linenum:
            if line < 0:
                break
            if not self.source[line].strip():
                self.source[line] = ''
                modified_lines.append(1 + line)  # Line indexed at 1
                cnt += 1
            line -= 1

        return modified_lines

    def fix_e401(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]

        if not target.lstrip().startswith('import'):
            return []

        indentation = target.split("import ")[0]
        modules = target.split("import ")[1].split(",")
        fixed_modulelist = \
            [indentation + "import %s" % m.lstrip() for m in modules]
        self.source[line_index] = self.newline.join(fixed_modulelist)

    def fix_e501(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]

        if target.lstrip().startswith('#'):
            # Wrap commented lines
            self.source[line_index] = shorten_comment(line=target,
                                                      newline=self.newline)
            return
        else:
            indent = _get_indentation(target)
            source = target[len(indent):]
            sio = StringIO(target)

            # don't fix when multiline string
            try:
                tokens = tokenize.generate_tokens(sio.readline)
                _tokens = [t for t in tokens]
            except (tokenize.TokenError, IndentationError):
                return []

            # Prefer
            # my_long_function_name(
            #     x, y, z, ...)
            #
            # over
            # my_long_function_name(x, y,
            #     z, ...)
            candidate0 = _shorten_line(_tokens, source, target, indent,
                                       self.indent_word, newline=self.newline,
                                       reverse=False)
            candidate1 = _shorten_line(_tokens, source, target, indent,
                                       self.indent_word, newline=self.newline,
                                       reverse=True)
            if candidate0 and candidate1:
                if candidate0.split(self.newline)[0].endswith('('):
                    self.source[line_index] = candidate0
                else:
                    self.source[line_index] = candidate1
            elif candidate0:
                self.source[line_index] = candidate0
            elif candidate1:
                self.source[line_index] = candidate1
            else:
                # Otherwise both don't work
                return []

    def fix_e502(self, result):
        """Remove extraneous escape of newline."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        self.source[line_index] = target.rstrip('\n\r \t\\') + self.newline

    def fix_e701(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column']

        fixed_source = (target[:c] + self.newline +
                        _get_indentation(target) + self.indent_word +
                        target[c:].lstrip())
        self.source[result['line'] - 1] = fixed_source

    def fix_e702(self, result):
        """Fix multiple statements on one line."""
        line_index = result['line'] - 1
        target = self.source[line_index]

        if target.rstrip().endswith(';'):
            self.source[line_index] = target.rstrip('\n \r\t;') + self.newline
            return

        # We currently do not support things like
        #     """
        #         hello
        #       """; foo()
        if '"""' in target:
            return []

        # Make sure we aren't likely in a string
        if target.strip().startswith('"') or target.strip().startswith("'"):
            return []

        offset = result['column'] - 1
        first = target[:offset].rstrip(';')
        second = target[offset:].lstrip(';')

        f = [_get_indentation(target) + t.strip()
             for t in [first, second] if t.strip()]

        self.source[line_index] = self.newline.join(f) + self.newline

    def fix_w291(self, result):
        fixed_line = self.source[result['line'] - 1].rstrip()
        self.source[result['line'] - 1] = "%s%s" % (fixed_line, self.newline)

    def fix_w293(self, result):
        assert not self.source[result['line'] - 1].strip()
        self.source[result['line'] - 1] = self.newline

    def fix_w391(self, _):
        source = copy.copy(self.source)
        source.reverse()
        blank_count = 0
        for line in source:
            line = line.rstrip()
            if line:
                break
            else:
                blank_count += 1
        source = source[blank_count:]
        source.reverse()

        original_length = len(self.source)
        self.source = source
        return range(1, 1 + original_length)

    def fix_w601(self, result):
        target = self.source[result['line'] - 1]
        _before = ""
        _after = ""
        _symbol = ""

        # Skip complicated cases
        if target.count('(') > 1 or target.count(')') > 1:
            return []
        if target.count('(') != target.count(')'):
            return []
        if target.count(',') > 0:
            return []

        _tmp = target.split(".has_key", 1)

        # find dict symbol
        _target = _tmp[0]
        for offset, t in enumerate(_target[::-1]):
            if t == " ":
                _before = _target[::-1][:offset - 1:-1]
                break
            else:
                _symbol = t + _symbol

        # find arg of has_key
        _target = _tmp[1]
        _level = 0
        _arg = ""
        for offset, t in enumerate(_target):
            if t == "(":
                _level += 1
            elif t == ")":
                _level -= 1
                if _level == 0:
                    _after += _target[offset + 1:]
                    break
            else:
                _arg += t

        # Maintain precedence
        if ' ' in _arg.strip():
            _arg = '(' + _arg.strip() + ')'

        self.source[result['line'] - 1] = \
            "".join([_before, _arg, " in ", _symbol, _after])

    def fix_w602(self, result):
        """Fix deprecated form of raising exception."""
        line_index = result['line'] - 1
        line = self.source[line_index]

        split_line = line.split(',')
        if len(split_line) > 1 and split_line[1].strip().startswith('('):
            # Give up
            return []

        if ' or ' in line or ' and ' in line:
            # Give up
            return []

        if (line.endswith('\\\n') or
                line.endswith('\\\r\n') or
                line.endswith('\\\r')):
            self.source[line_index] = line.rstrip('\n\r \t\\')
            self.source[line_index + 1] = \
                ' ' + self.source[line_index + 1].lstrip()
            return [line_index + 1, line_index + 2]  # Line indexed at 1

        modified_lines = [1 + line_index]  # Line indexed at 1

        double = '"""'
        single = "'''"
        if double in line or single in line:
            # Move full multiline string to current line
            if double in line and single in line:
                quotes = (double if line.find(double) < line.find(single)
                          else single)
            elif double in line:
                quotes = double
            else:
                quotes = single
            assert quotes in line

            # Find last line of multiline string
            end_line_index = line_index
            if line.count(quotes) == 1:
                for i in range(line_index + 1, len(self.source)):
                    end_line_index = i
                    if quotes in self.source[i]:
                        break

            # We do not handle anything other than plain multiline strings
            if ('(' in self.source[end_line_index] or
                    '\\' in self.source[end_line_index]):
                return []

            for i in range(line_index + 1, end_line_index + 1):
                line_contents = self.source[i]
                self.source[line_index] += line_contents
                self.source[i] = ''
                modified_lines.append(1 + i)  # Line indexed at 1
            line = self.source[line_index]

        indent, rest = _split_indentation(line)
        try:
            ast_body = ast.parse(rest).body[0]
        except SyntaxError:
            # Give up
            return []

        if len(ast_body._fields) == 3 and ast_body.tback is not None:
            _id = [indent, ]
            for node in ast.iter_child_nodes(ast_body):
                if ast.Str == type(node):
                    quote_word = line[node.col_offset]
                    if quote_word * 3 == \
                            line[node.col_offset:node.col_offset + 3]:
                        quote_word = quote_word * 3
                    _id.append(quote_word + node.s + quote_word)
                    continue
                if ast.Name == type(node):
                    _id.append(node.id)
                    continue
                try:
                    _id.append(repr(ast.literal_eval(node)))
                except ValueError:
                    # Give up
                    return []

            # find space and comment
            sio = StringIO(line)
            old_tokens = None
            for tokens in tokenize.generate_tokens(sio.readline):
                if tokens[0] is tokenize.COMMENT:
                    comment_offset = old_tokens[3][1]
                    _id.append(line[comment_offset:])
                    break
                elif len(_id) == 4 and tokens[0] is token.NEWLINE:
                    _id.append(self.newline)
                    break
                old_tokens = tokens
            # Create fixed line and check for correctness
            candidate = "%sraise %s(%s), None, %s%s" % tuple(_id)
            pattern = '[)(, ]'
            if (re.sub(pattern, repl='', string=candidate).replace('None', '')
                    == re.sub(pattern, repl='', string=line)):
                self.source[result['line'] - 1] = candidate
                return modified_lines
            else:
                return []
        else:
            self.source[line_index] = _fix_basic_raise(line, self.newline)

        return modified_lines

    def fix_w603(self, result):
        target = self.source[result['line'] - 1]
        self.source[result['line'] - 1] = re.sub('<>', '!=', target, count=1)

    def fix_w604(self, result):
        target = self.source[result['line'] - 1]

        # We do not support things like
        #     ``1`` + ``1``
        # And we do not support multiple lines like
        #     `(1
        #      )`
        if len(re.findall('`+', target)) != 2:
            return

        start = target.find('`')
        end = target[::-1].find('`') * -1
        self.source[result['line'] - 1] = "%srepr(%s)%s" % (
            target[:start], target[start + 1:end - 1], target[end:])


def find_newline(source):
    """Return type of newline used in source."""
    cr, lf, crlf = 0, 0, 0
    for s in source:
        if CRLF in s:
            crlf += 1
        elif CR in s:
            cr += 1
        elif LF in s:
            lf += 1
    _max = max(cr, crlf, lf)
    if _max == lf:
        return LF
    elif _max == crlf:
        return CRLF
    elif _max == cr:
        return CR
    else:
        return LF


def _get_indentword(source):
    """Return indentation type."""
    sio = StringIO(source)
    indent_word = "    "  # Default in case source has no indentation
    try:
        for t in tokenize.generate_tokens(sio.readline):
            if t[0] == token.INDENT:
                indent_word = t[1]
                break
    except (tokenize.TokenError, IndentationError):
        pass
    return indent_word


def _get_indentation(line):
    """Return leading whitespace."""
    non_whitespace_index = len(line) - len(line.lstrip())
    return line[:non_whitespace_index]


def _split_indentation(line):
    """Return line split into tuple (indentation, rest)."""
    non_whitespace_index = len(line) - len(line.lstrip())
    return (line[:non_whitespace_index], line[non_whitespace_index:])


def _analyze_pep8result(result):
    tmp = result.split(":")
    filename = tmp[0]
    line = int(tmp[1])
    column = int(tmp[2])
    info = " ".join(result.split()[1:])
    pep8id = info.lstrip().split()[0]
    return dict(id=pep8id, filename=filename, line=line,
                column=column, info=info)


def _get_difftext(old, new, filename):
    diff = unified_diff(old, new, 'original/' + filename, 'fixed/' + filename)
    return "".join(diff)


def _priority_key(pep8_result):
    """Key for sorting PEP8 results.

    Global fixes should be done first. This is important for things
    like indentation.

    """
    priority = ['e101', 'e111', 'w191',  # Global fixes
                'e701',  # Fix multiline colon-based before semicolon based
                'e702',  # Break multiline statements early
                'e225', 'e231',  # things that make lines longer
                'e501',  # before we break lines
                ]
    key = pep8_result['id'].lower()
    if key in priority:
        return priority.index(key)
    else:
        # Lowest priority
        return len(priority)


def _fix_basic_raise(line, newline):
    """Fix W602 basic case."""
    sio = StringIO(line)
    is_found_raise = False
    first_comma_found = False
    comment = ''
    args = ''
    indentation = ''
    exception_type = None
    for tokens in tokenize.generate_tokens(sio.readline):
        if tokens[0] is token.INDENT:
            assert not indentation
            indentation = tokens[1]
        elif tokens[1] == 'raise':
            is_found_raise = True
        elif tokens[0] is token.NAME and is_found_raise:
            if exception_type:
                args += tokens[1]
            else:
                exception_type = tokens[1]
        elif tokens[0] is token.NEWLINE:
            break
        elif tokens[0] is not token.DEDENT:
            if tokens[1].startswith(',') and not first_comma_found:
                first_comma_found = True
            elif tokens[1].startswith('#'):
                assert not comment
                comment = tokens[1]
                break
            else:
                args += tokens[1]
    assert exception_type
    return ''.join([indentation, 'raise ', exception_type,
                    '(',
                    args[1:-1] if args.startswith('(') else args,
                    ')',
                    comment, newline])


def _shorten_line(tokens, source, target, indentation, indent_word, newline,
                  reverse=False):
    """Separate line at OPERATOR."""
    if reverse:
        tokens.reverse()
    for tkn in tokens:
        # Don't break on '=' after keyword as this violates PEP 8.
        if token.OP == tkn[0] and tkn[1] != '=':
            offset = tkn[2][1] + 1
            if reverse:
                if offset > (MAX_LINE_WIDTH - len(indentation) -
                             len(indent_word)):
                    continue
            else:
                if (len(target.rstrip()) - offset >
                        (MAX_LINE_WIDTH - len(indentation) -
                         len(indent_word))):
                    continue
            first = source[:offset - len(indentation)]
            second = (indentation + indent_word +
                      source[offset - len(indentation):].lstrip())
            if not second.strip():
                continue
            # Don't modify if lines are not short enough
            if len(first) > MAX_LINE_WIDTH or len(second) > MAX_LINE_WIDTH:
                continue
            # Do not begin a line with a comma
            if second.lstrip().startswith(','):
                continue
            if tkn[1] in '+-*/':
                fixed = first + ' \\' + newline + second
            else:
                fixed = first + newline + second
            try:
                ret = compile(fixed, '<string>', 'exec')
            except SyntaxError:
                continue
            if ret:
                return indentation + fixed
    return None


def shorten_comment(line, newline):
    """Return trimmed or split long comment line."""
    assert len(line) > MAX_LINE_WIDTH
    line = line.rstrip()

    MIN_CHARACTER_REPEAT = 5
    if len(line) - len(line.rstrip(line[-1])) >= MIN_CHARACTER_REPEAT:
        # Trim comments that end with things like ---------
        return line[:MAX_LINE_WIDTH] + newline
    else:
        indentation = _get_indentation(line) + '# '
        import textwrap
        split_lines = textwrap.wrap(line.lstrip(' \t#'),
                                    initial_indent=indentation,
                                    subsequent_indent=indentation,
                                    width=MAX_LINE_WIDTH)
        return newline.join(split_lines) + newline


def fix_whitespace(line, offset, replacement):
    """Replace whitespace at offset and return fixed line."""
    # Replace escaped newlines too
    return (line[:offset].rstrip('\n\r \t\\') +
            replacement + line[offset:].lstrip('\n\r \t\\'))


def _spawn_pep8(pep8_options):
    """Execute pep8 via subprocess.Popen."""
    paths = os.environ['PATH'].split(':')
    for path in paths:
        if os.path.exists(os.path.join(path, PEP8_BIN)):
            cmd = ([os.path.join(path, PEP8_BIN)] +
                   pep8_options)
            p = Popen(cmd, stdout=PIPE)
            output = p.communicate()[0].decode('utf-8')
            return [_analyze_pep8result(l)
                    for l in output.splitlines()]
    raise Exception("'%s' is not found." % PEP8_BIN)


def _execute_pep8(pep8_options, source):
    """Execute pep8 via python method calls."""
    class QuietReport(pep8.BaseReport):

        """Version of checker that does not print."""

        def __init__(self, options):
            super(QuietReport, self).__init__(options)
            self.__full_error_results = []

        def error(self, line_number, offset, text, _):
            """Collect errors."""
            code = super(QuietReport, self).error(line_number, offset, text, _)
            if code:
                self.__full_error_results.append(
                    dict(id=code, line=line_number,
                         column=offset + 1, info=text))

        def full_error_results(self):
            """Return error results in detail.

            Results are in the form of a list of dictionaries. Each dictionary
            contains 'id', 'line', 'column', and 'info'.

            """
            return self.__full_error_results

    checker = pep8.Checker('', lines=source,
                           reporter=QuietReport, **pep8_options)
    checker.check_all()
    return checker.report.full_error_results()


class Reindenter(object):

    """Reindents badly-indented code to uniformly use four-space indentation.

    Released to the public domain, by Tim Peters, 03 October 2000.

    """

    def __init__(self, input_text):
        self.find_stmt = 1  # next token begins a fresh stmt?
        self.level = 0  # current indent level

        # Raw file lines.
        self.raw = input_text
        self.after = None

        # File lines, rstripped & tab-expanded.  Dummy at start is so
        # that we can use tokenize's 1-based line numbering easily.
        # Note that a line is all-blank iff it's "\n".
        self.lines = [line.rstrip('\n \t').expandtabs() + "\n"
                      for line in self.raw]
        self.lines.insert(0, None)
        self.index = 1  # index into self.lines of next line

        # List of (lineno, indentlevel) pairs, one for each stmt and
        # comment line.  indentlevel is -1 for comment lines, as a
        # signal that tokenize doesn't know what to do about them;
        # indeed, they're our headache!
        self.stats = []

    def run(self):
        tokens = tokenize.generate_tokens(self.getline)
        try:
            for t in tokens:
                self.tokeneater(*t)
        except (tokenize.TokenError, IndentationError):
            return False
        # Remove trailing empty lines.
        lines = self.lines
        while lines and lines[-1] == "\n":
            lines.pop()
        # Sentinel.
        stats = self.stats
        stats.append((len(lines), 0))
        # Map count of leading spaces to # we want.
        have2want = {}
        # Program after transformation.
        after = self.after = []
        # Copy over initial empty lines -- there's nothing to do until
        # we see a line with *something* on it.
        i = stats[0][0]
        after.extend(lines[1:i])
        for i in range(len(stats) - 1):
            thisstmt, thislevel = stats[i]
            nextstmt = stats[i + 1][0]
            have = _leading_space_count(lines[thisstmt])
            want = thislevel * 4
            if want < 0:
                # A comment line.
                if have:
                    # An indented comment line.  If we saw the same
                    # indentation before, reuse what it most recently
                    # mapped to.
                    want = have2want.get(have, - 1)
                    if want < 0:
                        # Then it probably belongs to the next real stmt.
                        for j in range(i + 1, len(stats) - 1):
                            jline, jlevel = stats[j]
                            if jlevel >= 0:
                                if have == _leading_space_count(lines[jline]):
                                    want = jlevel * 4
                                break
                    if want < 0:           # Maybe it's a hanging
                                           # comment like this one,
                        # in which case we should shift it like its base
                        # line got shifted.
                        for j in range(i - 1, -1, -1):
                            jline, jlevel = stats[j]
                            if jlevel >= 0:
                                want = (have + _leading_space_count(
                                        after[jline - 1]) -
                                        _leading_space_count(lines[jline]))
                                break
                    if want < 0:
                        # Still no luck -- leave it alone.
                        want = have
                else:
                    want = 0
            assert want >= 0
            have2want[have] = want
            diff = want - have
            if diff == 0 or have == 0:
                after.extend(lines[thisstmt:nextstmt])
            else:
                for line in lines[thisstmt:nextstmt]:
                    if diff > 0:
                        if line == "\n":
                            after.append(line)
                        else:
                            after.append(" " * diff + line)
                    else:
                        remove = min(_leading_space_count(line), -diff)
                        after.append(line[remove:])
        return self.raw != self.after

    def fixed_lines(self):
        return self.after

    def getline(self):
        """Line-getter for tokenize."""
        if self.index >= len(self.lines):
            line = ""
        else:
            line = self.lines[self.index]
            self.index += 1
        return line

    def tokeneater(self, token_type, _, start, __, line):
        """Line-eater for tokenize."""
        sline = start[0]
        if token_type == tokenize.NEWLINE:
            # A program statement, or ENDMARKER, will eventually follow,
            # after some (possibly empty) run of tokens of the form
            #     (NL | COMMENT)* (INDENT | DEDENT+)?
            self.find_stmt = 1

        elif token_type == tokenize.INDENT:
            self.find_stmt = 1
            self.level += 1

        elif token_type == tokenize.DEDENT:
            self.find_stmt = 1
            self.level -= 1

        elif token_type == tokenize.COMMENT:
            if self.find_stmt:
                self.stats.append((sline, -1))
                # but we're still looking for a new stmt, so leave
                # find_stmt alone

        elif token_type == tokenize.NL:
            pass

        elif self.find_stmt:
            # This is the first "real token" following a NEWLINE, so it
            # must be the first token of the next program statement, or an
            # ENDMARKER.
            self.find_stmt = 0
            if line:   # not endmarker
                self.stats.append((sline, self.level))


class Wrapper(object):

    """Class for functions relating to continuation lines and line folding.

    Each instance operates on a single logical line.

    """

    SKIP_TOKENS = frozenset([
        tokenize.COMMENT, tokenize.NL, tokenize.INDENT,
        tokenize.DEDENT, tokenize.NEWLINE, tokenize.ENDMARKER
    ])

    def __init__(self, physical_lines, hard_wrap=79, soft_wrap=72):
        if type(physical_lines) != list:
            physical_lines = physical_lines.splitlines(keepends=True)
        self.lines = physical_lines
        self.index = 0
        self.hard_wrap = hard_wrap
        self.soft_wrap = soft_wrap
        self.tokens = list()
        self.rel_indent = None
        sio = StringIO("".join(physical_lines))
        for t in tokenize.generate_tokens(sio.readline):
            if not len(self.tokens) and t[0] in self.SKIP_TOKENS:
                continue
            if t[0] != tokenize.ENDMARKER:
                #if t[2][0] > max_seen:
                    #max_seen = t[2][0]
                    #print ">>" + repr(t[4]) + "<<"
                self.tokens.append(t)
        self.logical_line, self.mapping = self.build_tokens_logical(
            self.tokens
        )

    def build_tokens_logical(self, tokens):
        """Build a logical line from a list of tokens.

        Returns the logical line and a list of (offset, token) tuples.  Does
        not mute strings like the version in pep8.py.

        """
        # from pep8.py with minor modifications
        mapping = []
        logical = []
        length = 0
        previous = None
        for t in tokens:
            token_type, text = t[0:2]
            if token_type in self.SKIP_TOKENS:
                continue
            if previous:
                end_line, end = previous[3]
                start_line, start = t[2]
                if end_line != start_line:  # different row
                    prev_text = self.lines[end_line - 1][end - 1]
                    if prev_text == ',' or (prev_text not in '{[('
                                            and text not in '}])'):
                        logical.append(' ')
                        length += 1
                elif end != start:  # different column
                    fill = self.lines[end_line - 1][end:start]
                    logical.append(fill)
                    length += len(fill)
            mapping.append((length, t))
            logical.append(text)
            length += len(text)
            previous = t
        logical_line = ''.join(logical)
        assert logical_line.lstrip() == logical_line
        assert logical_line.rstrip() == logical_line
        return logical_line, mapping

    def pep8_expected(self):
        """Helper function which replicates logic in pep8.py, to know what
        level to indent things to.

        Returns a list of lists; each list represents valid indent levels for
        the line in question, relative from the initial indent.  However, the
        first entry is the indent level which was expected.

        """

        # what follows is an adjusted version of
        # pep8.py:continuation_line_indentation.  All of the comments have been
        # stripped and the 'yield' statements replaced with 'pass'.
        tokens = self.tokens

        first_row = tokens[0][2][0]
        nrows = 1 + tokens[-1][2][0] - first_row

        # here are the return values
        valid_indents = [list()] * nrows
        indent_level = tokens[0][2][1]
        valid_indents[0].append(indent_level)

        if nrows == 1:
            # bug, really.
            return valid_indents

        indent_next = self.logical_line.endswith(':')

        row = depth = 0
        parens = [0] * nrows
        self.rel_indent = rel_indent = [0] * nrows
        indent = [indent_level]
        indent_chances = {}
        last_indent = (0, 0)
        last_token_multiline = None

        for token_type, text, start, end, _ in self.tokens:
            newline = row < start[0] - first_row
            if newline:
                row = start[0] - first_row
                newline = (not last_token_multiline and
                           token_type not in (tokenize.NL, tokenize.NEWLINE))

            if newline:
                # this is where the differences start.  instead of looking at
                # the line and determining whether the observed indent matches
                # our expectations, we decide which type of indentation is in
                # use at the given indent level, and return the offset.  this
                # algorithm is succeptable to "carried errors", but should
                # through repeated runs eventually solve indentation for
                # multi-line expressions less than PEP8_PASSES_MAX lines long.

                if depth:
                    for open_row in range(row - 1, -1, -1):
                        if parens[open_row]:
                            break
                else:
                    open_row = 0

                # that's all we get to work with.  this code attempts to
                # "reverse" the below logic, and place into the valid indents
                # list
                vi = []
                add_second_chances = False
                if token_type == tokenize.OP and text in ']})':
                    # this line starts with a closing bracket, so it needs to
                    # be closed at the same indent as the opening one.
                    if indent[depth]:
                        # hanging indent
                        vi.append(indent[depth])
                    else:
                        # visual indent
                        vi.append(indent_level + rel_indent[open_row])
                elif depth and indent[depth]:
                    # visual indent was previously confirmed.
                    vi.append(indent[depth])
                    add_second_chances = True
                elif depth and True in indent_chances.values():
                    # visual indent happened before, so stick to
                    # visual indent this time.
                    if depth > 1 and indent[depth - 1]:
                        vi.append(indent[depth - 1])
                    else:
                        # stupid fallback
                        vi.append(indent_level + 4)
                    add_second_chances = True
                elif not depth:
                    vi.append(indent_level + 4)
                else:
                    # must be in hanging indent
                    hang = rel_indent[open_row] + 4
                    vi.append(indent_level + hang)

                # about the best we can do without look-ahead
                if indent_next and vi[0] == indent_level + 4 and \
                        nrows == row + 1:
                    vi[0] += 4

                if add_second_chances:
                    # visual indenters like to line things up.
                    min_indent = vi[0]
                    for col, what in indent_chances.items():
                        if col > min_indent and (
                            what is True or
                            (what == str and token_type == tokenize.STRING) or
                            (what == text and token_type == tokenize.OP)
                        ):
                            vi.append(col)
                    vi = sorted(vi)

                valid_indents[row] = vi

                # ...returning to original continuation_line_identation func...
                visual_indent = indent_chances.get(start[1])
                last_indent = start
                rel_indent[row] = start[1] - indent_level
                hang = rel_indent[row] - rel_indent[open_row]

                if token_type == tokenize.OP and text in ']})':
                    if indent[depth]:
                        if start[1] != indent[depth]:
                            pass  # E124
                    elif hang:
                        pass  # E123
                elif visual_indent is True:
                    if not indent[depth]:
                        indent[depth] = start[1]
                elif visual_indent in (text, str):
                    pass
                elif indent[depth] and start[1] < indent[depth]:
                    pass  # E128
                elif hang == 4 or (indent_next and rel_indent[row] == 8):
                    pass
                else:
                    if hang <= 0:
                        pass  # E122
                    elif indent[depth]:
                        pass  # E127
                    elif hang % 4:
                        pass  # E121
                    else:
                        pass  # E126

            # line altered: comments shouldn't define a visual indent
            if parens[row] and not indent[depth] and token_type not in (
                tokenize.NL, tokenize.COMMENT
            ):
                indent[depth] = start[1]
                indent_chances[start[1]] = True
            elif token_type == tokenize.STRING or text in (
                'u', 'ur', 'b', 'br'
            ):
                indent_chances[start[1]] = str

            if token_type == tokenize.OP:
                if text in '([{':
                    depth += 1
                    indent.append(0)
                    parens[row] += 1
                elif text in ')]}' and depth > 0:
                    prev_indent = indent.pop() or last_indent[1]
                    for d in range(depth):
                        if indent[d] > prev_indent:
                            indent[d] = 0
                    for ind in list(indent_chances):
                        if ind >= prev_indent:
                            del indent_chances[ind]
                    depth -= 1
                    if depth and indent[depth]:  # modified
                        indent_chances[indent[depth]] = True
                    for idx in range(row, -1, -1):
                        if parens[idx]:
                            parens[idx] -= 1
                            break
                assert len(indent) == depth + 1
                if start[1] not in indent_chances:
                    indent_chances[start[1]] = text

            last_token_multiline = (start[0] != end[0])

        if indent_next and rel_indent[-1] == 4:
            pass  # E125

        return valid_indents


def _leading_space_count(line):
    """Return number of leading spaces in line."""
    i = 0
    while i < len(line) and line[i] == ' ':
        i += 1
    return i


def fix_file(filename, opts, output=sys.stdout):
    tmp_source = read_from_filename(filename)

    # Add missing newline (important for diff)
    tmp_newline = find_newline(tmp_source)
    if tmp_source == tmp_source.rstrip(tmp_newline):
        tmp_source += tmp_newline

    fix = FixPEP8(filename, opts, contents=tmp_source)
    fixed_source = fix.fix()
    original_source = copy.copy(fix.original_source)
    tmp_filename = filename
    if not pep8 or opts.in_place:
        encoding = detect_encoding(filename)
    for _ in range(opts.pep8_passes):
        if fixed_source == tmp_source:
            break
        tmp_source = copy.copy(fixed_source)
        if not pep8:
            tmp_filename = tempfile.mkstemp()[1]
            fp = open_with_encoding(tmp_filename, encoding=encoding, mode='w')
            fp.write(fixed_source)
            fp.close()
        fix = FixPEP8(tmp_filename, opts, contents=tmp_source)
        fixed_source = fix.fix()
        if not pep8:
            os.remove(tmp_filename)
    del tmp_filename
    del tmp_source

    if opts.diff:
        new = StringIO(''.join(fix.source))
        new = new.readlines()
        output.write(_get_difftext(original_source, new, filename))
    elif opts.in_place:
        fp = open_with_encoding(filename, encoding=encoding,
                                mode='w')
        fp.write(fixed_source)
        fp.close()
    else:
        output.write(fixed_source)


def parse_args(args):
    """Parse command-line options."""
    parser = OptionParser(usage='Usage: autopep8 [options] '
                                '[filename [filename ...]]',
                          version="autopep8: %s" % __version__,
                          description=__doc__,
                          prog='autopep8')
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                      help='print verbose messages')
    parser.add_option('-d', '--diff', action='store_true', dest='diff',
                      help='print the diff for the fixed source')
    parser.add_option('-i', '--in-place', action='store_true',
                      help='make changes to files in place')
    parser.add_option('-r', '--recursive', action='store_true',
                      help='run recursively; must be used with --in-place or '
                           '--diff')
    parser.add_option('-p', '--pep8-passes',
                      default=PEP8_PASSES_MAX, type='int',
                      help='maximum number of additional pep8 passes'
                           ' (default: %default)')
    parser.add_option('--ignore', default='',
                      help='do not fix these errors/warnings (e.g. E4,W)')
    parser.add_option('--select', default='',
                      help='select errors/warnings (e.g. E4,W)')
    opts, args = parser.parse_args(args)

    if not len(args):
        parser.error('incorrect number of arguments')

    if len(args) > 1 and not (opts.in_place or opts.diff):
        parser.error('autopep8 only takes one filename as argument '
                     'unless the "--in-place" or "--diff" options are '
                     'used')

    if opts.recursive and not (opts.in_place or opts.diff):
        parser.error('--recursive must be used with --in-place or --diff')

    if opts.in_place and opts.diff:
        parser.error('--in-place and --diff are mutually exclusive')

    return opts, args


def main():
    """Tool main."""
    opts, args = parse_args(sys.argv[1:])
    if opts.in_place or opts.diff:
        filenames = list(set(args))
    else:
        assert len(args) == 1
        assert not opts.recursive
        filenames = args[:1]

    while filenames:
        name = filenames.pop(0)
        if opts.recursive and os.path.isdir(name):
            for root, _, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py')]
        else:
            if opts.verbose:
                sys.stderr.write('[file:%s]\n' % name)
            try:
                fix_file(name, opts)
            except (UnicodeDecodeError, IOError) as error:
                sys.stderr.write(str(error) + '\n')


if __name__ == '__main__':
    sys.exit(main())

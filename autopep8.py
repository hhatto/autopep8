#!/usr/bin/env python
#
# Copyright (C) 2010-2011 Hideo Hattori
# Copyright (C) 2011-2013 Hideo Hattori, Steven Myint
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Automatically formats Python code to conform to the PEP 8 style guide.

Fixes that only need be done once can be added by adding a function of the form
"fix_<code>(source)" to this module. They should return the fixed source code.
These fixes are picked up by apply_global_fixes().

Fixes that depend on pep8 should be added as methods to FixPEP8. See the class
documentation for more information.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import codecs
import collections
import copy
import difflib
import fnmatch
import inspect
import io
import keyword
import locale
import os
import re
import signal
import sys
import token
import tokenize

import pep8


try:
    unicode
except NameError:
    unicode = str


__version__ = '1.0a4'


CR = '\r'
LF = '\n'
CRLF = '\r\n'


PYTHON_SHEBANG_REGEX = re.compile(r'^#!.*\bpython[23]?\b\s*$')


# For generating line shortening candidates.
SHORTEN_OPERATOR_GROUPS = frozenset([
    frozenset([',']),
    frozenset(['%']),
    frozenset([',', '(', '[', '{']),
    frozenset(['%', '(', '[', '{']),
    frozenset([',', '(', '[', '{', '%', '+', '-', '*', '/', '//']),
    frozenset(['%', '+', '-', '*', '/', '//']),
])


DEFAULT_IGNORE = 'E24'
DEFAULT_INDENT_SIZE = 4


# W602 is handled separately due to the need to avoid "with_traceback".
CODE_TO_2TO3 = {
    'E721': ['idioms'],
    'W601': ['has_key'],
    'W603': ['ne'],
    'W604': ['repr'],
    'W690': ['apply',
             'except',
             'exitfunc',
             'import',
             'numliterals',
             'operator',
             'paren',
             'reduce',
             'renames',
             'standarderror',
             'sys_exc',
             'throw',
             'tuple_params',
             'xreadlines']}


def open_with_encoding(filename, encoding=None, mode='r'):
    """Return opened file with a specific encoding."""
    if not encoding:
        encoding = detect_encoding(filename)

    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def detect_encoding(filename):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            from lib2to3.pgen2 import tokenize as lib2to3_tokenize
            encoding = lib2to3_tokenize.detect_encoding(input_file.readline)[0]

        # Check for correctness of encoding
        with open_with_encoding(filename, encoding) as test_file:
            test_file.read()

        return encoding
    except (LookupError, SyntaxError, UnicodeDecodeError):
        return 'latin-1'


def readlines_from_file(filename):
    """Return contents of file."""
    with open_with_encoding(filename) as input_file:
        return input_file.readlines()


def extended_blank_lines(logical_line,
                         blank_lines,
                         indent_level,
                         previous_logical):
    """Check for missing blank lines after class declaration."""
    if previous_logical.startswith('class '):
        if (
            logical_line.startswith(('def ', 'class ', '@')) or
            pep8.DOCSTRING_REGEX.match(logical_line)
        ):
            if indent_level and not blank_lines:
                yield (0, 'E309 expected 1 blank line after class declaration')
    elif previous_logical.startswith('def '):
        if blank_lines and pep8.DOCSTRING_REGEX.match(logical_line):
            yield (0, 'E303 too many blank lines ({0})'.format(blank_lines))
    elif pep8.DOCSTRING_REGEX.match(previous_logical):
        # Missing blank line between class docstring and method declaration.
        if (
            indent_level and
            not blank_lines and
            logical_line.startswith(('def ')) and
            '(self' in logical_line
        ):
            yield (0, 'E301 expected 1 blank line, found 0')
pep8.register_check(extended_blank_lines)


def continued_indentation(logical_line, tokens, indent_level, noqa):
    """Override pep8's function to provide indentation information."""
    first_row = tokens[0][2][0]
    nrows = 1 + tokens[-1][2][0] - first_row
    if noqa or nrows == 1:
        return

    # indent_next tells us whether the next block is indented. Assuming
    # that it is indented by 4 spaces, then we should not allow 4-space
    # indents on the final continuation line. In turn, some other
    # indents are allowed to have an extra 4 spaces.
    indent_next = logical_line.endswith(':')

    row = depth = 0

    # Remember how many brackets were opened on each line.
    parens = [0] * nrows

    # Relative indents of physical lines.
    rel_indent = [0] * nrows

    # Visual indents.
    indent_chances = {}
    last_indent = tokens[0][2]
    indent = [last_indent[1]]

    last_token_multiline = None
    line = None
    last_line = ''
    last_line_begins_with_multiline = False
    for token_type, text, start, end, line in tokens:

        newline = row < start[0] - first_row
        if newline:
            row = start[0] - first_row
            newline = (not last_token_multiline and
                       token_type not in (tokenize.NL, tokenize.NEWLINE))
            last_line_begins_with_multiline = last_token_multiline

        if newline:
            # This is the beginning of a continuation line.
            last_indent = start

            # Record the initial indent.
            rel_indent[row] = pep8.expand_indent(line) - indent_level

            if depth:
                # A bracket expression in a continuation line.
                # Find the line that it was opened on.
                for open_row in range(row - 1, -1, -1):
                    if parens[open_row]:
                        break
            else:
                # An unbracketed continuation line (ie, backslash).
                open_row = 0
            hang = rel_indent[row] - rel_indent[open_row]
            close_bracket = (token_type == tokenize.OP and text in ']})')
            visual_indent = (not close_bracket and hang > 0 and
                             indent_chances.get(start[1]))

            if close_bracket and indent[depth]:
                # Closing bracket for visual indent.
                if start[1] != indent[depth]:
                    yield (start, 'E124 {0}'.format(indent[depth]))
            elif close_bracket and not hang:
                pass
            elif visual_indent is True:
                # Visual indent is verified.
                if not indent[depth]:
                    indent[depth] = start[1]
            elif visual_indent in (text, unicode):
                # Ignore token lined up with matching one from a previous line.
                pass
            elif indent[depth] and start[1] < indent[depth]:
                # Visual indent is broken.
                yield (start, 'E128 {0}'.format(indent[depth]))
            elif (hang == DEFAULT_INDENT_SIZE or
                  (indent_next and
                   rel_indent[row] == 2 * DEFAULT_INDENT_SIZE)):
                # Hanging indent is verified.
                if close_bracket:
                    yield (start, 'E123 {0}'.format(indent_level +
                                                    rel_indent[open_row]))
            else:
                one_indented = (indent_level + rel_indent[open_row] +
                                DEFAULT_INDENT_SIZE)
                # Indent is broken.
                if hang <= 0:
                    error = ('E122', one_indented)
                elif indent[depth]:
                    error = ('E127', indent[depth])
                elif hang % DEFAULT_INDENT_SIZE:
                    error = ('E121', one_indented)
                else:
                    error = ('E126', one_indented)

                yield (start, '{0} {1}'.format(*error))

        # Look for visual indenting.
        if (parens[row] and token_type not in (tokenize.NL, tokenize.COMMENT)
                and not indent[depth]):
            indent[depth] = start[1]
            indent_chances[start[1]] = True
        # Deal with implicit string concatenation.
        elif (token_type in (tokenize.STRING, tokenize.COMMENT) or
              text in ('u', 'ur', 'b', 'br')):
            indent_chances[start[1]] = unicode
        # Special case for the "if" statement because len("if (") is equal to
        # 4.
        elif not indent_chances and not row and not depth and text == 'if':
            indent_chances[end[1] + 1] = True

        # Keep track of bracket depth.
        if token_type == tokenize.OP:
            if text in '([{':
                depth += 1
                indent.append(0)
                parens[row] += 1
            elif text in ')]}' and depth > 0:
                # Parent indents should not be more than this one.
                prev_indent = indent.pop() or last_indent[1]
                for d in range(depth):
                    if indent[d] > prev_indent:
                        indent[d] = 0
                for ind in list(indent_chances):
                    if ind >= prev_indent:
                        del indent_chances[ind]
                depth -= 1
                if depth:
                    indent_chances[indent[depth]] = True
                for idx in range(row, -1, -1):
                    if parens[idx]:
                        parens[idx] -= 1
                        rel_indent[row] = rel_indent[idx]
                        break
            assert len(indent) == depth + 1
            if (
                start[1] not in indent_chances and
                # This is for purposes of speeding up E121 (GitHub #90).
                not last_line.rstrip().endswith(',')
            ):
                # Allow to line up tokens.
                indent_chances[start[1]] = text

        last_token_multiline = (start[0] != end[0])
        last_line = line

    if (
        indent_next and
        not last_line_begins_with_multiline and
        pep8.expand_indent(line) == indent_level + DEFAULT_INDENT_SIZE
    ):
        yield (last_indent, 'E125 {0}'.format(indent_level +
                                              2 * DEFAULT_INDENT_SIZE))
del pep8._checks['logical_line'][pep8.continued_indentation]
pep8.register_check(continued_indentation)


class FixPEP8(object):

    """Fix invalid code.

    Fixer methods are prefixed "fix_". The _fix_source() method looks for these
    automatically.

    The fixer method can take either one or two arguments (in addition to
    self). The first argument is "result", which is the error information from
    pep8. The second argument, "logical", is required only for logical-line
    fixes.

    The fixer method can return the list of modified lines or None. An empty
    list would mean that no changes were made. None would mean that only the
    line reported in the pep8 error was modified. Note that the modified line
    numbers that are returned are indexed at 1. This typically would correspond
    with the line number reported in the pep8 error information.

    [fixed method list]
        - e121,e122,e123,e124,e125,e126,e127,e128,e129
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
        - e711
        - w291

    """

    def __init__(self, filename,
                 options,
                 contents=None,
                 long_line_ignore_cache=None):
        self.filename = filename
        if contents is None:
            self.source = readlines_from_file(filename)
        else:
            sio = io.StringIO(contents)
            self.source = sio.readlines()
        self.options = options
        self.indent_word = _get_indentword(''.join(self.source))

        self.long_line_ignore_cache = (
            set() if long_line_ignore_cache is None
            else long_line_ignore_cache)

        # method definition
        self.fix_e121 = self._fix_reindent
        self.fix_e122 = self._fix_reindent
        self.fix_e123 = self._fix_reindent
        self.fix_e124 = self._fix_reindent
        self.fix_e126 = self._fix_reindent
        self.fix_e127 = self._fix_reindent
        self.fix_e128 = self._fix_reindent
        self.fix_e129 = self._fix_reindent
        self.fix_e202 = self.fix_e201
        self.fix_e203 = self.fix_e201
        self.fix_e211 = self.fix_e201
        self.fix_e221 = self.fix_e271
        self.fix_e222 = self.fix_e271
        self.fix_e223 = self.fix_e271
        self.fix_e226 = self.fix_e225
        self.fix_e227 = self.fix_e225
        self.fix_e228 = self.fix_e225
        self.fix_e241 = self.fix_e271
        self.fix_e242 = self.fix_e224
        self.fix_e261 = self.fix_e262
        self.fix_e272 = self.fix_e271
        self.fix_e273 = self.fix_e271
        self.fix_e274 = self.fix_e271
        self.fix_e309 = self.fix_e301
        self.fix_e501 = (
            self.fix_long_line_logically if
            options and (options.aggressive >= 2 or options.experimental) else
            self.fix_long_line_physically)
        self.fix_e703 = self.fix_e702

        self._ws_comma_done = False

    def _fix_source(self, results):
        try:
            (logical_start, logical_end) = _find_logical(self.source)
            logical_support = True
        except (SyntaxError, tokenize.TokenError):  # pragma: no cover
            logical_support = False

        completed_lines = set()
        for result in sorted(results, key=_priority_key):
            if result['line'] in completed_lines:
                continue

            fixed_methodname = 'fix_' + result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)

                line_index = result['line'] - 1
                original_line = self.source[line_index]

                is_logical_fix = len(inspect.getargspec(fix).args) > 2
                if is_logical_fix:
                    logical = None
                    if logical_support:
                        logical = _get_logical(self.source,
                                               result,
                                               logical_start,
                                               logical_end)
                        if logical and set(range(
                            logical[0][0],
                            logical[1][0] + 1)).intersection(
                                completed_lines):
                            continue

                    modified_lines = fix(result, logical)
                else:
                    modified_lines = fix(result)

                if modified_lines is None:
                    # Force logical fixes to report what they modified.
                    assert not is_logical_fix

                    if self.source[line_index] == original_line:
                        modified_lines = []

                if modified_lines:
                    completed_lines.update(modified_lines)
                elif modified_lines == []:  # Empty list means no fix
                    if self.options.verbose >= 2:
                        print(
                            '--->  Not fixing {f} on line {l}'.format(
                                f=result['id'], l=result['line']),
                            file=sys.stderr)
                else:  # We assume one-line fix when None.
                    completed_lines.add(result['line'])
            else:
                if self.options.verbose >= 3:
                    print(
                        "--->  '{0}' is not defined.".format(fixed_methodname),
                        file=sys.stderr)

                    info = result['info'].strip()
                    print('--->  {0}:{1}:{2}:{3}'.format(self.filename,
                                                         result['line'],
                                                         result['column'],
                                                         info),
                          file=sys.stderr)

    def fix(self):
        """Return a version of the source code with PEP 8 violations fixed."""
        pep8_options = {
            'ignore': self.options.ignore,
            'select': self.options.select,
            'max_line_length': self.options.max_line_length,
        }
        results = _execute_pep8(pep8_options, self.source)

        if self.options.verbose:
            progress = {}
            for r in results:
                if r['id'] not in progress:
                    progress[r['id']] = set()
                progress[r['id']].add(r['line'])
            print('--->  {n} issue(s) to fix {progress}'.format(
                n=len(results), progress=progress), file=sys.stderr)

        if self.options.line_range:
            results = [
                r for r in results
                if self.options.line_range[0] <= r['line'] <=
                self.options.line_range[1]]

        self._fix_source(filter_results(source=''.join(self.source),
                                        results=results,
                                        aggressive=self.options.aggressive,
                                        indent_size=self.options.indent_size))
        return ''.join(self.source)

    def _fix_reindent(self, result):
        """Fix a badly indented line.

        This is done by adding or removing from its initial indent only.

        """
        num_indent_spaces = int(result['info'].split()[1])
        line_index = result['line'] - 1
        target = self.source[line_index]

        self.source[line_index] = ' ' * num_indent_spaces + target.lstrip()

    def fix_e125(self, result):
        """Fix indentation undistinguish from the next logical line."""
        num_indent_spaces = int(result['info'].split()[1])
        line_index = result['line'] - 1
        target = self.source[line_index]

        spaces_to_add = num_indent_spaces - len(_get_indentation(target))
        indent = len(_get_indentation(target))
        modified_lines = []

        while len(_get_indentation(self.source[line_index])) >= indent:
            self.source[line_index] = (' ' * spaces_to_add +
                                       self.source[line_index])
            modified_lines.append(1 + line_index)  # Line indexed at 1.
            line_index -= 1

        return modified_lines

    def fix_e201(self, result):
        """Remove extraneous whitespace."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        if is_probably_part_of_multiline(target):
            return []

        fixed = fix_whitespace(target,
                               offset=offset,
                               replacement='')

        self.source[line_index] = fixed

    def fix_e224(self, result):
        """Remove extraneous whitespace around operator."""
        target = self.source[result['line'] - 1]
        offset = result['column'] - 1
        fixed = target[:offset] + target[offset:].replace('\t', ' ')
        self.source[result['line'] - 1] = fixed

    def fix_e225(self, result):
        """Fix missing whitespace around operator."""
        target = self.source[result['line'] - 1]
        offset = result['column'] - 1
        fixed = target[:offset] + ' ' + target[offset:]

        # Only proceed if non-whitespace characters match.
        # And make sure we don't break the indentation.
        if (
            fixed.replace(' ', '') == target.replace(' ', '') and
            _get_indentation(fixed) == _get_indentation(target)
        ):
            self.source[result['line'] - 1] = fixed
        else:
            return []

    def fix_e231(self, result):
        """Add missing whitespace."""
        # Optimize for comma case. This will fix all commas in the full source
        # code in one pass. Don't do this more than once. If it fails the first
        # time, there is no point in trying again.
        if ',' in result['info'] and not self._ws_comma_done:
            self._ws_comma_done = True
            original = ''.join(self.source)
            new = refactor(original, ['ws_comma'])
            if original.strip() != new.strip():
                self.source = [new]
                return range(1, 1 + len(original))

        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column']
        fixed = target[:offset] + ' ' + target[offset:]
        self.source[line_index] = fixed

    def fix_e251(self, result):
        """Remove whitespace around parameter '=' sign."""
        line_index = result['line'] - 1
        target = self.source[line_index]

        # This is necessary since pep8 sometimes reports columns that goes
        # past the end of the physical line. This happens in cases like,
        # foo(bar\n=None)
        c = min(result['column'] - 1,
                len(target) - 1)

        if target[c].strip():
            fixed = target
        else:
            fixed = target[:c].rstrip() + target[c:].lstrip()

        # There could be an escaped newline
        #
        #     def foo(a=\
        #             1)
        if fixed.endswith(('=\\\n', '=\\\r\n', '=\\\r')):
            self.source[line_index] = fixed.rstrip('\n\r \t\\')
            self.source[line_index + 1] = self.source[line_index + 1].lstrip()
            return [line_index + 1, line_index + 2]  # Line indexed at 1

        self.source[result['line'] - 1] = fixed

    def fix_e262(self, result):
        """Fix spacing after comment hash."""
        target = self.source[result['line'] - 1]
        offset = result['column']

        code = target[:offset].rstrip(' \t#')
        comment = target[offset:].lstrip(' \t#')

        fixed = code + ('  # ' + comment if comment.strip() else '\n')

        self.source[result['line'] - 1] = fixed

    def fix_e271(self, result):
        """Fix extraneous whitespace around keywords."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        if is_probably_part_of_multiline(target):
            return []

        fixed = fix_whitespace(target,
                               offset=offset,
                               replacement=' ')

        if fixed == target:
            return []
        else:
            self.source[line_index] = fixed

    def fix_e301(self, result):
        """Add missing blank line."""
        cr = '\n'
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e302(self, result):
        """Add missing 2 blank lines."""
        add_linenum = 2 - int(result['info'].split()[-1])
        cr = '\n' * add_linenum
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e303(self, result):
        """Remove extra blank lines."""
        delete_linenum = int(result['info'].split('(')[1].split(')')[0]) - 2
        delete_linenum = max(1, delete_linenum)

        # We need to count because pep8 reports an offset line number if there
        # are comments.
        cnt = 0
        line = result['line'] - 2
        modified_lines = []
        while cnt < delete_linenum and line >= 0:
            if not self.source[line].strip():
                self.source[line] = ''
                modified_lines.append(1 + line)  # Line indexed at 1
                cnt += 1
            line -= 1

        return modified_lines

    def fix_e304(self, result):
        """Remove blank line following function decorator."""
        line = result['line'] - 2
        if not self.source[line].strip():
            self.source[line] = ''

    def fix_e401(self, result):
        """Put imports on separate lines."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        if not target.lstrip().startswith('import'):
            return []

        indentation = re.split(pattern=r'\bimport\b',
                               string=target, maxsplit=1)[0]
        fixed = (target[:offset].rstrip('\t ,') + '\n' +
                 indentation + 'import ' + target[offset:].lstrip('\t ,'))
        self.source[line_index] = fixed

    def fix_long_line_logically(self, result, logical):
        """Try to make lines fit within --max-line-length characters."""
        if (
            not logical or
            len(logical[2]) == 1 or
            self.source[result['line'] - 1].lstrip().startswith('#')
        ):
            return self.fix_long_line_physically(result)

        start_line_index = logical[0][0]
        end_line_index = logical[1][0]
        logical_lines = logical[2]

        previous_line = get_item(self.source, start_line_index - 1, default='')
        next_line = get_item(self.source, end_line_index + 1, default='')

        single_line = join_logical_line(''.join(logical_lines))

        fixed = self.fix_long_line(
            target=single_line,
            previous_line=previous_line,
            next_line=next_line,
            original=''.join(logical_lines))

        if fixed:
            for line_index in range(start_line_index, end_line_index + 1):
                self.source[line_index] = ''
            self.source[start_line_index] = fixed
            return range(start_line_index + 1, end_line_index + 1)
        else:
            return []

    def fix_long_line_physically(self, result):
        """Try to make lines fit within --max-line-length characters."""
        line_index = result['line'] - 1
        target = self.source[line_index]

        previous_line = get_item(self.source, line_index - 1, default='')
        next_line = get_item(self.source, line_index + 1, default='')

        fixed = self.fix_long_line(
            target=target,
            previous_line=previous_line,
            next_line=next_line,
            original=target)

        if fixed:
            self.source[line_index] = fixed
            return [line_index + 1]
        else:
            return []

    def fix_long_line(self, target, previous_line,
                      next_line, original):
        cache_entry = (target, previous_line, next_line)
        if cache_entry in self.long_line_ignore_cache:
            return []

        if target.lstrip().startswith('#'):
            # Wrap commented lines.
            return shorten_comment(
                line=target,
                max_line_length=self.options.max_line_length,
                last_comment=not next_line.lstrip().startswith('#'))

        fixed = get_fixed_long_line(
            target=target,
            previous_line=previous_line,
            original=original,
            indent_word=self.indent_word,
            max_line_length=self.options.max_line_length,
            aggressive=self.options.aggressive,
            experimental=self.options.experimental,
            verbose=self.options.verbose)
        if fixed and not code_almost_equal(original, fixed):
            return fixed
        else:
            self.long_line_ignore_cache.add(cache_entry)
            return None

    def fix_e502(self, result):
        """Remove extraneous escape of newline."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        self.source[line_index] = target.rstrip('\n\r \t\\') + '\n'

    def fix_e701(self, result):
        """Put colon-separated compound statement on separate lines."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column']

        fixed_source = (target[:c] + '\n' +
                        _get_indentation(target) + self.indent_word +
                        target[c:].lstrip('\n\r \t\\'))
        self.source[result['line'] - 1] = fixed_source
        return [result['line'], result['line'] + 1]

    def fix_e702(self, result, logical):
        """Put semicolon-separated compound statement on separate lines."""
        if not logical:
            return []  # pragma: no cover
        logical_lines = logical[2]

        line_index = result['line'] - 1
        target = self.source[line_index]

        if target.rstrip().endswith('\\'):
            # Normalize '1; \\\n2' into '1; 2'.
            self.source[line_index] = target.rstrip('\n \r\t\\')
            self.source[line_index + 1] = self.source[line_index + 1].lstrip()
            return [line_index + 1, line_index + 2]

        if target.rstrip().endswith(';'):
            self.source[line_index] = target.rstrip('\n \r\t;') + '\n'
            return [line_index + 1]

        offset = result['column'] - 1
        first = target[:offset].rstrip(';').rstrip()
        second = (_get_indentation(logical_lines[0]) +
                  target[offset:].lstrip(';').lstrip())

        self.source[line_index] = first + '\n' + second
        return [line_index + 1]

    def fix_e711(self, result):
        """Fix comparison with None."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        right_offset = offset + 2
        if right_offset >= len(target):
            return []

        left = target[:offset].rstrip()
        center = target[offset:right_offset]
        right = target[right_offset:].lstrip()

        if not right.startswith('None'):
            return []

        if center.strip() == '==':
            new_center = 'is'
        elif center.strip() == '!=':
            new_center = 'is not'
        else:
            return []

        self.source[line_index] = ' '.join([left, new_center, right])

    def fix_e712(self, result):
        """Fix comparison with boolean."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        # Handle very easy "not" special cases.
        if re.match(r'^\s*if \w+ == False:$', target):
            self.source[line_index] = re.sub(r'if (\w+) == False:',
                                             r'if not \1:', target, count=1)
        elif re.match(r'^\s*if \w+ != True:$', target):
            self.source[line_index] = re.sub(r'if (\w+) != True:',
                                             r'if not \1:', target, count=1)
        else:
            right_offset = offset + 2
            if right_offset >= len(target):
                return []

            left = target[:offset].rstrip()
            center = target[offset:right_offset]
            right = target[right_offset:].lstrip()

            # Handle simple cases only.
            new_right = None
            if center.strip() == '==':
                if re.match(r'\bTrue\b', right):
                    new_right = re.sub(r'\bTrue\b *', '', right, count=1)
            elif center.strip() == '!=':
                if re.match(r'\bFalse\b', right):
                    new_right = re.sub(r'\bFalse\b *', '', right, count=1)

            if new_right is None:
                return []

            if new_right[0].isalnum():
                new_right = ' ' + new_right

            self.source[line_index] = left + new_right

    def fix_w291(self, result):
        """Remove trailing whitespace."""
        fixed_line = self.source[result['line'] - 1].rstrip()
        self.source[result['line'] - 1] = fixed_line + '\n'


def get_fixed_long_line(target, previous_line, original,
                        indent_word='    ', max_line_length=79,
                        aggressive=False, experimental=False, verbose=False):
    indent = _get_indentation(target)
    source = target[len(indent):]
    assert source.lstrip() == source

    # Check for partial multiline.
    try:
        tokens = list(generate_tokens(source))
    except (SyntaxError, tokenize.TokenError):
        return

    candidates = shorten_line(
        tokens, source, indent,
        indent_word,
        max_line_length,
        aggressive=aggressive,
        experimental=experimental,
        previous_line=previous_line)

    # Also sort alphabetically as a tie breaker (for determinism).
    candidates = sorted(
        sorted(set(candidates).union([target, original])),
        key=lambda x: line_shortening_rank(x,
                                           indent_word,
                                           max_line_length))

    if verbose >= 4:
        print(('-' * 79 + '\n').join([''] + candidates + ['']),
              file=codecs.getwriter('utf-8')(sys.stderr.buffer
                                             if hasattr(sys.stderr,
                                                        'buffer')
                                             else sys.stderr))

    if candidates:
        return candidates[0]


def join_logical_line(logical_line):
    """Return single line based on logical line input."""
    indentation = _get_indentation(logical_line)

    return indentation + untokenize_without_newlines(
        generate_tokens(logical_line.lstrip())) + '\n'


def untokenize_without_newlines(tokens):
    """Return source code based on tokens."""
    text = ''
    last_row = 0
    last_column = -1

    for t in tokens:
        token_string = t[1]
        (start_row, start_column) = t[2]
        (end_row, end_column) = t[3]

        if start_row > last_row:
            last_column = 0
        if (
            (start_column > last_column or token_string == '\n') and
            not text.endswith(' ')
        ):
            text += ' '

        if token_string != '\n':
            text += token_string

        last_row = end_row
        last_column = end_column

    return text


def _find_logical(source_lines):
    # make a variable which is the index of all the starts of lines
    logical_start = []
    logical_end = []
    last_newline = True
    parens = 0
    for t in generate_tokens(''.join(source_lines)):
        if t[0] in [tokenize.COMMENT, tokenize.DEDENT,
                    tokenize.INDENT, tokenize.NL,
                    tokenize.ENDMARKER]:
            continue
        if not parens and t[0] in [tokenize.NEWLINE, tokenize.SEMI]:
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
    return (logical_start, logical_end)


def _get_logical(source_lines, result, logical_start, logical_end):
    """Return the logical line corresponding to the result.

    Assumes input is already E702-clean.

    """
    row = result['line'] - 1
    col = result['column'] - 1
    ls = None
    le = None
    for i in range(0, len(logical_start), 1):
        assert logical_end
        x = logical_end[i]
        if x[0] > row or (x[0] == row and x[1] > col):
            le = x
            ls = logical_start[i]
            break
    if ls is None:
        return None
    original = source_lines[ls[0]:le[0] + 1]
    return ls, le, original


def get_item(items, index, default=None):
    if 0 <= index < len(items):
        return items[index]
    else:
        return default


def reindent(source, indent_size):
    """Reindent all lines."""
    reindenter = Reindenter(source)
    return reindenter.run(indent_size)


def code_almost_equal(a, b):
    """Return True if code is similar.

    Ignore whitespace when comparing specific line.

    """
    split_a = split_and_strip_non_empty_lines(a)
    split_b = split_and_strip_non_empty_lines(b)

    if len(split_a) != len(split_b):
        return False

    for index in range(len(split_a)):
        if ''.join(split_a[index].split()) != ''.join(split_b[index].split()):
            return False

    return True


def split_and_strip_non_empty_lines(text):
    """Return lines split by newline.

    Ignore empty lines.

    """
    return [line.strip() for line in text.splitlines() if line.strip()]


def fix_e269(source, aggressive=False):
    """Format block comments."""
    if '#' not in source:
        # Optimization.
        return source

    ignored_line_numbers = multiline_string_lines(
        source,
        include_docstrings=True) | set(commented_out_code_lines(source))

    fixed_lines = []
    sio = io.StringIO(source)
    for (line_number, line) in enumerate(sio.readlines(), start=1):
        if (
            line.lstrip().startswith('#') and
            line_number not in ignored_line_numbers
        ):
            indentation = _get_indentation(line)
            line = line.lstrip()

            # Normalize beginning if not a shebang.
            if len(line) > 1:
                if (
                    # Leave multiple spaces like '#    ' alone.
                    (line.count('#') > 1 or line[1].isalnum())
                    # Leave stylistic outlined blocks alone.
                    and not line.rstrip().endswith('#')
                ):
                    line = '# ' + line.lstrip('# \t')

            fixed_lines.append(indentation + line)
        else:
            fixed_lines.append(line)

    return ''.join(fixed_lines)


def refactor(source, fixer_names, ignore=None):
    """Return refactored code using lib2to3.

    Skip if ignore string is produced in the refactored code.

    """
    from lib2to3 import pgen2
    try:
        new_text = refactor_with_2to3(source,
                                      fixer_names=fixer_names)
    except (pgen2.parse.ParseError,
            SyntaxError,
            UnicodeDecodeError,
            UnicodeEncodeError):
        return source

    if ignore:
        if ignore in new_text and ignore not in source:
            return source

    return new_text


def code_to_2to3(select, ignore):
    fixes = set()
    for code, fix in CODE_TO_2TO3.items():
        if code_match(code, select=select, ignore=ignore):
            fixes |= set(fix)
    return fixes


def fix_2to3(source, aggressive=True, select=None, ignore=None):
    """Fix various deprecated code (via lib2to3)."""
    if not aggressive:
        return source

    select = select or []
    ignore = ignore or []

    return refactor(source,
                    code_to_2to3(select=select,
                                 ignore=ignore))


def fix_w602(source, aggressive=True):
    """Fix deprecated form of raising exception."""
    if not aggressive:
        return source

    return refactor(source, ['raise'],
                    ignore='with_traceback')


def find_newline(source):
    """Return type of newline used in source.

    Input is a list of lines.

    """
    assert not isinstance(source, unicode)

    counter = collections.defaultdict(int)
    for line in source:
        if line.endswith(CRLF):
            counter[CRLF] += 1
        elif line.endswith(CR):
            counter[CR] += 1
        elif line.endswith(LF):
            counter[LF] += 1

    return (sorted(counter, key=counter.get, reverse=True) or [LF])[0]


def _get_indentword(source):
    """Return indentation type."""
    indent_word = '    '  # Default in case source has no indentation
    try:
        for t in generate_tokens(source):
            if t[0] == token.INDENT:
                indent_word = t[1]
                break
    except (SyntaxError, tokenize.TokenError):
        pass
    return indent_word


def _get_indentation(line):
    """Return leading whitespace."""
    if line.strip():
        non_whitespace_index = len(line) - len(line.lstrip())
        return line[:non_whitespace_index]
    else:
        return ''


def get_diff_text(old, new, filename):
    """Return text of unified diff between old and new."""
    newline = '\n'
    diff = difflib.unified_diff(
        old, new,
        'original/' + filename,
        'fixed/' + filename,
        lineterm=newline)

    text = ''
    for line in diff:
        text += line

        # Work around missing newline (http://bugs.python.org/issue2142).
        if not line.endswith(newline):
            text += newline + r'\ No newline at end of file' + newline

    return text


def _priority_key(pep8_result):
    """Key for sorting PEP8 results.

    Global fixes should be done first. This is important for things like
    indentation.

    """
    priority = [
        # Fix multiline colon-based before semicolon based.
        'e701',
        # Break multiline statements early.
        'e702',
        # Things that make lines longer.
        'e225', 'e231',
        # Remove extraneous whitespace before breaking lines.
        'e201',
        # Shorten whitespace in comment before resorting to wrapping.
        'e262'
    ]
    middle_index = 10000
    lowest_priority = [
        # We need to shorten lines last since the logical fixer can get in a
        # loop, which causes us to exit early.
        'e501'
    ]
    key = pep8_result['id'].lower()
    try:
        return priority.index(key)
    except ValueError:
        try:
            return middle_index + lowest_priority.index(key) + 1
        except ValueError:
            return middle_index


def shorten_line(tokens, source, indentation, indent_word, max_line_length,
                 aggressive=False, experimental=False, previous_line=''):
    """Separate line at OPERATOR.

    Multiple candidates will be yielded.

    """
    for candidate in _shorten_line(tokens=tokens,
                                   source=source,
                                   indentation=indentation,
                                   indent_word=indent_word,
                                   aggressive=aggressive,
                                   previous_line=previous_line):
        yield candidate

    if aggressive:
        for key_token_strings in SHORTEN_OPERATOR_GROUPS:
            shortened = _shorten_line_at_tokens(
                tokens=tokens,
                source=source,
                indentation=indentation,
                indent_word=indent_word,
                key_token_strings=key_token_strings,
                aggressive=aggressive)

            if shortened is not None and shortened != source:
                yield shortened

    if experimental:
        for shortened in _shorten_line_at_tokens_new(
                tokens=tokens,
                indentation=indentation,
                indent_word=indent_word,
                max_line_length=max_line_length):

            yield shortened


def _shorten_line(tokens, source, indentation, indent_word,
                  aggressive=False, previous_line=''):
    """Separate line at OPERATOR.

    The input is expected to be free of newlines except for inside multiline
    strings and at the end.

    Multiple candidates will be yielded.

    """
    for (token_type,
         token_string,
         start_offset,
         end_offset) in token_offsets(tokens):

        if (
            token_type == tokenize.COMMENT and
            not is_probably_part_of_multiline(previous_line) and
            not is_probably_part_of_multiline(source) and
            not source[start_offset + 1:].strip().lower().startswith(
                ('noqa', 'pragma:', 'pylint:'))
        ):
            # Move inline comments to previous line.
            first = source[:start_offset]
            second = source[start_offset:]
            yield (indentation + second.strip() + '\n' +
                   indentation + first.strip() + '\n')
        elif token_type == token.OP and token_string != '=':
            # Don't break on '=' after keyword as this violates PEP 8.

            assert token_type != token.INDENT

            first = source[:end_offset]

            second_indent = indentation
            if first.rstrip().endswith('('):
                second_indent += indent_word
            elif '(' in first:
                second_indent += ' ' * (1 + first.find('('))
            else:
                second_indent += indent_word

            second = (second_indent + source[end_offset:].lstrip())
            if (
                not second.strip() or
                second.lstrip().startswith('#')
            ):
                continue

            # Do not begin a line with a comma
            if second.lstrip().startswith(','):
                continue
            # Do end a line with a dot
            if first.rstrip().endswith('.'):
                continue
            if token_string in '+-*/':
                fixed = first + ' \\' + '\n' + second
            else:
                fixed = first + '\n' + second

            # Only fix if syntax is okay.
            if check_syntax(normalize_multiline(fixed)
                            if aggressive else fixed):
                yield indentation + fixed


# A convenient way to handle tokens.
Token = collections.namedtuple('Token', ['token_type', 'token_string',
                                         'spos', 'epos', 'line'])


def _get_as_string(items):
    string = ''
    last_was_keyword = False

    for item in items:
        if item.is_comma:
            string += ', '
        elif item.is_colon:
            string += ': '
        else:
            item_string = repr(item)
            if (
                string and
                (last_was_keyword or
                 (not string.endswith(tuple('([{,.:}]) ')) and
                  not item_string.startswith(tuple('([{,.:}])'))))
            ):
                string += ' '
            string += item_string

        last_was_keyword = item.is_keyword
    return string


class ReflowedLines(object):

    """The reflowed lines of atoms."""

    class _Indent(object):

        """Represent an indentation in the atom stream."""

        def __init__(self, indent):
            self._indent = indent

        def emit(self):
            return self._indent

        @property
        def size(self):
            return len(self._indent)

    class _Space(object):

        """Represent a space in the atom stream."""

        def emit(self):
            return ' '

        @property
        def size(self):
            return 1

    class _LineBreak(object):

        """Represent a line break in the atom stream."""

        def emit(self):
            return '\n'

        @property
        def size(self):
            return 0

    def __init__(self, max_line_length):
        self._lines = []
        self._max_line_length = max_line_length

    def __repr__(self):
        return self.emit()

    def add_item(self, item):
        self._lines.append(item)

    def add_indent(self, indent):
        self._lines.append(self._Indent(indent))

    def add_line_break(self):
        self._lines.append(self._LineBreak())

    def add_space_if_needed(self, curr_text, equal=False):
        prev_item = self._lines[-1] if self._lines else None

        if (
            not prev_item or isinstance(
                prev_item, (self._LineBreak, self._Indent, self._Space))
        ):
            return

        prev_text = unicode(prev_item)
        if (
            ((prev_item.is_keyword or prev_item.is_string or
              prev_item.is_name or prev_item.is_number) and
             curr_text not in '.,}])') or
            (prev_text != '.' and
             (prev_text in ':,}])' or (equal and prev_text == '=')))
        ):
            self._lines.append(self._Space())

    def fits_on_current_line(self, item_extent):
        return self.current_size() + item_extent <= self._max_line_length

    def current_size(self):
        """The size of the current line minus the indentation."""

        size = 0
        for item in reversed(self._lines):
            size += item.size
            if isinstance(item, self._LineBreak):
                break

        return size

    def line_empty(self):
        return (self._lines and
                isinstance(self._lines[-1],
                           (self._LineBreak, self._Indent)))

    def emit(self):
        string = ''
        for item in self._lines:
            if isinstance(item, self._LineBreak):
                string = string.rstrip()
            string += item.emit()

        return string.rstrip() + '\n'


class Atom(object):

    """The smallest unbreakable unit that can be reflowed."""

    def __init__(self, atom):
        self._atom = atom

    def __repr__(self):
        return self._atom.token_string

    def __len__(self):
        return self.size

    def reflow(self, reflowed_lines, continued_indent,
               break_after_open_bracket=False, depth=1):
        total_size = self.size

        if self.__repr__() not in ',:([{}])':
            # Some atoms will need an extra 1-sized space token after them.
            total_size += 1

        if (
            not reflowed_lines.fits_on_current_line(total_size) and
            not reflowed_lines.line_empty()
        ):
            # Start a new line if there is already something on the line and
            # adding this atom would make it go over the max line length.
            reflowed_lines.add_line_break()
            reflowed_lines.add_indent(continued_indent)

        reflowed_lines.add_item(self)

    def emit(self):
        return self.__repr__()

    @property
    def is_keyword(self):
        return keyword.iskeyword(self._atom.token_string)

    @property
    def is_string(self):
        return self._atom.token_type == tokenize.STRING

    @property
    def is_name(self):
        return self._atom.token_type == tokenize.NAME

    @property
    def is_number(self):
        return self._atom.token_type == tokenize.NUMBER

    @property
    def is_comma(self):
        return self._atom.token_string == ','

    @property
    def is_colon(self):
        return self._atom.token_string == ':'

    @property
    def size(self):
        return len(self._atom.token_string)


class Container_(object):

    """Base class for all container types."""

    def __init__(self, items):
        self._items = items

    def __repr__(self):
        return _get_as_string(self._items)

    def __iter__(self):
        for element in self._items:
            yield element

    def __getitem__(self, idx):
        return self._items[idx]

    def reflow(self, reflowed_lines, continued_indent,
               break_after_open_bracket=False, depth=1):
        for (index, item) in enumerate(self._items):
            prev_elem = get_item(self._items, index - 1)
            next_elem = get_item(self._items, index + 1)

            if prev_elem and prev_elem.is_string and item.is_string:
                # Place consecutive string literals on separate lines.
                reflowed_lines.add_line_break()
                reflowed_lines.add_indent(continued_indent)

            elif isinstance(item, Atom):
                item_text = unicode(item)
                item_size = len(item_text)
                if item_text not in '([{,}])':
                    item_size += depth + 2
                if reflowed_lines.fits_on_current_line(item_size):
                    reflowed_lines.add_space_if_needed(item_text)
                else:
                    # No room at the inn. Line break for the new element.
                    reflowed_lines.add_line_break()
                    reflowed_lines.add_indent(continued_indent)

            # Increase the continued indentation only if we're recursing on a
            # container.
            offset = 1 if isinstance(item, Container_) else 0
            item.reflow(reflowed_lines, continued_indent + (' ' * offset),
                        depth=depth + 1)

            if (
                break_after_open_bracket and index == 0 and
                    # Prefer to keep empty containers together instead of
                    # separating them.
                    unicode(item) == self.open_bracket and
                    (not next_elem or repr(next_elem) != self.close_bracket)
            ):
                reflowed_lines.add_line_break()
                reflowed_lines.add_indent(continued_indent)
                break_after_open_bracket = False

    @property
    def is_string(self):
        return False

    @property
    def size(self):
        return len(self.__repr__())

    @property
    def is_keyword(self):
        return False

    @property
    def is_comma(self):
        return False

    @property
    def is_colon(self):
        return False


class Tuple_(Container_):

    """A high-level representation of a tuple."""

    def __init__(self, items):
        super(Tuple_, self).__init__(items)

    @property
    def open_bracket(self):
        return '('

    @property
    def close_bracket(self):
        return ')'


class List_(Container_):

    """A high-level representation of a list."""

    def __init__(self, items):
        super(List_, self).__init__(items)

    @property
    def open_bracket(self):
        return '['

    @property
    def close_bracket(self):
        return ']'


class DictOrSet(Container_):

    """A high-level representation of a dictionary or set."""

    def __init__(self, items):
        super(DictOrSet, self).__init__(items)

    @property
    def open_bracket(self):
        return '{'

    @property
    def close_bracket(self):
        return '}'


def _parse_container(tokens, index):
    """Parse a high-level container, such as a list, tuple, etc."""

    # Store the opening bracket.
    items = [Atom(Token(*tokens[index]))]
    index += 1

    num_tokens = len(tokens)
    while index < num_tokens:
        tok = Token(*tokens[index])

        if tok.token_string in ')]}':
            # We've reached the end of this container.
            items.append(Atom(tok))

            if tok.token_string == ')':
                # The end of a tuple.
                return (Tuple_(items), index)

            elif tok.token_string == ']':
                # The end of a list.
                return (List_(items), index)

            else:  # tok.token_string == '}'
                # The end of a dictionary or set.
                return (DictOrSet(items), index)

        if tok.token_string in '([{':
            # A sub-container is being defined.
            (container, index) = _parse_container(tokens, index)
            items.append(container)

        else:
            items.append(Atom(tok))

        index += 1


def _parse_tokens(tokens):
    """Parse the tokens.

    This converts the tokens into a form where we can manipulate them more
    easily.

    """

    index = 0
    parsed_tokens = []

    num_tokens = len(tokens)
    while index < num_tokens:
        tok = Token(*tokens[index])

        assert tok.token_type != token.INDENT
        if tok.token_type == tokenize.NEWLINE:
            # There's only one newline and it's at the end.
            break

        if tok.token_string in '([{':
            (container, index) = _parse_container(tokens, index)
            parsed_tokens.append(container)
        else:
            parsed_tokens.append(Atom(tok))

        index += 1

    return parsed_tokens


def _reflow_lines(parsed_tokens, indentation, indent_word, max_line_length,
                  start_on_prefix_line):
    """Reflow the lines so that it looks nice."""

    if unicode(parsed_tokens[0]) == 'def':
        # A function definition gets indented a bit more.
        continued_indent = indentation + indent_word * 2
    else:
        continued_indent = indentation + indent_word

    break_after_open_bracket = not start_on_prefix_line

    reflowed_lines = ReflowedLines(max_line_length)
    reflowed_lines.add_indent(indentation)

    for (index, item) in enumerate(parsed_tokens):
        reflowed_lines.add_space_if_needed(unicode(item), equal=True)

        if start_on_prefix_line and isinstance(item, Container_):
            start_on_prefix_line = False
            continued_indent = ' ' * (reflowed_lines.current_size() + 1)

        item.reflow(
            reflowed_lines, continued_indent, break_after_open_bracket)

    return reflowed_lines.emit()


def _shorten_line_at_tokens_new(tokens, indentation, indent_word,
                                max_line_length):
    """Shorten the line taking its length into account.

    The input is expected to be free of newlines except for inside multiline
    strings and at the end.

    """

    parsed_tokens = _parse_tokens(tokens)

    if parsed_tokens:
        # Perform two reflows. The first one starts on the same line as the
        # prefix. The second starts on the line after the prefix.
        fixed = _reflow_lines(parsed_tokens, indentation, indent_word,
                              max_line_length, start_on_prefix_line=True)
        if check_syntax(normalize_multiline(fixed.lstrip())):
            yield fixed

        fixed = _reflow_lines(parsed_tokens, indentation, indent_word,
                              max_line_length, start_on_prefix_line=False)
        if check_syntax(normalize_multiline(fixed.lstrip())):
            yield fixed


def _shorten_line_at_tokens(tokens, source, indentation, indent_word,
                            key_token_strings, aggressive):
    """Separate line by breaking at tokens in key_token_strings.

    The input is expected to be free of newlines except for inside multiline
    strings and at the end.

    """
    offsets = []
    for (index, _t) in enumerate(token_offsets(tokens)):
        (token_type,
         token_string,
         start_offset,
         end_offset) = _t

        assert token_type != token.INDENT

        if token_string in key_token_strings:
            # Do not break in containers with zero or one items.
            unwanted_next_token = {
                '(': ')',
                '[': ']',
                '{': '}'}.get(token_string)
            if unwanted_next_token:
                if (
                    get_item(tokens,
                             index + 1,
                             default=[None, None])[1] == unwanted_next_token or
                    get_item(tokens,
                             index + 2,
                             default=[None, None])[1] == unwanted_next_token
                ):
                    continue

            if (
                index > 2 and token_string == '(' and
                tokens[index - 1][1] in ',(%['
            ):
                # Don't split after a tuple start, or before a tuple start if
                # the tuple is in a list.
                continue

            if end_offset < len(source) - 1:
                # Don't split right before newline.
                offsets.append(end_offset)
        else:
            # Break at adjacent strings. These were probably meant to be on
            # separate lines in the first place.
            previous_token = get_item(tokens, index - 1)
            if (
                token_type == tokenize.STRING and
                previous_token and previous_token[0] == tokenize.STRING
            ):
                offsets.append(start_offset)

    current_indent = None
    fixed = None
    for line in split_at_offsets(source, offsets):
        if fixed:
            fixed += '\n' + current_indent + line

            for symbol in '([{':
                if line.endswith(symbol):
                    current_indent += indent_word
        else:
            # First line.
            fixed = line
            assert not current_indent
            current_indent = indent_word

    assert fixed is not None

    if check_syntax(normalize_multiline(fixed)
                    if aggressive > 1 else fixed):
        return indentation + fixed
    else:
        return None


def token_offsets(tokens):
    """Yield tokens and offsets."""
    end_offset = 0
    previous_end_row = 0
    previous_end_column = 0
    for t in tokens:
        token_type = t[0]
        token_string = t[1]
        (start_row, start_column) = t[2]
        (end_row, end_column) = t[3]

        # Account for the whitespace between tokens.
        end_offset += start_column
        if previous_end_row == start_row:
            end_offset -= previous_end_column

        # Record the start offset of the token.
        start_offset = end_offset

        # Account for the length of the token itself.
        end_offset += len(token_string)

        yield (token_type,
               token_string,
               start_offset,
               end_offset)

        previous_end_row = end_row
        previous_end_column = end_column


def normalize_multiline(line):
    """Normalize multiline-related code that will cause syntax error.

    This is for purposes of checking syntax.

    """
    if line.startswith('def ') and line.rstrip().endswith(':'):
        return line + ' pass'
    elif line.startswith('return '):
        return 'def _(): ' + line
    else:
        return line


def fix_whitespace(line, offset, replacement):
    """Replace whitespace at offset and return fixed line."""
    # Replace escaped newlines too
    left = line[:offset].rstrip('\n\r \t\\')
    right = line[offset:].lstrip('\n\r \t\\')
    if right.startswith('#'):
        return line
    else:
        return left + replacement + right


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
                    {'id': code,
                     'line': line_number,
                     'column': offset + 1,
                     'info': text})

        def full_error_results(self):
            """Return error results in detail.

            Results are in the form of a list of dictionaries. Each
            dictionary contains 'id', 'line', 'column', and 'info'.

            """
            return self.__full_error_results

    checker = pep8.Checker('', lines=source,
                           reporter=QuietReport, **pep8_options)
    checker.check_all()
    return checker.report.full_error_results()


def _remove_leading_and_normalize(line):
    return line.lstrip().rstrip(CR + LF) + '\n'


class Reindenter(object):

    """Reindents badly-indented code to uniformly use four-space indentation.

    Released to the public domain, by Tim Peters, 03 October 2000.

    """

    def __init__(self, input_text):
        sio = io.StringIO(input_text)
        source_lines = sio.readlines()

        self.string_content_line_numbers = multiline_string_lines(input_text)

        # File lines, rstripped & tab-expanded. Dummy at start is so
        # that we can use tokenize's 1-based line numbering easily.
        # Note that a line is all-blank iff it is a newline.
        self.lines = []
        for line_number, line in enumerate(source_lines, start=1):
            # Do not modify if inside a multiline string.
            if line_number in self.string_content_line_numbers:
                self.lines.append(line)
            else:
                # Only expand leading tabs.
                self.lines.append(_get_indentation(line).expandtabs() +
                                  _remove_leading_and_normalize(line))

        self.lines.insert(0, None)
        self.index = 1  # index into self.lines of next line
        self.input_text = input_text

    def run(self, indent_size=DEFAULT_INDENT_SIZE):
        """Fix indentation and return modified line numbers.

        Line numbers are indexed at 1.

        """
        if indent_size < 1:
            return self.input_text

        try:
            stats = _reindent_stats(tokenize.generate_tokens(self.getline))
        except (SyntaxError, tokenize.TokenError):
            return self.input_text
        # Remove trailing empty lines.
        lines = self.lines
        while lines and lines[-1] == '\n':
            lines.pop()
        # Sentinel.
        stats.append((len(lines), 0))
        # Map count of leading spaces to # we want.
        have2want = {}
        # Program after transformation.
        after = []
        # Copy over initial empty lines -- there's nothing to do until
        # we see a line with *something* on it.
        i = stats[0][0]
        after.extend(lines[1:i])
        for i in range(len(stats) - 1):
            thisstmt, thislevel = stats[i]
            nextstmt = stats[i + 1][0]
            have = _leading_space_count(lines[thisstmt])
            want = thislevel * indent_size
            if want < 0:
                # A comment line.
                if have:
                    # An indented comment line. If we saw the same
                    # indentation before, reuse what it most recently
                    # mapped to.
                    want = have2want.get(have, -1)
                    if want < 0:
                        # Then it probably belongs to the next real stmt.
                        for j in range(i + 1, len(stats) - 1):
                            jline, jlevel = stats[j]
                            if jlevel >= 0:
                                if have == _leading_space_count(lines[jline]):
                                    want = jlevel * indent_size
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
                for line_number, line in enumerate(lines[thisstmt:nextstmt],
                                                   start=thisstmt):
                    if line_number in self.string_content_line_numbers:
                        after.append(line)
                    elif diff > 0:
                        if line == '\n':
                            after.append(line)
                        else:
                            after.append(' ' * diff + line)
                    else:
                        remove = min(_leading_space_count(line), -diff)
                        after.append(line[remove:])

        return ''.join(after)

    def getline(self):
        """Line-getter for tokenize."""
        if self.index >= len(self.lines):
            line = ''
        else:
            line = self.lines[self.index]
            self.index += 1
        return line


def _reindent_stats(tokens):
    """Return list of (lineno, indentlevel) pairs.

    One for each stmt and comment line. indentlevel is -1 for comment lines, as
    a signal that tokenize doesn't know what to do about them; indeed, they're
    our headache!

    """
    find_stmt = 1  # next token begins a fresh stmt?
    level = 0  # current indent level
    stats = []

    for t in tokens:
        token_type = t[0]
        sline = t[2][0]
        line = t[4]

        if token_type == tokenize.NEWLINE:
            # A program statement, or ENDMARKER, will eventually follow,
            # after some (possibly empty) run of tokens of the form
            #     (NL | COMMENT)* (INDENT | DEDENT+)?
            find_stmt = 1

        elif token_type == tokenize.INDENT:
            find_stmt = 1
            level += 1

        elif token_type == tokenize.DEDENT:
            find_stmt = 1
            level -= 1

        elif token_type == tokenize.COMMENT:
            if find_stmt:
                stats.append((sline, -1))
                # but we're still looking for a new stmt, so leave
                # find_stmt alone

        elif token_type == tokenize.NL:
            pass

        elif find_stmt:
            # This is the first "real token" following a NEWLINE, so it
            # must be the first token of the next program statement, or an
            # ENDMARKER.
            find_stmt = 0
            if line:   # not endmarker
                stats.append((sline, level))

    return stats


def _leading_space_count(line):
    """Return number of leading spaces in line."""
    i = 0
    while i < len(line) and line[i] == ' ':
        i += 1
    return i


def refactor_with_2to3(source_text, fixer_names):
    """Use lib2to3 to refactor the source.

    Return the refactored source code.

    """
    from lib2to3.refactor import RefactoringTool
    fixers = ['lib2to3.fixes.fix_' + name for name in fixer_names]
    tool = RefactoringTool(fixer_names=fixers, explicit=fixers)

    from lib2to3.pgen2 import tokenize as lib2to3_tokenize
    try:
        return unicode(tool.refactor_string(source_text, name=''))
    except lib2to3_tokenize.TokenError:
        return source_text


def check_syntax(code):
    """Return True if syntax is okay."""
    try:
        return compile(code, '<string>', 'exec')
    except (SyntaxError, TypeError, UnicodeDecodeError):
        return False


def filter_results(source, results, aggressive, indent_size):
    """Filter out spurious reports from pep8.

    If aggressive is True, we allow possibly unsafe fixes (E711, E712).

    """
    non_docstring_string_line_numbers = multiline_string_lines(
        source, include_docstrings=False)
    all_string_line_numbers = multiline_string_lines(
        source, include_docstrings=True)

    commented_out_code_line_numbers = commented_out_code_lines(source)

    for r in results:
        issue_id = r['id'].lower()

        if r['line'] in non_docstring_string_line_numbers:
            if issue_id.startswith(('e1', 'e501', 'w191')):
                continue

        if r['line'] in all_string_line_numbers:
            if issue_id in ['e501']:
                continue

        # We must offset by 1 for lines that contain the trailing contents of
        # multiline strings.
        if not aggressive and (r['line'] + 1) in all_string_line_numbers:
            # Do not modify multiline strings in non-aggressive mode. Remove
            # trailing whitespace could break doctests.
            if issue_id.startswith(('w29', 'w39')):
                continue

        if aggressive <= 0:
            if issue_id.startswith(('e711', 'w6')):
                continue

        if aggressive <= 1:
            if issue_id.startswith(('e712', )):
                continue

        if r['line'] in commented_out_code_line_numbers:
            if issue_id.startswith(('e26', 'e501')):
                continue

        yield r


def multiline_string_lines(source, include_docstrings=False):
    """Return line numbers that are within multiline strings.

    The line numbers are indexed at 1.

    Docstrings are ignored.

    """
    line_numbers = set()
    previous_token_type = ''
    try:
        for t in generate_tokens(source):
            token_type = t[0]
            start_row = t[2][0]
            end_row = t[3][0]

            if token_type == tokenize.STRING and start_row != end_row:
                if (
                    include_docstrings or
                    previous_token_type != tokenize.INDENT
                ):
                    # We increment by one since we want the contents of the
                    # string.
                    line_numbers |= set(range(1 + start_row, 1 + end_row))

            previous_token_type = token_type
    except (SyntaxError, tokenize.TokenError):
        pass

    return line_numbers


def commented_out_code_lines(source):
    """Return line numbers of comments that are likely code.

    Commented-out code is bad practice, but modifying it just adds even more
    clutter.

    """
    line_numbers = []
    try:
        for t in generate_tokens(source):
            token_type = t[0]
            token_string = t[1]
            start_row = t[2][0]
            line = t[4]

            # Ignore inline comments.
            if not line.lstrip().startswith('#'):
                continue

            if token_type == tokenize.COMMENT:
                stripped_line = token_string.lstrip('#').strip()
                if (
                    ' ' in stripped_line and
                    '#' not in stripped_line and
                    check_syntax(stripped_line)
                ):
                    line_numbers.append(start_row)
    except (SyntaxError, tokenize.TokenError):
        pass

    return line_numbers


def shorten_comment(line, max_line_length, last_comment=False):
    """Return trimmed or split long comment line.

    If there are no comments immediately following it, do a text wrap.
    Doing this wrapping on all comments in general would lead to jagged
    comment text.

    """
    assert len(line) > max_line_length
    line = line.rstrip()

    # PEP 8 recommends 72 characters for comment text.
    indentation = _get_indentation(line) + '# '
    max_line_length = min(max_line_length,
                          len(indentation) + 72)

    MIN_CHARACTER_REPEAT = 5
    if (
        len(line) - len(line.rstrip(line[-1])) >= MIN_CHARACTER_REPEAT and
        not line[-1].isalnum()
    ):
        # Trim comments that end with things like ---------
        return line[:max_line_length] + '\n'
    elif last_comment and re.match(r'\s*#+\s*\w+', line):
        import textwrap
        split_lines = textwrap.wrap(line.lstrip(' \t#'),
                                    initial_indent=indentation,
                                    subsequent_indent=indentation,
                                    width=max_line_length,
                                    break_long_words=False,
                                    break_on_hyphens=False)
        return '\n'.join(split_lines) + '\n'
    else:
        return line + '\n'


def normalize_line_endings(lines, newline):
    """Return fixed line endings.

    All lines will be modified to use the most common line ending.

    """
    return [line.rstrip('\n\r') + newline for line in lines]


def mutual_startswith(a, b):
    return b.startswith(a) or a.startswith(b)


def code_match(code, select, ignore):
    if ignore:
        assert not isinstance(ignore, unicode)
        for ignored_code in [c.strip() for c in ignore]:
            if mutual_startswith(code.lower(), ignored_code.lower()):
                return False

    if select:
        assert not isinstance(select, unicode)
        for selected_code in [c.strip() for c in select]:
            if mutual_startswith(code.lower(), selected_code.lower()):
                return True
        return False

    return True


def fix_code(source, options=None):
    """Return fixed source code."""
    if not options:
        options = parse_args([''])

    if not isinstance(source, unicode):
        source = source.decode(locale.getpreferredencoding(False))

    sio = io.StringIO(source)
    return fix_lines(sio.readlines(), options=options)


def fix_lines(source_lines, options, filename=''):
    """Return fixed source code."""
    # Transform everything to line feed. Then change them back to original
    # before returning fixed source code.
    original_newline = find_newline(source_lines)
    tmp_source = ''.join(normalize_line_endings(source_lines, '\n'))

    # Keep a history to break out of cycles.
    previous_hashes = set()

    if options.line_range:
        fixed_source = tmp_source
    else:
        # Apply global fixes only once (for efficiency).
        fixed_source = apply_global_fixes(tmp_source, options)

    passes = 0
    long_line_ignore_cache = set()
    while hash(fixed_source) not in previous_hashes:
        if options.pep8_passes >= 0 and passes > options.pep8_passes:
            break
        passes += 1

        previous_hashes.add(hash(fixed_source))

        tmp_source = copy.copy(fixed_source)

        fix = FixPEP8(
            filename,
            options,
            contents=tmp_source,
            long_line_ignore_cache=long_line_ignore_cache)

        fixed_source = fix.fix()

    sio = io.StringIO(fixed_source)
    return ''.join(normalize_line_endings(sio.readlines(), original_newline))


def fix_file(filename, options=None, output=None):
    if not options:
        options = parse_args([filename])

    original_source = readlines_from_file(filename)

    fixed_source = original_source

    if options.in_place or output:
        encoding = detect_encoding(filename)

    if output:
        output = codecs.getwriter(encoding)(output.buffer
                                            if hasattr(output, 'buffer')
                                            else output)

        output = LineEndingWrapper(output)

    fixed_source = fix_lines(fixed_source, options, filename=filename)

    if options.diff:
        new = io.StringIO(fixed_source)
        new = new.readlines()
        diff = get_diff_text(original_source, new, filename)
        if output:
            output.write(diff)
            output.flush()
        else:
            return diff
    elif options.in_place:
        fp = open_with_encoding(filename, encoding=encoding,
                                mode='w')
        fp.write(fixed_source)
        fp.close()
    else:
        if output:
            output.write(fixed_source)
            output.flush()
        else:
            return fixed_source


def global_fixes():
    """Yield multiple (code, function) tuples."""
    for function in globals().values():
        if inspect.isfunction(function):
            arguments = inspect.getargspec(function)[0]
            if arguments[:1] != ['source']:
                continue

            code = extract_code_from_function(function)
            if code:
                yield (code, function)


def apply_global_fixes(source, options):
    """Run global fixes on source code.

    These are fixes that only need be done once (unlike those in
    FixPEP8, which are dependent on pep8).

    """
    if code_match('E101', select=options.select, ignore=options.ignore):
        source = reindent(source,
                          indent_size=options.indent_size)

    for (code, function) in global_fixes():
        if code_match(code, select=options.select, ignore=options.ignore):
            if options.verbose:
                print('--->  Applying global fix for {0}'.format(code.upper()),
                      file=sys.stderr)
            source = function(source,
                              aggressive=options.aggressive)

    source = fix_2to3(source,
                      aggressive=options.aggressive,
                      select=options.select,
                      ignore=options.ignore)

    return source


def extract_code_from_function(function):
    """Return code handled by function."""
    if not function.__name__.startswith('fix_'):
        return None

    code = re.sub('^fix_', '', function.__name__)
    if not code:
        return None

    try:
        int(code[1:])
    except ValueError:
        return None

    return code


def create_parser():
    """Return command-line parser."""
    # Do import locally to be friendly to those who use autopep8 as a library
    # and are supporting Python 2.6.
    import argparse

    parser = argparse.ArgumentParser(description=docstring_summary(__doc__),
                                     prog='autopep8')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='count', dest='verbose',
                        default=0,
                        help='print verbose messages; '
                        'multiple -v result in more verbose messages')
    parser.add_argument('-d', '--diff', action='store_true', dest='diff',
                        help='print the diff for the fixed source')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files in place')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='run recursively over directories; '
                        'must be used with --in-place or --diff')
    parser.add_argument('-j', '--jobs', type=int, metavar='n', default=1,
                        help='number of parallel jobs; '
                        'match CPU count if value is less than 1')
    parser.add_argument('-p', '--pep8-passes', metavar='n',
                        default=-1, type=int,
                        help='maximum number of additional pep8 passes '
                        '(default: infinite)')
    parser.add_argument('-a', '--aggressive', action='count', default=0,
                        help='enable non-whitespace changes; '
                        'multiple -a result in more aggressive changes')
    parser.add_argument('--experimental', action='store_true',
                        help='enable experimental fixes')
    parser.add_argument('--exclude', metavar='globs',
                        help='exclude file/directory names that match these '
                        'comma-separated globs')
    parser.add_argument('--list-fixes', action='store_true',
                        help='list codes for fixes; '
                        'used by --ignore and --select')
    parser.add_argument('--ignore', metavar='errors', default='',
                        help='do not fix these errors/warnings '
                        '(default: {0})'.format(DEFAULT_IGNORE))
    parser.add_argument('--select', metavar='errors', default='',
                        help='fix only these errors/warnings (e.g. E4,W)')
    parser.add_argument('--max-line-length', metavar='n', default=79, type=int,
                        help='set maximum allowed line length '
                        '(default: %(default)s)')
    parser.add_argument('--range', metavar='line', dest='line_range',
                        default=None, type=int, nargs=2,
                        help='only fix errors found within this inclusive '
                        'range of line numbers (e.g. 1 99); '
                        'line numbers are indexed at 1')
    parser.add_argument('--indent-size', default=DEFAULT_INDENT_SIZE,
                        type=int, metavar='n',
                        help='number of spaces per indent level '
                             '(default %(default)s)')
    parser.add_argument('files', nargs='*',
                        help="files to format or '-' for standard in")

    return parser


def parse_args(arguments):
    """Parse command-line options."""
    parser = create_parser()
    args = parser.parse_args(arguments)

    if not args.files and not args.list_fixes:
        parser.error('incorrect number of arguments')

    args.files = [decode_filename(name) for name in args.files]

    if '-' in args.files:
        if len(args.files) > 1:
            parser.error('cannot mix stdin and regular files')

        if args.diff:
            parser.error('--diff cannot be used with standard input')

        if args.in_place:
            parser.error('--in-place cannot be used with standard input')

        if args.recursive:
            parser.error('--recursive cannot be used with standard input')

    if len(args.files) > 1 and not (args.in_place or args.diff):
        parser.error('autopep8 only takes one filename as argument '
                     'unless the "--in-place" or "--diff" args are '
                     'used')

    if args.recursive and not (args.in_place or args.diff):
        parser.error('--recursive must be used with --in-place or --diff')

    if args.exclude and not args.recursive:
        parser.error('--exclude is only relevant when used with --recursive')

    if args.in_place and args.diff:
        parser.error('--in-place and --diff are mutually exclusive')

    if args.max_line_length <= 0:
        parser.error('--max-line-length must be greater than 0')

    if args.select:
        args.select = args.select.split(',')

    if args.ignore:
        args.ignore = args.ignore.split(',')
    elif not args.select:
        if args.aggressive:
            # Enable everything by default if aggressive.
            args.select = ['E', 'W']
        else:
            args.ignore = DEFAULT_IGNORE.split(',')

    if args.exclude:
        args.exclude = args.exclude.split(',')
    else:
        args.exclude = []

    if args.jobs < 1:
        # Do not import multiprocessing globally in case it is not supported
        # on the platform.
        import multiprocessing
        args.jobs = multiprocessing.cpu_count()

    if args.jobs > 1 and not args.in_place:
        parser.error('parallel jobs requires --in-place')

    return args


def decode_filename(filename):
    """Return Unicode filename."""
    if isinstance(filename, unicode):
        return filename
    else:
        return filename.decode(sys.getfilesystemencoding())


def supported_fixes():
    """Yield pep8 error codes that autopep8 fixes.

    Each item we yield is a tuple of the code followed by its
    description.

    """
    yield ('E101', docstring_summary(reindent.__doc__))

    instance = FixPEP8(filename=None, options=None, contents='')
    for attribute in dir(instance):
        code = re.match('fix_([ew][0-9][0-9][0-9])', attribute)
        if code:
            yield (
                code.group(1).upper(),
                re.sub(r'\s+', ' ',
                       docstring_summary(getattr(instance, attribute).__doc__))
            )

    for (code, function) in sorted(global_fixes()):
        yield (code.upper() + (4 - len(code)) * ' ',
               re.sub(r'\s+', ' ', docstring_summary(function.__doc__)))

    for code in sorted(CODE_TO_2TO3):
        yield (code.upper() + (4 - len(code)) * ' ',
               re.sub(r'\s+', ' ', docstring_summary(fix_2to3.__doc__)))


def docstring_summary(docstring):
    """Return summary of docstring."""
    return docstring.split('\n')[0]


def line_shortening_rank(candidate, indent_word, max_line_length):
    """Return rank of candidate.

    This is for sorting candidates.

    """
    if not candidate.strip():
        return 0

    rank = 0
    lines = candidate.split('\n')

    offset = 0
    if (
        not lines[0].lstrip().startswith('#') and
        lines[0].rstrip()[-1] not in '([{'
    ):
        for symbol in '([{':
            offset = max(offset, 1 + lines[0].find(symbol))

    current_longest = max(offset + len(x.strip()) for x in lines)

    rank += 2 * max(0, current_longest - max_line_length)

    rank += len(lines)

    # Too much variation in line length is ugly.
    rank += 2 * standard_deviation(len(line) for line in lines)

    bad_staring_symbol = {
        '(': ')',
        '[': ']',
        '{': '}'}.get(lines[0][-1])

    if len(lines) > 1:
        if (
            bad_staring_symbol and
            lines[1].lstrip().startswith(bad_staring_symbol)
        ):
            rank += 20

    for current_line in lines:
        current_line = current_line.strip()

        if current_line.startswith('#'):
            continue

        for bad_start in ['.', '%', '+', '-', '/']:
            if current_line.startswith(bad_start):
                rank += 100

            # Do not tolerate operators on their own line.
            if current_line == bad_start:
                rank += 1000

        if current_line.endswith(('(', '[', '{')):
            # Avoid lonely opening. They result in longer lines.
            if len(current_line) <= len(indent_word):
                rank += 100

            # Avoid ugliness of ", (\n".
            if current_line.endswith(','):
                rank += 100

            if has_arithmetic_operator(current_line):
                rank += 100

        if current_line.endswith(('%', '(', '[', '{')):
            rank -= 20

        # Try to break list comprehensions at the "for".
        if current_line.startswith('for '):
            rank -= 50

        if current_line.endswith('\\'):
            rank += 1

        # Prefer breaking at commas rather than colon.
        if ',' in current_line and current_line.endswith(':'):
            rank += 10

        rank += 10 * count_unbalanced_brackets(current_line)

    return max(0, rank)


def standard_deviation(numbers):
    """Return standard devation."""
    numbers = list(numbers)
    if not numbers:
        return 0
    mean = sum(numbers) / len(numbers)
    return (sum((n - mean) ** 2 for n in numbers) /
            len(numbers)) ** .5


def has_arithmetic_operator(line):
    """Return True if line contains any arithmetic operators."""
    for operator in pep8.ARITHMETIC_OP:
        if operator in line:
            return True

    return False


def count_unbalanced_brackets(line):
    """Return number of unmatched open/close brackets."""
    count = 0
    for opening, closing in ['()', '[]', '{}']:
        count += abs(line.count(opening) - line.count(closing))

    return count


def split_at_offsets(line, offsets):
    """Split line at offsets.

    Return list of strings.

    """
    result = []

    previous_offset = 0
    current_offset = 0
    for current_offset in sorted(offsets):
        if current_offset < len(line) and previous_offset != current_offset:
            result.append(line[previous_offset:current_offset].strip())
        previous_offset = current_offset

    result.append(line[current_offset:])

    return result


class LineEndingWrapper(object):

    r"""Replace line endings to work with sys.stdout.

    It seems that sys.stdout expects only '\n' as the line ending, no matter
    the platform. Otherwise, we get repeated line endings.

    """

    def __init__(self, output):
        self.__output = output

    def write(self, s):
        self.__output.write(s.replace('\r\n', '\n').replace('\r', '\n'))

    def flush(self):
        self.__output.flush()


def match_file(filename, exclude):
    """Return True if file is okay for modifying/recursing."""
    base_name = os.path.basename(filename)

    if base_name.startswith('.'):
        return False

    for pattern in exclude:
        if fnmatch.fnmatch(base_name, pattern):
            return False

    if not os.path.isdir(filename) and not is_python_file(filename):
        return False

    return True


def find_files(filenames, recursive, exclude):
    """Yield filenames."""
    while filenames:
        name = filenames.pop(0)
        if recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if match_file(os.path.join(root, f),
                                            exclude)]
                directories[:] = [d for d in directories
                                  if match_file(os.path.join(root, d),
                                                exclude)]
        else:
            yield name


def _fix_file(parameters):
    """Helper function for optionally running fix_file() in parallel."""
    if parameters[1].verbose:
        print('[file:{0}]'.format(parameters[0]), file=sys.stderr)
    try:
        fix_file(*parameters)
    except IOError as error:
        print(unicode(error), file=sys.stderr)


def fix_multiple_files(filenames, options, output=None):
    """Fix list of files.

    Optionally fix files recursively.

    """
    filenames = find_files(filenames, options.recursive, options.exclude)
    if options.jobs > 1:
        import multiprocessing
        pool = multiprocessing.Pool(options.jobs)
        pool.map(_fix_file,
                 [(name, options) for name in filenames])
    else:
        for name in filenames:
            _fix_file((name, options, output))


def is_python_file(filename):
    """Return True if filename is Python file."""
    if filename.endswith('.py'):
        return True

    try:
        with open_with_encoding(filename) as f:
            first_line = f.readlines(1)[0]
    except (IOError, IndexError):
        return False

    if not PYTHON_SHEBANG_REGEX.match(first_line):
        return False

    return True


def is_probably_part_of_multiline(line):
    """Return True if line is likely part of a multiline string.

    When multiline strings are involved, pep8 reports the error as being
    at the start of the multiline string, which doesn't work for us.

    """
    return (
        '"""' in line or
        "'''" in line or
        line.rstrip().endswith('\\')
    )


def main():
    """Tool main."""
    try:
        # Exit on broken pipe.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except AttributeError:  # pragma: no cover
        # SIGPIPE is not available on Windows.
        pass

    try:
        args = parse_args(sys.argv[1:])

        if args.list_fixes:
            for code, description in sorted(supported_fixes()):
                print('{code} - {description}'.format(
                    code=code, description=description))
            return 0

        if args.files == ['-']:
            assert not args.in_place

            # LineEndingWrapper is unnecessary here due to the symmetry between
            # standard in and standard out.
            sys.stdout.write(fix_code(sys.stdin.read(), args))
        else:
            if args.in_place or args.diff:
                args.files = list(set(args.files))
            else:
                assert len(args.files) == 1
                assert not args.recursive

            fix_multiple_files(args.files, args, sys.stdout)
    except KeyboardInterrupt:
        return 1  # pragma: no cover


class CachedTokenizer(object):

    """A one-element cache around tokenize.generate_tokens().

    Original code written by Ned Batchelder, in coverage.py.

    """

    def __init__(self):
        self.last_text = None
        self.last_tokens = None

    def generate_tokens(self, text):
        """A stand-in for tokenize.generate_tokens()."""
        if text != self.last_text:
            string_io = io.StringIO(text)
            self.last_tokens = list(
                tokenize.generate_tokens(string_io.readline)
            )
            self.last_text = text
        return self.last_tokens

_cached_tokenizer = CachedTokenizer()
generate_tokens = _cached_tokenizer.generate_tokens


if __name__ == '__main__':
    sys.exit(main())

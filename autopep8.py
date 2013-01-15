#!/usr/bin/env python
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Automatically formats Python code to conform to the PEP 8 style guide."""

from __future__ import print_function
from __future__ import division

import copy
import os
import re
import sys
import inspect
import codecs
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import token
import tokenize
from optparse import OptionParser
from subprocess import Popen, PIPE
import difflib
import tempfile

from distutils.version import StrictVersion
try:
    import pep8
    try:
        if StrictVersion(pep8.__version__) < StrictVersion('1.3a2'):
            pep8 = None
    except ValueError:
        # Ignore non-standard version tags.
        pass
except ImportError:
    pep8 = None


__version__ = '0.8.5'


PEP8_BIN = 'pep8'
CR = '\r'
LF = '\n'
CRLF = '\r\n'

try:
    unicode
except NameError:
    unicode = str


def open_with_encoding(filename, encoding=None, mode='r'):
    """Return opened file with a specific encoding."""
    if not encoding:
        encoding = detect_encoding(filename)

    import io
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
    except (SyntaxError, LookupError, UnicodeDecodeError):
        return 'latin-1'


def read_from_filename(filename, readlines=False):
    """Return contents of file."""
    with open_with_encoding(filename) as input_file:
        return input_file.readlines() if readlines else input_file.read()


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
        - e711
        - e721
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
        self.newline = find_newline(self.source)
        self.options = options
        self.indent_word = _get_indentword(unicode().join(self.source))
        self.logical_start = None
        self.logical_end = None
        # method definition
        self.fix_e111 = self.fix_e101
        self.fix_e128 = self.fix_e127
        self.fix_e202 = self.fix_e201
        self.fix_e203 = self.fix_e201
        self.fix_e211 = self.fix_e201
        self.fix_e221 = self.fix_e271
        self.fix_e222 = self.fix_e271
        self.fix_e223 = self.fix_e271
        self.fix_e226 = self.fix_e225
        self.fix_e241 = self.fix_e271
        self.fix_e242 = self.fix_e224
        self.fix_e261 = self.fix_e262
        self.fix_e272 = self.fix_e271
        self.fix_e273 = self.fix_e271
        self.fix_e274 = self.fix_e271
        self.fix_e703 = self.fix_e702
        self.fix_w191 = self.fix_e101

    def _fix_source(self, results):
        completed_lines = set()
        for result in sorted(results, key=_priority_key):
            if result['line'] in completed_lines:
                continue

            fixed_methodname = 'fix_%s' % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)

                is_logical_fix = len(inspect.getargspec(fix).args) > 2
                if is_logical_fix:
                    # Do not run logical fix if any lines have been modified.
                    if completed_lines:
                        continue

                    logical = self._get_logical(result)
                    if not logical:
                        continue

                    modified_lines = fix(result, logical)
                else:
                    modified_lines = fix(result)

                if modified_lines:
                    completed_lines.update(modified_lines)
                elif modified_lines == []:  # Empty list means no fix
                    if self.options.verbose >= 2:
                        print(
                            '--->  Not fixing {f} on line {l}'.format(
                                f=result['id'], l=result['line']),
                            file=sys.stderr)
                else:  # We assume one-line fix when None
                    completed_lines.add(result['line'])
            else:
                if self.options.verbose >= 3:
                    print("--->  '%s' is not defined." % fixed_methodname,
                          file=sys.stderr)
                    info = result['info'].strip()
                    print('--->  %s:%s:%s:%s' % (self.filename,
                                                 result['line'],
                                                 result['column'],
                                                 info),
                          file=sys.stderr)

    def fix(self):
        """Return a version of the source code with PEP 8 violations fixed."""
        if pep8:
            pep8_options = {
                'ignore':
                self.options.ignore and self.options.ignore.split(','),
                'select':
                self.options.select and self.options.select.split(','),
                'max_line_length':
                self.options.max_line_length,
            }
            results = _execute_pep8(pep8_options, self.source)
        else:
            if self.options.verbose:
                print('Running in compatibility mode. Consider '
                      'upgrading to the latest pep8.',
                      file=sys.stderr)
            results = _spawn_pep8((['--ignore=' + self.options.ignore]
                                   if self.options.ignore else []) +
                                  (['--select=' + self.options.select]
                                   if self.options.select else []) +
                                  (['--max-line-length={length}'.format(
                                      length=self.options.max_line_length)]
                                   if self.options.max_line_length else []) +
                                  [self.filename])

        if self.options.verbose:
            progress = {}
            for r in results:
                if r['id'] not in progress:
                    progress[r['id']] = set()
                progress[r['id']].add(r['line'])
            print('--->  {n} issue(s) to fix {progress}'.format(
                n=len(results), progress=progress), file=sys.stderr)

        self._fix_source(filter_results(source=unicode().join(self.source),
                                        results=results,
                                        aggressive=self.options.aggressive))
        return unicode().join(self.source)

    def fix_e101(self, _):
        """Reindent all lines."""
        reindenter = Reindenter(self.source, self.newline)
        modified_line_numbers = reindenter.run()
        if modified_line_numbers:
            self.source = reindenter.fixed_lines()
            return modified_line_numbers
        else:
            return []

    def find_logical(self, force=False):
        # make a variable which is the index of all the starts of lines
        if not force and self.logical_start is not None:
            return
        logical_start = []
        logical_end = []
        last_newline = True
        sio = StringIO(''.join(self.source))
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

    def _get_logical(self, result):
        """Return the logical line corresponding to the result.

        Assumes input is already E702-clean.

        """
        try:
            self.find_logical()
        except (IndentationError, tokenize.TokenError):
            return None

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

    def _fix_reindent(self, result, logical, fix_distinct=False):
        """Fix a badly indented line.

        This is done by adding or removing from its initial indent only.

        """
        if not logical:
            return []
        ls, _, original = logical
        try:
            rewrapper = Wrapper(original)
        except (tokenize.TokenError, IndentationError):
            return []
        valid_indents = rewrapper.pep8_expected()
        if not rewrapper.rel_indent:
            return []
        if result['line'] > ls[0]:
            # got a valid continuation line number from pep8
            row = result['line'] - ls[0] - 1
            # always pick the first option for this
            valid = valid_indents[row]
            got = rewrapper.rel_indent[row]
        else:
            # Line number from pep8 isn't a continuation line. Instead,
            # compare our own function's result, look for the first mismatch,
            # and just hope that we take fewer than 100 iterations to finish.
            for row in range(0, len(original), 1):
                valid = valid_indents[row]
                got = rewrapper.rel_indent[row]
                if valid != got:
                    break
        line = ls[0] + row
        # always pick the expected indent, for now.
        indent_to = valid[0]
        if fix_distinct and indent_to == 4:
            if len(valid) == 1:
                return []
            else:
                indent_to = valid[1]

        if got != indent_to:
            orig_line = self.source[line]
            new_line = ' ' * (indent_to) + orig_line.lstrip()
            if new_line == orig_line:
                return []
            else:
                self.source[line] = new_line
                return [line + 1]  # Line indexed at 1
        else:
            return []

    def fix_e121(self, result, logical):
        """Fix indentation to be a multiple of four."""
        # Fix by adjusting initial indent level.
        return self._fix_reindent(result, logical)

    def fix_e122(self, result, logical):
        """Add absent indentation for hanging indentation."""
        # Fix by adding an initial indent.
        return self._fix_reindent(result, logical)

    def fix_e123(self, result, logical):
        """Align closing bracket to match opening bracket."""
        # Fix by deleting whitespace to the correct level.
        if not logical:
            return []
        logical_lines = logical[2]
        line_index = result['line'] - 1
        original_line = self.source[line_index]

        fixed_line = (_get_indentation(logical_lines[0]) +
                      original_line.lstrip())
        if fixed_line == original_line:
            # Fall back to slower method.
            return self._fix_reindent(result, logical)
        else:
            self.source[line_index] = fixed_line

    def fix_e124(self, result, logical):
        """Align closing bracket to match visual indentation."""
        # Fix by inserting whitespace before the closing bracket.
        return self._fix_reindent(result, logical)

    def fix_e125(self, result, logical):
        """Indent to distinguish line from next logical line."""
        # Fix by indenting the line in error to the next stop.
        modified_lines = self._fix_reindent(result, logical, fix_distinct=True)
        if modified_lines:
            return modified_lines
        else:
            # Fallback
            line_index = result['line'] - 1
            original_line = self.source[line_index]
            self.source[line_index] = self.indent_word + original_line

    def fix_e126(self, result, logical):
        """Fix over-indented hanging indentation."""
        # fix by deleting whitespace to the left
        if not logical:
            return []
        logical_lines = logical[2]
        line_index = result['line'] - 1
        original = self.source[line_index]

        fixed = (_get_indentation(logical_lines[0]) +
                 self.indent_word + original.lstrip())
        if fixed == original:
            # Fallback to slower method.
            return self._fix_reindent(result, logical)
        else:
            self.source[line_index] = fixed

    def fix_e127(self, result, logical):
        """Fix visual indentation."""
        # Fix by inserting/deleting whitespace to the correct level.
        modified_lines = self._align_visual_indent(result, logical)
        if modified_lines != []:
            return modified_lines
        else:
            # Fallback to slower method.
            return self._fix_reindent(result, logical)

    def _align_visual_indent(self, result, logical):
        """Correct visual indent.

        This includes over (E127) and under (E128) indented lines.

        """
        if not logical:
            return []
        logical_lines = logical[2]
        line_index = result['line'] - 1
        original = self.source[line_index]
        fixed = original

        if logical_lines[0].rstrip().endswith('\\'):
            fixed = (_get_indentation(logical_lines[0]) +
                     self.indent_word + original.lstrip())
        else:
            for symbol in '([{':
                if symbol in logical_lines[0]:
                    fixed = logical_lines[0].find(
                        symbol) * ' ' + original.lstrip()
                    break

        if fixed == original:
            return []
        else:
            self.source[line_index] = fixed

    def fix_e201(self, result):
        """Remove extraneous whitespace."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        # When multiline strings are involved, pep8 reports the error as
        # being at the start of the multiline string, which doesn't work
        # for us.
        if ('"""' in target or
            "'''" in target or
                target.rstrip().endswith('\\')):
            return []

        fixed = fix_whitespace(target,
                               offset=offset,
                               replacement='')

        if fixed == target:
            return []
        else:
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
        if (fixed.endswith('=\\\n') or
                fixed.endswith('=\\\r\n') or
                fixed.endswith('=\\\r')):
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

        fixed = code + ('  # ' + comment if comment.strip()
                        else self.newline)

        self.source[result['line'] - 1] = fixed

    def fix_e271(self, result):
        """Fix extraneous whitespace around keywords."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        offset = result['column'] - 1

        # When multiline strings are involved, pep8 reports the error as
        # being at the start of the multiline string, which doesn't work
        # for us.
        if ('"""' in target or
            "'''" in target or
                target.rstrip().endswith('\\')):
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
        cr = self.newline
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e302(self, result):
        """Add missing 2 blank lines."""
        add_linenum = 2 - int(result['info'].split()[-1])
        cr = self.newline * add_linenum
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
        while cnt < delete_linenum:
            if line < 0:
                break
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

        # pep8 (1.3.1) reports false positive if there is an import statement
        # followed by a semicolon and some unrelated statement with commas in
        # it.
        if ';' in target:
            return []

        indentation = re.split(pattern=r'\bimport\b',
                               string=target, maxsplit=1)[0]
        fixed = (target[:offset].rstrip('\t ,') + self.newline +
                 indentation + 'import ' + target[offset:].lstrip('\t ,'))
        self.source[line_index] = fixed

    def fix_e501(self, result):
        """Try to make lines fit within --max-line-length characters."""
        line_index = result['line'] - 1
        target = self.source[line_index]

        if target.lstrip().startswith('#'):
            # Shorten comment if it is the last comment line.
            try:
                if self.source[line_index + 1].lstrip().startswith('#'):
                    return []
            except IndexError:
                pass

            # Wrap commented lines.
            fixed = shorten_comment(
                line=target,
                newline=self.newline,
                max_line_length=self.options.max_line_length)
            if fixed == self.source[line_index]:
                return []
            else:
                self.source[line_index] = fixed
                return

        indent = _get_indentation(target)
        source = target[len(indent):]
        sio = StringIO(target)

        # Check for multiline string.
        try:
            tokens = list(tokenize.generate_tokens(sio.readline))
        except (tokenize.TokenError, IndentationError):
            multi_line_candidate = break_multi_line(
                target, newline=self.newline,
                indent_word=self.indent_word,
                max_line_length=self.options.max_line_length)

            if multi_line_candidate:
                self.source[line_index] = multi_line_candidate
                return
            else:
                return []

        # Prefer
        # my_long_function_name(
        #     x, y, z, ...)
        #
        # over
        # my_long_function_name(x, y,
        #     z, ...)
        candidates = [None, None]
        for candidate_index, reverse in enumerate([False, True]):
            candidates[candidate_index] = shorten_line(
                tokens, source, target, indent,
                self.indent_word, newline=self.newline,
                max_line_length=self.options.max_line_length,
                reverse=reverse,
                aggressive=self.options.aggressive)

        if candidates[0] and candidates[1]:
            if candidates[0].split(self.newline)[0].endswith('('):
                self.source[line_index] = candidates[0]
            else:
                self.source[line_index] = candidates[1]
        elif candidates[0]:
            self.source[line_index] = candidates[0]
        elif candidates[1]:
            self.source[line_index] = candidates[1]
        else:
            # Otherwise both don't work
            return []

    def fix_e502(self, result):
        """Remove extraneous escape of newline."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        self.source[line_index] = target.rstrip('\n\r \t\\') + self.newline

    def fix_e701(self, result):
        """Put colon-separated compound statement on separate lines."""
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column']

        fixed_source = (target[:c] + self.newline +
                        _get_indentation(target) + self.indent_word +
                        target[c:].lstrip('\n\r \t\\'))
        self.source[result['line'] - 1] = fixed_source

    def fix_e702(self, result, logical):
        """Put semicolon-separated compound statement on separate lines."""
        logical_lines = logical[2]

        line_index = result['line'] - 1
        target = self.source[line_index]

        if target.rstrip().endswith('\\'):
            # Normalize '1; \\\n2' into '1; 2'.
            self.source[line_index] = target.rstrip('\n \r\t\\')
            self.source[line_index + 1] = self.source[line_index + 1].lstrip()
            return [line_index + 1, line_index + 2]

        if target.rstrip().endswith(';'):
            self.source[line_index] = target.rstrip('\n \r\t;') + self.newline
            return

        offset = result['column'] - 1
        first = target[:offset].rstrip(';').rstrip()
        second = (_get_indentation(logical_lines[0]) +
                  target[offset:].lstrip(';').lstrip())

        self.source[line_index] = first + self.newline + second

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

    def fix_e721(self, _):
        """Switch to use isinstance()."""
        return self.refactor('idioms')

    def fix_w291(self, result):
        """Remove trailing whitespace."""
        fixed_line = self.source[result['line'] - 1].rstrip()
        self.source[result['line'] - 1] = '%s%s' % (fixed_line, self.newline)

    def fix_w293(self, result):
        """Remove trailing whitespace on blank line."""
        assert not self.source[result['line'] - 1].strip()
        self.source[result['line'] - 1] = self.newline

    def fix_w391(self, _):
        """Remove trailing blank lines."""
        blank_count = 0
        for line in reversed(self.source):
            line = line.rstrip()
            if line:
                break
            else:
                blank_count += 1

        original_length = len(self.source)
        self.source = self.source[:original_length - blank_count]
        return range(1, 1 + original_length)

    def refactor(self, fixer_name, ignore=None):
        """Return refactored code using lib2to3.

        Skip if ignore string is produced in the refactored code.

        """
        from lib2to3 import pgen2
        try:
            new_text = refactor_with_2to3(''.join(self.source),
                                          fixer_name=fixer_name)
        except (pgen2.parse.ParseError,
                UnicodeDecodeError, UnicodeEncodeError):
            return []

        original = unicode().join(self.source).strip()
        if original == new_text.strip():
            return []
        else:
            if ignore:
                if ignore in new_text and ignore not in ''.join(self.source):
                    return []
            original_length = len(self.source)
            self.source = [new_text]
            return range(1, 1 + original_length)

    def fix_w601(self, _):
        """Replace the {}.has_key() form with 'in'."""
        return self.refactor('has_key')

    def fix_w602(self, _):
        """Fix deprecated form of raising exception."""
        return self.refactor('raise',
                             ignore='with_traceback')

    def fix_w603(self, _):
        """Replace <> with !=."""
        return self.refactor('ne')

    def fix_w604(self, _):
        """Replace backticks with repr()."""
        return self.refactor('repr')


def find_newline(source):
    """Return type of newline used in source."""
    cr, lf, crlf = 0, 0, 0
    for s in source:
        if s.endswith(CRLF):
            crlf += 1
        elif s.endswith(CR):
            cr += 1
        elif s.endswith(LF):
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
    indent_word = '    '  # Default in case source has no indentation
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
    if line.strip():
        non_whitespace_index = len(line) - len(line.lstrip())
        return line[:non_whitespace_index]
    else:
        return ''


def _analyze_pep8result(result):
    tmp = result.split(':')
    info = ' '.join(result.split()[1:])
    return {'id': info.lstrip().split()[0],
            'filename': tmp[0],
            'line': int(tmp[1]),
            'column': int(tmp[2]),
            'info': info}


def _get_difftext(old, new, filename):
    diff = difflib.unified_diff(
        old, new,
        'original/' + filename,
        'fixed/' + filename)
    return ''.join(diff)


def _priority_key(pep8_result):
    """Key for sorting PEP8 results.

    Global fixes should be done first. This is important for things
    like indentation.

    """
    priority = ['e101', 'e111', 'w191',  # Global fixes
                'e701',  # Fix multiline colon-based before semicolon based
                'e702',  # Break multiline statements early
                'e225', 'e231',  # things that make lines longer
                'e201',  # Remove extraneous whitespace before breaking lines
                'e501',  # before we break lines
                ]
    key = pep8_result['id'].lower()
    if key in priority:
        return priority.index(key)
    else:
        # Lowest priority
        return len(priority)


def shorten_line(tokens, source, target, indentation, indent_word, newline,
                 max_line_length, reverse=False, aggressive=False):
    """Separate line at OPERATOR."""
    actual_length = len(indentation) + len(source)

    delta = (actual_length - max_line_length) // 3
    assert delta >= 0

    if not delta:
        delta = 1

    shortened = None
    length = None
    for length in range(max_line_length, actual_length, delta):
        shortened = _shorten_line(
            tokens=tokens,
            source=source,
            target=target,
            indentation=indentation,
            indent_word=indent_word,
            newline=newline,
            max_line_length=length,
            reverse=reverse,
            aggressive=aggressive)

        if shortened is not None:
            break

    if length is None or length > max_line_length:
        commas_shortened = _shorten_line_at_commas(
            tokens=tokens,
            source=source,
            indentation=indentation,
            newline=newline)

        if commas_shortened is not None and commas_shortened != source:
            shortened = commas_shortened

    return shortened


def _shorten_line(tokens, source, target, indentation, indent_word, newline,
                  max_line_length, reverse=False, aggressive=False):
    """Separate line at OPERATOR."""
    max_line_length_minus_indentation = max_line_length - len(indentation)
    if reverse:
        tokens = reversed(tokens)
    for tkn in tokens:
        # Don't break on '=' after keyword as this violates PEP 8.
        if token.OP == tkn[0] and tkn[1] != '=':
            offset = tkn[2][1] + 1
            if reverse:
                if offset > (max_line_length_minus_indentation -
                             len(indent_word)):
                    continue
            else:
                if (len(target.rstrip()) - offset >
                        (max_line_length_minus_indentation -
                         len(indent_word))):
                    continue
            first = source[:offset - len(indentation)]

            second_indent = indentation
            if first.rstrip().endswith('('):
                second_indent += indent_word
            elif '(' in first:
                second_indent += ' ' * (1 + first.find('('))
            else:
                second_indent += indent_word

            second = (second_indent +
                      source[offset - len(indentation):].lstrip())
            if not second.strip():
                continue

            # Don't modify if lines are not short enough
            if len(first) > max_line_length_minus_indentation:
                continue
            if len(second) > max_line_length:  # Already includes indentation
                continue
            # Do not begin a line with a comma
            if second.lstrip().startswith(','):
                continue
            # Do end a line with a dot
            if first.rstrip().endswith('.'):
                continue
            if tkn[1] in '+-*/':
                fixed = first + ' \\' + newline + second
            else:
                fixed = first + newline + second

            # Only fix if syntax is okay.
            if check_syntax(normalize_multiline(fixed)
                            if aggressive else fixed):
                return indentation + fixed
    return None


def _shorten_line_at_commas(tokens, source, indentation, newline):
    """Separate line by breaking at commas."""
    if ',' not in source:
        return None

    fixed = ''
    last_column = -1
    for tkn in tokens:
        token_type = tkn[0]
        token_string = tkn[1]
        _, start_column = tkn[2]
        _, end_column = tkn[3]

        fixed += token_string

        if token_type == token.OP and token_string == ',':
            fixed += newline
        else:
            # Preserve spacing
            if start_column > last_column:
                fixed += source[last_column:start_column]

        last_column = end_column

    if check_syntax(fixed):
        return indentation + fixed
    else:
        return None


def normalize_multiline(line):
    """Remove multiline-related code that will cause syntax error.

    This is for purposes of checking syntax.

    """
    for quote in '\'"':
        pattern = r'^{q}[^{q}]*{q}\s*:\s*'.format(q=quote)
        if re.match(pattern, line):
            return re.sub(pattern, '', line)

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


def _spawn_pep8(pep8_options):
    """Execute pep8 via subprocess.Popen."""
    p = Popen([PEP8_BIN] + pep8_options, stdout=PIPE)
    output = p.communicate()[0].decode('utf-8')
    return [_analyze_pep8result(l) for l in output.splitlines()]


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

    def __init__(self, input_text, newline):
        self.newline = newline

        # Raw file lines.
        self.raw = input_text
        self.after = None

        self.string_content_line_numbers = multiline_string_lines(
            ''.join(self.raw))

        # File lines, rstripped & tab-expanded. Dummy at start is so
        # that we can use tokenize's 1-based line numbering easily.
        # Note that a line is all-blank iff it is a newline.
        self.lines = []
        for line_number, line in enumerate(self.raw, start=1):
            # Do not modify if inside a multi-line string.
            if line_number in self.string_content_line_numbers:
                self.lines.append(line)
            else:
                # Only expand leading tabs.
                self.lines.append(_get_indentation(line).expandtabs() +
                                  line.strip() + newline)

        self.lines.insert(0, None)
        self.index = 1  # index into self.lines of next line

    def run(self):
        """Fix indentation and return modified line numbers.

        Line numbers are indexed at 1.

        """
        try:
            stats = reindent_stats(tokenize.generate_tokens(self.getline))
        except (tokenize.TokenError, IndentationError):
            return set()
        # Remove trailing empty lines.
        lines = self.lines
        while lines and lines[-1] == self.newline:
            lines.pop()
        # Sentinel.
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
                    # An indented comment line. If we saw the same
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
                for line_number, line in enumerate(lines[thisstmt:nextstmt],
                                                   start=thisstmt):
                    if line_number in self.string_content_line_numbers:
                        after.append(line)
                    elif diff > 0:
                        if line == self.newline:
                            after.append(line)
                        else:
                            after.append(' ' * diff + line)
                    else:
                        remove = min(_leading_space_count(line), -diff)
                        after.append(line[remove:])

        if self.raw == self.after:
            return set()
        else:
            return (set(range(1, 1 + len(self.raw))) -
                    self.string_content_line_numbers)

    def fixed_lines(self):
        return self.after

    def getline(self):
        """Line-getter for tokenize."""
        if self.index >= len(self.lines):
            line = ''
        else:
            line = self.lines[self.index]
            self.index += 1
        return line


def reindent_stats(tokens):
    """Return list  of (lineno, indentlevel) pairs.

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


class Wrapper(object):

    """Class for functions relating to continuation lines and line folding.

    Each instance operates on a single logical line.

    """

    SKIP_TOKENS = frozenset([
        tokenize.COMMENT, tokenize.NL, tokenize.INDENT,
        tokenize.DEDENT, tokenize.NEWLINE, tokenize.ENDMARKER
    ])

    def __init__(self, physical_lines):
        self.lines = physical_lines
        self.tokens = []
        self.rel_indent = None
        sio = StringIO(''.join(physical_lines))
        for t in tokenize.generate_tokens(sio.readline):
            if not len(self.tokens) and t[0] in self.SKIP_TOKENS:
                continue
            if t[0] != tokenize.ENDMARKER:
                self.tokens.append(t)

        self.logical_line = self.build_tokens_logical(self.tokens)

    def build_tokens_logical(self, tokens):
        """Build a logical line from a list of tokens.

        Return the logical line and a list of (offset, token) tuples. Does
        not mute strings like the version in pep8.py.

        """
        # from pep8.py with minor modifications
        logical = []
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
                elif end != start:  # different column
                    fill = self.lines[end_line - 1][end:start]
                    logical.append(fill)
            logical.append(text)
            previous = t
        logical_line = ''.join(logical)
        assert logical_line.lstrip() == logical_line
        assert logical_line.rstrip() == logical_line
        return logical_line

    def pep8_expected(self):
        """Replicate logic in pep8.py, to know what level to indent things to.

        Return a list of lists; each list represents valid indent levels for
        the line in question, relative from the initial indent. However, the
        first entry is the indent level which was expected.

        """
        # What follows is an adjusted version of
        # pep8.py:continuation_line_indentation. All of the comments have been
        # stripped and the 'yield' statements replaced with 'pass'.
        tokens = self.tokens
        if not tokens:
            return

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
                # This is where the differences start. Instead of looking at
                # the line and determining whether the observed indent matches
                # our expectations, we decide which type of indentation is in
                # use at the given indent level, and return the offset. This
                # algorithm is susceptible to "carried errors", but should
                # through repeated runs eventually solve indentation for
                # multi-line expressions less than PEP8_PASSES_MAX lines long.

                if depth:
                    for open_row in range(row - 1, -1, -1):
                        if parens[open_row]:
                            break
                else:
                    open_row = 0

                # That's all we get to work with. This code attempts to
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
                if (indent_next and vi[0] == indent_level + 4 and
                        nrows == row + 1):
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

                # Returning to original continuation_line_indentation() from
                # pep8.
                visual_indent = indent_chances.get(start[1])
                last_indent = start
                rel_indent[row] = start[1] - indent_level
                hang = rel_indent[row] - rel_indent[open_row]

                if token_type == tokenize.OP and text in ']})':
                    pass
                elif visual_indent is True:
                    if not indent[depth]:
                        indent[depth] = start[1]

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

        return valid_indents


def _leading_space_count(line):
    """Return number of leading spaces in line."""
    i = 0
    while i < len(line) and line[i] == ' ':
        i += 1
    return i


def refactor_with_2to3(source_text, fixer_name):
    """Use lib2to3 to refactor the source.

    Return the refactored source code.

    """
    from lib2to3 import refactor
    fixers = ['lib2to3.fixes.fix_' + fixer_name]
    tool = refactor.RefactoringTool(
        fixer_names=fixers,
        explicit=fixers)
    return unicode(tool.refactor_string(source_text, name=''))


def break_multi_line(source_text, newline, indent_word, max_line_length):
    """Break first line of multi-line code.

    Return None if a break is not possible.

    """
    # Handle special case only.
    for symbol in '([{':
        # Only valid if symbol is not on a line by itself.
        if (symbol in source_text
                and source_text.rstrip().endswith(',')
                and not source_text.lstrip().startswith(symbol)):
            index = 1 + source_text.find(symbol)
            if index >= max_line_length:
                return None

            # Make sure we are not in a string.
            for quote in ['"', "'"]:
                if quote in source_text:
                    if source_text.find(quote) < index:
                        return None

            # Make sure we are not in a comment.
            if '#' in source_text:
                if source_text.find('#') < index:
                    return None

            assert index < len(source_text)
            return (
                source_text[:index].rstrip() + newline +
                _get_indentation(source_text) + indent_word +
                source_text[index:].lstrip())

    return None


def check_syntax(code):
    """Return True if syntax is okay."""
    try:
        return compile(code, '<string>', 'exec')
    except (SyntaxError, TypeError, UnicodeDecodeError):
        return False


def filter_results(source, results, aggressive=False):
    """Filter out spurious reports from pep8.

    If aggressive is True, we allow possibly unsafe fixes (E711, E712).

    """
    non_docstring_string_line_numbers = multiline_string_lines(
        source, include_docstrings=False)
    all_string_line_numbers = multiline_string_lines(
        source, include_docstrings=True)

    split_source = [None] + source.splitlines()

    for r in results:
        issue_id = r['id'].lower()

        if r['line'] in non_docstring_string_line_numbers:
            if issue_id.startswith('e1'):
                continue
            elif issue_id in ['e501', 'w191']:
                continue

        if r['line'] in all_string_line_numbers:
            if issue_id in ['e501']:
                continue

        # Filter out incorrect E101 reports when there are no tabs.
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multi-line string.
        if issue_id == 'e101' and '\t' not in split_source[r['line']]:
            continue

        if issue_id in ['e711', 'e712'] and not aggressive:
            continue

        yield r


def multiline_string_lines(source, include_docstrings=False):
    """Return line numbers that are within multiline strings.

    The line numbers are indexed at 1.

    Docstrings are ignored.

    """
    sio = StringIO(source)
    line_numbers = set()
    previous_token_type = ''
    try:
        for t in tokenize.generate_tokens(sio.readline):
            token_type = t[0]
            start_row = t[2][0]
            end_row = t[3][0]
            start_row = t[2][0]
            end_row = t[3][0]

            if (token_type == tokenize.STRING and start_row != end_row):
                if (include_docstrings or
                        previous_token_type != tokenize.INDENT):
                    # We increment by one since we want the contents of the
                    # string.
                    line_numbers |= set(range(1 + start_row, 1 + end_row))

            previous_token_type = token_type
    except (IndentationError, tokenize.TokenError):
        pass

    return line_numbers


def shorten_comment(line, newline, max_line_length):
    """Return trimmed or split long comment line."""
    assert len(line) > max_line_length
    line = line.rstrip()

    # PEP 8 recommends 72 characters for comment text.
    indentation = _get_indentation(line) + '# '
    max_line_length = min(max_line_length,
                          len(indentation) + 72)

    MIN_CHARACTER_REPEAT = 5
    if (len(line) - len(line.rstrip(line[-1])) >= MIN_CHARACTER_REPEAT and
            not line[-1].isalnum()):
        # Trim comments that end with things like ---------
        return line[:max_line_length] + newline
    elif re.match(r'\s*#+\s*\w+', line):
        import textwrap
        split_lines = textwrap.wrap(line.lstrip(' \t#'),
                                    initial_indent=indentation,
                                    subsequent_indent=indentation,
                                    width=max_line_length,
                                    break_long_words=False)
        return newline.join(split_lines) + newline
    else:
        return line + newline


def format_block_comments(source):
    """Format block comments."""
    if '#' not in source:
        # Optimization.
        return source

    string_line_numbers = multiline_string_lines(source,
                                                 include_docstrings=True)
    fixed_lines = []
    sio = StringIO(source)
    for (line_number, line) in enumerate(sio.readlines(), start=1):
        if (re.match(r'\s*#+\w+', line) and
                line_number not in string_line_numbers):
            fixed_lines.append(_get_indentation(line) +
                               '# ' +
                               line.lstrip().lstrip('#'))
        else:
            fixed_lines.append(line)

    return ''.join(fixed_lines)


def normalize_line_endings(lines):
    """Return fixed line endings.

    All lines will be modified to use the most common line ending.

    """
    newline = find_newline(lines)
    return [line.rstrip('\n\r') + newline for line in lines]


def mutual_startswith(a, b):
    return b.startswith(a) or a.startswith(b)


def code_match(code, select, ignore):
    if ignore:
        for ignored_code in [c.strip() for c in ignore.split(',')]:
            if mutual_startswith(code.lower(), ignored_code.lower()):
                return False

    if select:
        for selected_code in [c.strip() for c in select.split(',')]:
            if mutual_startswith(code.lower(), selected_code.lower()):
                return True
        return False

    return True


def fix_file(filename, opts=None, output=None):
    if not opts:
        opts = parse_args([filename])[0]

    original_source = read_from_filename(filename, readlines=True)

    tmp_source = unicode().join(normalize_line_endings(original_source))

    fix = FixPEP8(filename, opts, contents=tmp_source)
    fixed_source = fix.fix()
    tmp_filename = filename
    if not pep8 or opts.in_place:
        encoding = detect_encoding(filename)

    if code_match('e26', select=opts.select, ignore=opts.ignore):
        fixed_source = format_block_comments(fixed_source)

    interruption = None
    try:
        # Keep a history to break out of cycles.
        previous_hashes = set([hash(tmp_source)])

        for _ in range(opts.pep8_passes):
            if hash(fixed_source) in previous_hashes:
                break
            else:
                previous_hashes.add(hash(fixed_source))

            tmp_source = copy.copy(fixed_source)

            if not pep8:
                (_tmp_open_file, tmp_filename) = tempfile.mkstemp()
                os.close(_tmp_open_file)
                fp = open_with_encoding(tmp_filename,
                                        encoding=encoding, mode='w')
                fp.write(fixed_source)
                fp.close()
            fix = FixPEP8(tmp_filename, opts, contents=tmp_source)
            fixed_source = fix.fix()
            if not pep8:
                os.remove(tmp_filename)
    except KeyboardInterrupt as exception:
        # Allow stopping early.
        interruption = exception
    del tmp_filename
    del tmp_source

    if opts.diff:
        new = StringIO(fixed_source)
        new = new.readlines()
        diff = _get_difftext(original_source, new, filename)
        if output:
            output.write(diff)
        else:
            return output
    elif opts.in_place:
        fp = open_with_encoding(filename, encoding=encoding,
                                mode='w')
        fp.write(fixed_source)
        fp.close()
    else:
        if output:
            output.write(fixed_source)
        else:
            return fixed_source

    if interruption:
        raise interruption


def parse_args(args):
    """Parse command-line options."""
    parser = OptionParser(usage='Usage: autopep8 [options] '
                                '[filename [filename ...]]'
                                '\nUse filename \'-\'  for stdin.',
                          version='autopep8: %s' % __version__,
                          description=__doc__,
                          prog='autopep8')
    parser.add_option('-v', '--verbose', action='count', dest='verbose',
                      default=0,
                      help='print verbose messages; '
                           'multiple -v result in more verbose messages')
    parser.add_option('-d', '--diff', action='store_true', dest='diff',
                      help='print the diff for the fixed source')
    parser.add_option('-i', '--in-place', action='store_true',
                      help='make changes to files in place')
    parser.add_option('-r', '--recursive', action='store_true',
                      help='run recursively; must be used with --in-place or '
                           '--diff')
    parser.add_option('-p', '--pep8-passes',
                      default=100, type=int,
                      help='maximum number of additional pep8 passes'
                           ' (default: %default)')
    parser.add_option('--list-fixes', action='store_true',
                      help='list codes for fixes; '
                           'used by --ignore and --select')
    parser.add_option('--ignore', default='',
                      help='do not fix these errors/warnings (e.g. E4,W)')
    parser.add_option('--select', default='',
                      help='fix only these errors/warnings (e.g. E4,W)')
    parser.add_option('--max-line-length', default=79, type=int,
                      help='set maximum allowed line length '
                           '(default: %default)')
    parser.add_option('--aggressive', action='store_true',
                      help='enable possibly unsafe changes (E711, E712)')
    opts, args = parser.parse_args(args)

    if not len(args) and not opts.list_fixes:
        parser.error('incorrect number of arguments')

    if '-' in args and len(args) > 1:
        parser.error('cannot mix stdin and regular files')

    if len(args) > 1 and not (opts.in_place or opts.diff):
        parser.error('autopep8 only takes one filename as argument '
                     'unless the "--in-place" or "--diff" options are '
                     'used')

    if opts.recursive and not (opts.in_place or opts.diff):
        parser.error('--recursive must be used with --in-place or --diff')

    if opts.in_place and opts.diff:
        parser.error('--in-place and --diff are mutually exclusive')

    if opts.max_line_length < 8:
        parser.error('--max-line-length must greater than 8')

    if args == ['-'] and (opts.in_place or opts.recursive):
        parser.error('--in-place or --recursive cannot be used with '
                     'standard input')

    return opts, args


def supported_fixes():
    """Yield pep8 error codes that autopep8 fixes.

    Each item we yield is a tuple of the code followed by its description.

    """
    instance = FixPEP8(filename=None, options=None, contents='')
    for attribute in dir(instance):
        code = re.match('fix_([ew][0-9][0-9][0-9])', attribute)
        if code:
            yield (code.group(1).upper(),
                   re.sub(r'\s+', ' ',
                          getattr(instance, attribute).__doc__))

class LineEndingWrapper(object):

    r"""Replace line endings to work with sys.stdout.

    It seems that sys.stdout expects only '\n' as the line ending, no matter
    the platform. Otherwise, we get repeated line endings.

    """

    def __init__(self, output):
        self.__output = output

    def write(self, s):
        self.__output.write(s.replace('\r\n', '\n').replace('\r', '\n'))

    def __getattr__(self, key):
        return getattr(self.__output, key)


def main():
    """Tool main."""
    opts, args = parse_args(sys.argv[1:])

    if opts.list_fixes:
        for code, description in supported_fixes():
            print('{code} - {description}'.format(
                code=code, description=description))
        return 0

    if opts.in_place or opts.diff:
        filenames = list(set(args))
    else:
        assert len(args) == 1
        assert not opts.recursive
        if args == ['-']:
            assert not opts.in_place
            temp = tempfile.NamedTemporaryFile()
            temp.write(sys.stdin.read())
            temp.flush()
            filenames = [temp.name]
        else:
            filenames = args[:1]

    output = codecs.getwriter('utf-8')(sys.stdout.buffer
                                       if sys.version_info[0] >= 3
                                       else sys.stdout)

    output = LineEndingWrapper(output)

    while filenames:
        name = filenames.pop(0)
        if opts.recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                for d in directories:
                    if d.startswith('.'):
                        directories.remove(d)
        else:
            if opts.verbose:
                print('[file:%s]' % name, file=sys.stderr)
            try:
                fix_file(name, opts, output)
            except IOError as error:
                print(str(error), file=sys.stderr)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)

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

from distutils.version import LooseVersion
try:
    import pep8
    if LooseVersion(pep8.__version__) < LooseVersion('0.5.1'):
        pep8 = None
except ImportError:
    pep8 = None


__version__ = '0.6.5'


PEP8_BIN = 'pep8'
PEP8_PASSES_MAX = 100
CR = '\r'
LF = '\n'
CRLF = '\r\n'
MAX_LINE_WIDTH = 79


def open_with_encoding(filename, encoding, mode='r'):
    """Open file with a specific encoding."""
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
            with open(filename, encoding=encoding) as input_file:
                input_file.read()

            return encoding
        except (SyntaxError, LookupError, UnicodeDecodeError):
            return 'latin-1'
    except AttributeError:
        return 'utf-8'


def read_from_filename(filename, readlines=False):
    """Simple open file, read contents, close file.

    Ensures file gets closed without relying on CPython GC.
    Jython requires files to be closed.

    """
    with open_with_encoding(filename,
                            encoding=detect_encoding(filename)) as input_file:
        return input_file.readlines() if readlines else input_file.read()


class FixPEP8(object):

    """Fix invalid code.

    [fixed method list]
        - e111
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
        self.newline = _find_newline(self.source)
        self.options = options
        self.indent_word = _get_indentword("".join(self.source))
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

    def _pep8_options(self, targetfile):
        """Return options to be passed to pep8."""
        return (["--repeat", targetfile] +
                (["--ignore=" + self.options.ignore]
                 if self.options.ignore else []) +
                (["--select=" + self.options.select]
                 if self.options.select else []))

    def _fix_source(self, results):
        completed_lines = []
        for result in sorted(results, key=_priority_key):
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
        pep8_options = self._pep8_options(self.filename)
        if pep8:
            results = _execute_pep8(pep8_options, self.source)
        else:
            results = _spawn_pep8(pep8_options)
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
        target = self.source[result['line'] - 1]
        target_char = result['info'].split()[-1][1]
        fixed = ""
        fixed_end = 0
        for i in re.finditer("%s\S" % target_char, target):
            fixed += target[fixed_end:i.start()] + "%s " % target_char
            fixed_end = i.end() - 1
        fixed += target[fixed_end:]
        self.source[result['line'] - 1] = fixed

    def fix_e251(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column'] - 1
        fixed = target[:c] + re.sub(r'\s*=\s*', '=', target[c:], 1)

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
                                       self.indent_word, reverse=False,
                                       newline=self.newline)
            candidate1 = _shorten_line(_tokens, source, target, indent,
                                       self.indent_word, reverse=True,
                                       newline=self.newline)
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

    def fix_w292(self, _):
        self.source[-1] += self.newline

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
        self.source[result['line'] - 1] = re.sub('<>', '!=', target)

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


def _find_newline(source):
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
    non_whitespace_index = len(line) - len(line.lstrip())
    return line[:non_whitespace_index]


def _split_indentation(line):
    """Split into tuple (indentation, rest)."""
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
                'e702']  # Break multiline statements early
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


def _shorten_line(tokens, source, target, indentation, indent_word,
                  reverse=False, newline=LF):
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
                      source[offset - len(indentation):])
            if not second.strip():
                continue
            # Don't modify if lines are not short enough
            if len(first) > MAX_LINE_WIDTH or len(second) > MAX_LINE_WIDTH:
                continue
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
    pep8.process_options(['pep8'] + pep8_options)

    class QuietChecker(pep8.Checker):

        """Version of checker that does not print."""

        def __init__(self, filename, lines):
            pep8.Checker.__init__(self, filename, lines=lines)
            self.__results = None

        def report_error(self, line_number, offset, text, check):
            """Collect errors."""
            code = text[:4]
            if not pep8.ignore_code(code):
                self.__results.append(
                    dict(id=text.split()[0], line=line_number,
                         column=offset + 1, info=text))

        def check_all(self, expected=None, line_offset=0):
            """Check code and return results."""
            self.__results = []
            pep8.Checker.check_all(self, expected, line_offset)
            return self.__results

    checker = QuietChecker('', lines=source)
    return checker.check_all()


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
            have = _getlspace(lines[thisstmt])
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
                                if have == _getlspace(lines[jline]):
                                    want = jlevel * 4
                                break
                    if want < 0:           # Maybe it's a hanging
                                           # comment like this one,
                        # in which case we should shift it like its base
                        # line got shifted.
                        for j in range(i - 1, -1, -1):
                            jline, jlevel = stats[j]
                            if jlevel >= 0:
                                want = (have + _getlspace(after[jline - 1]) -
                                        _getlspace(lines[jline]))
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
                        remove = min(_getlspace(line), -diff)
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

    def tokeneater(self, token_type, _, start, __, line,
                   INDENT=tokenize.INDENT,
                   DEDENT=tokenize.DEDENT,
                   NEWLINE=tokenize.NEWLINE,
                   COMMENT=tokenize.COMMENT,
                   NL=tokenize.NL):
        """Line-eater for tokenize."""
        sline = start[0]
        if token_type == NEWLINE:
            # A program statement, or ENDMARKER, will eventually follow,
            # after some (possibly empty) run of tokens of the form
            #     (NL | COMMENT)* (INDENT | DEDENT+)?
            self.find_stmt = 1

        elif token_type == INDENT:
            self.find_stmt = 1
            self.level += 1

        elif token_type == DEDENT:
            self.find_stmt = 1
            self.level -= 1

        elif token_type == COMMENT:
            if self.find_stmt:
                self.stats.append((sline, -1))
                # but we're still looking for a new stmt, so leave
                # find_stmt alone

        elif token_type == NL:
            pass

        elif self.find_stmt:
            # This is the first "real token" following a NEWLINE, so it
            # must be the first token of the next program statement, or an
            # ENDMARKER.
            self.find_stmt = 0
            if line:   # not endmarker
                self.stats.append((sline, self.level))


def _getlspace(line):
    """Count number of leading blanks."""
    i = 0
    while i < len(line) and line[i] == " ":
        i += 1
    return i


def fix_file(filename, opts, output=sys.stdout):
    tmp_source = read_from_filename(filename)
    fix = FixPEP8(filename, opts, contents=tmp_source)
    fixed_source = fix.fix()
    original_source = copy.copy(fix.original_source)
    tmp_filename = filename
    for _ in range(opts.pep8_passes):
        if fixed_source == tmp_source:
            break
        tmp_source = copy.copy(fixed_source)
        if not pep8:
            tmp_filename = tempfile.mkstemp()[1]
            fp = open(tmp_filename, 'w')
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
        fp = open_with_encoding(filename, encoding=detect_encoding(filename),
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

    return opts, args


def main():
    """Tool main."""
    opts, args = parse_args(sys.argv[1:])
    try:
        if opts.in_place or opts.diff:
            for f in set(args):
                if opts.verbose and len(args) > 1:
                    sys.stderr.write('[file:%s]\n' % f)
                fix_file(f, opts)
        else:
            fix_file(args[0], opts)
    except IOError as error:
        sys.stderr.write(str(error) + '\n')
        return 1


if __name__ == '__main__':
    sys.exit(main())

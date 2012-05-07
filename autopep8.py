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

try:
    import pep8
    if not pep8.__version__ >= '0.5.1':
        pep8 = None
except ImportError:
    pep8 = None


__version__ = '0.6'


pep8bin = 'pep8'
PEP8_PASSES_MAX = 100
CR = '\r'
LF = '\n'
CRLF = '\r\n'


def read_from_filename(filename, readlines=False):
    """Simple open file, read contents, close file.
    Ensures file gets closed without relying on CPython GC.
    Jython requires files to be closed.
    """
    f = open(filename)
    try:
        return f.readlines() if readlines else f.read()
    finally:
        f.close()


class FixPEP8(object):
    """fix invalid code

    [fixed method list]
        - e111
        - e201,e202,e203
        - e211
        - e221,e222,e223,e224,e225
        - e231
        - e251
        - e261,e262
        - e301,e302,e303
        - e401
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
        self.results = []
        self.options = options
        self.indent_word = _get_indentword("".join(self.source))
        # method definition
        self.fix_e111 = self.fix_e101
        self.fix_e222 = self.fix_e221
        self.fix_e223 = self.fix_e221
        self.fix_e241 = self.fix_e221
        self.fix_e242 = self.fix_e224
        self.fix_w191 = self.fix_e101

    def _spawn_pep8(self, targetfile):
        """execute pep8 via subprocess.Popen."""
        paths = os.environ['PATH'].split(':')
        for path in paths:
            if os.path.exists(os.path.join(path, pep8bin)):
                cmd = ([os.path.join(path, pep8bin)] +
                       self._pep8_options(targetfile))
                p = Popen(cmd, stdout=PIPE)
                return p.stdout.readlines()
        raise Exception("'%s' is not found." % pep8bin)

    def _execute_pep8(self, targetfile):
        """execute pep8 via python method calls."""
        pep8.options, pep8.args = \
                pep8.process_options(['pep8'] + self._pep8_options(targetfile))
        sys_stdout = sys.stdout
        fake_stdout = StringIO()
        sys.stdout = fake_stdout
        tmp_checker = pep8.Checker(self.filename, lines=self.source)
        tmp_checker.check_all()
        sys.stdout = sys_stdout
        result = fake_stdout.getvalue()
        return StringIO(result).readlines()

    def _pep8_options(self, targetfile):
        """return options to be passed to pep8."""
        return (["-r", targetfile] +
                (["--ignore=" + self.options.ignore]
                 if self.options.ignore else []))

    def _fix_source(self):
        completed_lines = []
        for result in sorted(self.results, key=_priority_key):
            if result['line'] in completed_lines:
                continue
            fixed_methodname = "fix_%s" % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)
                modified_lines = fix(result)
                if modified_lines:
                    completed_lines += modified_lines
                if self.options.verbose:
                    if modified_lines == []:
                        sys.stderr.write('Not fixing {f} on line {l}\n'.format(
                                f=result['id'], l=result['line']))
                completed_lines.append(result['line'])
            else:
                if self.options.verbose:
                    sys.stderr.write("'%s' is not defined.\n" % \
                            fixed_methodname)
                    info = result['info'].strip()
                    sys.stderr.write("%s:%s:%s:%s\n" % (result['filename'],
                                                        result['line'],
                                                        result['column'],
                                                        info))

    def _fix_whitespace(self, result, pattern, repl):
        (indent, rest) = _split_indentation(self.source[result['line'] - 1])
        fixed = re.sub(pattern, repl, rest)
        self.source[result['line'] - 1] = indent + fixed

    def fix(self):
        if pep8:
            pep8result = self._execute_pep8(self.filename)
        else:
            pep8result = self._spawn_pep8(self.filename)
        self.results = [_analyze_pep8result(line) for line in pep8result]
        self._fix_source()
        return "".join(self.source)

    def fix_e101(self, _):
        """Reindent all lines."""
        reindenter = Reindenter(self.source)
        if reindenter.run():
            self.source = reindenter.fixed_lines()
            return range(len(self.source))
        else:
            return []

    def fix_e201(self, result):
        self._fix_whitespace(result, r"\(\s+", "(")
        self._fix_whitespace(result, r"\[\s+", "[")
        self._fix_whitespace(result, r"{\s+", "{")

    def fix_e202(self, result):
        self._fix_whitespace(result, r"\s+\)", ")")
        self._fix_whitespace(result, r"\s+\]", "]")
        self._fix_whitespace(result, r"\s+}", "}")

    def fix_e203(self, result):
        self._fix_whitespace(result, r"\s+:", ":")
        self._fix_whitespace(result, r"\s+,", ",")

    def fix_e211(self, result):
        self._fix_whitespace(result, r"\s+\(", "(")
        self._fix_whitespace(result, r"\s+\[", "[")

    def fix_e221(self, result):
        """e221, e222 and e223 fixed method"""
        target = self.source[result['line'] - 1]
        c = result['column'] + 1
        fixed = re.sub(r'\s+', ' ', target[c::-1], 1)[::-1] + target[c + 1:]
        if fixed == target:
            # for e223 fixed method
            fixed = re.sub(r'\t+', ' ', target[c::-1], 1)[::-1] + \
                    target[c + 1:]
        self.source[result['line'] - 1] = fixed

    def fix_e224(self, result):
        target = self.source[result['line'] - 1]
        offset = result['column'] - 1
        fixed = target[:offset] + target[offset:].replace('\t', ' ')
        self.source[result['line'] - 1] = fixed

    def fix_e225(self, result):
        target = self.source[result['line'] - 1]
        offset = result['column']
        fixed = target[:offset - 1] + " " + target[offset - 1:]

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
        target = self.source[result['line'] - 1]
        c = result['column'] - 1
        fixed = target[:c] + re.sub(r'\s*=\s*', '=', target[c:], 1)
        self.source[result['line'] - 1] = fixed

    def fix_e261(self, result):
        target = self.source[result['line'] - 1]
        c = result['column']

        # pep8 is sometimes off by one in cases like "{# comment"
        if target[c] == '#':
            pass
        elif target[c - 1] == '#':
            c = c - 1
        else:
            return

        fixed = target[:c] + " " + target[c:]
        self.source[result['line'] - 1] = fixed

    def fix_e262(self, result):
        target = self.source[result['line'] - 1]
        split = target.rsplit('#', 1)

        assert len(split) == 2
        comment = split[1].lstrip()
        fixed = split[0].rstrip(' \t#') + ('  # ' + comment if comment else '')

        self.source[result['line'] - 1] = fixed

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
                modified_lines.append(line)
                cnt += 1
            line -= 1

        return modified_lines

    def fix_e401(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]

        # Take care of semicolons first
        if target.rstrip().endswith(';'):
            self.source[line_index] = _fix_multiple_statements(target,
                                                               self.newline)
        else:
            indentation = target.split("import ")[0]
            modules = target.split("import ")[1].split(",")
            fixed_modulelist = \
                    [indentation + "import %s" % m.lstrip() for m in modules]
            self.source[line_index] = self.newline.join(fixed_modulelist)

    def fix_e701(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]
        c = result['column']

        fixed_source = target[:c] + self.newline + \
                       _get_indentation(target) + self.indent_word + \
                       target[c:].lstrip()
        self.source[result['line'] - 1] = fixed_source

    def fix_e702(self, result):
        target = self.source[result['line'] - 1]
        if '"""' in target:
            # We currently do not support things like
            #     """
            #         hello
            #       """; foo()
            return []
        self.source[result['line'] - 1] = _fix_multiple_statements(target,
                self.newline)

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
        found_notblank = False
        blank_count = 0
        for line in source:
            line = line.rstrip()
            if re.match("^$", line):
                blank_count += 1
            else:
                found_notblank = True
            if found_notblank and not re.match("^$", line):
                break
        source = source[blank_count:]
        source.reverse()
        self.source = source

    def fix_w601(self, result):
        target = self.source[result['line'] - 1]
        _before = ""
        _after = ""
        _symbol = ""

        # Skip complicated cases
        if target.count('(') > 1 or target.count(')') > 1:
            return

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
        line_index = result['line'] - 1
        line = self.source[line_index]

        split_line = line.split(',')
        if len(split_line) > 1 and split_line[1].strip().startswith('('):
            # Give up
            return []

        if line.rstrip().endswith(';'):
            # Take care of semicolons first
            self.source[line_index] = _fix_multiple_statements(line,
                                                               self.newline)
            return
        elif line[-2:] == '\\\n':
            # Remove escaped LF first
            self.source[line_index] = line[:-2]
            return
        elif line[-3:] == '\\\r\n':
            # Remove escaped CRLF first
            self.source[line_index] = line[:-3]
            return
        elif line[-2:] == '\\\r':
            # Remove escaped CR first
            # NOTE: Doesn't get executed because pep8 doesn't seem to work with
            #       CR line endings
            self.source[line_index] = line[:-2]
            return

        modified_lines = [line_index]

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
                modified_lines.append(i)
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
        self.source[result['line'] - 1] = \
            ''.join([indentation, 'raise ', exception_type,
                     '(',
                     args[1:-1] if args.startswith('(') else args,
                     ')',
                     comment, self.newline])

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
    for t in tokenize.generate_tokens(sio.readline):
        if t[0] == token.INDENT:
            indent_word = t[1]
            break
    return indent_word


def _get_indentation(line):
    non_whitespace_index = len(line) - len(line.lstrip())
    return line[:non_whitespace_index]


def _split_indentation(line):
    """Split into tuple (indentation, rest)."""
    non_whitespace_index = len(line) - len(line.lstrip())
    return (line[:non_whitespace_index], line[non_whitespace_index:])


def _fix_multiple_statements(target, newline):
    f = [_get_indentation(target) + t.strip()
         for t in target.split(";") if t.strip()]
    return newline.join(f) + newline


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
    difftext = [line for line in diff]
    return "".join(difftext)


def _priority_key(pep8_result):
    """Key for sorting PEP8 results.
    Global fixes should be done first. This is important for things
    like indentation.
    """
    high_priority = ['e101', 'e111', 'w191']
    return pep8_result['id'].lower() not in high_priority


class Reindenter:
    """Reindents badly-indented code to uniformly use four-space indentation.
    Released to the public domain, by Tim Peters, 03 October 2000."""
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
        for t in tokens:
            self.tokeneater(*t)
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
                                want = have + _getlspace(after[jline - 1]) - \
                                       _getlspace(lines[jline])
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


def fix_file(filename, opts):
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
        new = StringIO("".join(fix.source))
        new = new.readlines()
        sys.stdout.write(_get_difftext(original_source, new,
                                       filename))
    elif opts.in_place:
        fp = open(filename, 'w')
        fp.write(fixed_source)
        fp.close()
    else:
        sys.stdout.write(fixed_source)


def main():
    """tool main"""
    parser = OptionParser(version="autopep8: %s" % __version__,
                          description=__doc__)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                      help='print to verbose result.')
    parser.add_option('-d', '--diff', action='store_true', dest='diff',
                      help='diff print of fixed source.')
    parser.add_option('-i', '--in-place', action='store_true',
                      help='make changes to files in place')
    parser.add_option('-p', '--pep8-passes',
                      default=PEP8_PASSES_MAX, type='int',
                      help='maximum number of additional pep8 passes'
                           ' (default:%d)' % PEP8_PASSES_MAX)
    parser.add_option('--ignore', default='',
                      help='do not fix these errors/warnings (e.g. E4,W)')
    opts, args = parser.parse_args()
    if not len(args):
        print(parser.format_help())
        return 1

    if opts.in_place:
        for f in args:
            fix_file(f, opts)
    else:
        fix_file(args[0], opts)


if __name__ == '__main__':
    sys.exit(main())

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

try:
    import pep8
    if not pep8.__version__ >= '0.5.1':
        pep8 = None
except ImportError:
    pep8 = None


__version__ = '0.5.1'


pep8bin = 'pep8'
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
        self.fix_e222 = self.fix_e221
        self.fix_e223 = self.fix_e221

    def _get_indentlevel(self, line):
        sio = StringIO(line)
        indent_word = ""
        for t in tokenize.generate_tokens(sio.readline):
            if t[0] == token.INDENT:
                indent_word = t[1]
                break
        import math
        indent_level = int(math.ceil(float(len(indent_word)) /
                                     len(self.indent_word)))
        return indent_level + 1

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
        for result in self.results:
            if result['line'] in completed_lines:
                continue
            fixed_methodname = "fix_%s" % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)
                modified_lines = fix(result)
                if modified_lines:
                    completed_lines += modified_lines
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
        target = self.source[result['line'] - 1]
        fixed = re.sub(pattern, repl, target)
        self.source[result['line'] - 1] = fixed

    def fix(self):
        if pep8:
            pep8result = self._execute_pep8(self.filename)
        else:
            pep8result = self._spawn_pep8(self.filename)
        self.results = [_analyze_pep8result(line) for line in pep8result]
        self._fix_source()
        return "".join(self.source)

    #def fix_e101(self, result):
    #    target = self.source[result['line'] - 1]
    #    offset = result['column'] - 1
    #    if target[offset] == '\t':
    #        fixed = self.indent_word + target[offset + 1:]
    #    else:
    #        # FIXME: not implement
    #        fixed = target
    #    self.source[result['line'] - 1] = fixed

    def fix_e111(self, result):
        sio = StringIO("".join(self.source[result['line'] - 1:]))
        last_line = ""
        diff_cnt = 0
        fixed_lines = []
        for tokens in tokenize.generate_tokens(sio.readline):
            if tokens[0] == token.INDENT:
                _level = self._get_indentlevel(tokens[4])
                diff_cnt = 4 * (_level - 1) - len(tokens[1])
            if tokens[0] == token.DEDENT:
                break
            if tokens[4] != last_line:
                last_line = tokens[4]
                if diff_cnt >= 0:
                    fixed_lines.append(" " * diff_cnt + tokens[4])
                else:
                    fixed_lines.append(tokens[4][abs(diff_cnt):])
        for offset, fixed_line in enumerate(fixed_lines):
            self.source[result['line'] - 1 + offset] = fixed_line

        # Mark everything as modified since we don't want other instances of
        # E111 fixes to interfere with this fix.
        return range(len(self.source))

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
        fixed = re.sub(r'\t+', ' ', target, 1)
        self.source[result['line'] - 1] = fixed

    def fix_e225(self, result):
        target = self.source[result['line'] - 1]
        offset = result['column']
        fixed = target[:offset - 1] + " " + target[offset - 1:]

        # Only proceed if non-whitespace characters match
        if fixed.replace(' ', '') == target.replace(' ', ''):
            self.source[result['line'] - 1] = fixed

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
        if ';' in target:
            self.source[line_index] = _fix_multiple_statements(target,
                                                               self.newline)
        else:
            indentation = target.split("import ")[0]
            modules = target.split("import ")[1].split(",")
            fixed_modulelist = \
                    [indentation + "import %s" % m.lstrip() for m in modules]
            self.source[line_index] = self.newline.join(fixed_modulelist)

    def fix_e701(self, result):
        target = self.source[result['line'] - 1]
        c = result['column']
        indent_level = self._get_indentlevel(target)
        fixed_source = target[:c] + self.newline + \
                       self.indent_word * indent_level + target[c:].lstrip()
        self.source[result['line'] - 1] = fixed_source

    def fix_e702(self, result):
        target = self.source[result['line'] - 1]
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

        if ';' in line:
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

        # Skip cases with multiple arguments as to not handle tracebacks
        # incorrectly in cases such as "raise Exception, Value, Traceback".
        if line.count(',') - line.count(',)') > 1:
            # TODO: Don't Care corner cases.
            import ast
            indent = (self._get_indentlevel(line) - 1) * self.indent_word
            indent_offset = (self._get_indentlevel(line) - 1) * \
                    len(self.indent_word)
            ast_body = ast.parse(line[indent_offset:]).body[0]
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
                _id.append(repr(ast.literal_eval(node)))
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
            # create to fixed source
            self.source[result['line'] - 1] = "%sraise %s(%s), None, %s%s" % (
                    tuple(_id))
            return modified_lines

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
        if len(re.findall('`+', target)) > 2:
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


def _fix_multiple_statements(target, newline):
    non_whitespace_index = len(target) - len(target.lstrip())
    indentation = target[:non_whitespace_index]
    f = [indentation + t.strip() for t in target.split(";") if t.strip()]
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
    parser.add_option('-p', '--pep8-passes', default=20, type='int',
                      help='maximum number of additional pep8 passes')
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

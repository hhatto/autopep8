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
    from StringIO import StringIO
import token
import tokenize
from optparse import OptionParser
from subprocess import Popen, PIPE
from difflib import unified_diff
import tempfile

__version__ = '0.3'


pep8bin = 'pep8'
CR = '\r'
LF = '\n'
CRLF = '\r\n'


class FixPEP8(object):

    """fix invalid code

    [fixed method list]
        - e201,e202,e203
        - e211
        - e221,e225
        - e231
        - e251
        - e261,e262
        - e301,e302,e303
        - e401
        - e701,e702
        - w291,w293
        - w391
        - w602
    """
    def __init__(self, filename, options):
        self.filename = filename
        self.source = open(filename).readlines()
        self.original_source = copy.copy(self.source)
        self.newline = self._find_newline(self.source)
        self.results = []
        self.options = options
        self.indent_word = self._get_indentword("".join(self.source))
        # method definition
        self.fix_e222 = self.fix_e221

    def _find_newline(self, source):
        cr, lf, crlf = 0, 0, 0
        for s in source:
            if CRLF in s:
                crlf += 1
            elif CR in s:
                cr += 0
            elif LF in s:
                lf += 0
        _max = max(cr, crlf, lf)
        if _max == lf:
            return LF
        elif _max == crlf:
            return CRLF
        elif _max == cr:
            return CR
        else:
            return LF

    def _get_indentword(self, source):
        sio = StringIO(source)
        indent_word = "    "  # Default in case source has no indentation
        for t in tokenize.generate_tokens(sio.readline):
            if t[0] == token.INDENT:
                indent_word = t[1]
                break
        return indent_word

    def _get_indentlevel(self, line):
        sio = StringIO(line)
        indent_word = ""
        for t in tokenize.generate_tokens(sio.readline):
            if t[0] == token.INDENT:
                indent_word = t[1]
                break
        indent_level = len(indent_word) / len(self.indent_word)
        return indent_level + 1

    def _analyze_pep8result(self, result):
        tmp = result.split(":")
        filename = tmp[0]
        line = int(tmp[1])
        column = int(tmp[2])
        info = " ".join(result.split()[1:])
        pep8id = info.lstrip().split()[0]
        return dict(id=pep8id, filename=filename, line=line,
                    column=column, info=info)

    def _execute_pep8(self, targetfile):
        """execute pep8 via subprocess.Popen."""
        paths = os.environ['PATH'].split(':')
        paths.reverse()
        for path in paths:
            if os.path.exists(path + '/' + pep8bin):
                cmd = "%s/%s -r %s" % (path, pep8bin, targetfile)
                p = Popen(cmd, stdout=PIPE, shell=True)
                return p.stdout.readlines()
        raise Exception("'%s' is not found." % pep8bin)

    def _fix_source(self):
        for result in self.results:
            fixed_methodname = "fix_%s" % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)
                fix(result)
            else:
                print >> sys.stderr, "'%s' is not defined." % fixed_methodname
                if self.options.verbose:
                    info = result['info'].strip()
                    print >> sys.stderr, "%s:%s:%s:%s" % (result['filename'],
                                                          result['line'],
                                                          result['column'],
                                                          info)

    def _fix_whitespace(self, result, pattern, repl):
        target = self.source[result['line'] - 1]
        fixed = re.sub(pattern, repl, target)
        self.source[result['line'] - 1] = fixed

    def fix(self):
        pep8result = self._execute_pep8(self.filename)
        raw_results = [self._analyze_pep8result(line) for line in pep8result]

        # Only handle one error per line
        line_results = {}
        for result in raw_results:
            line_results[result['line']] = result

        self.results = line_results.values()

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
        """e221 and e222 fixed method"""
        target = self.source[result['line'] - 1]
        c = result['column'] + 1
        fixed = re.sub(r'\s+', ' ', target[c::-1], 1)[::-1] + target[c + 1:]
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

        # pep8 is sometiems off by one in cases like "{# comment"
        if target[c] == '#':
            pass
        elif target[c - 1] == '#':
            c = c - 1
        else:
            return

        fixed = target[:c] + " " + target[c:]
        self.source[result['line'] - 1] = fixed

    def fix_e262(self, result):
        self._fix_whitespace(result, r"##* *", "# ")

    def fix_e301(self, result):
        cr = self.newline
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e302(self, result):
        add_linenum = 2 - int(result['info'].split()[-1])
        cr = self.newline * add_linenum
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e303(self, result):
        delete_linenum = int(result['info'].split("(")[1].split(")")[0]) - 2
        delete_linenum = max(1, delete_linenum)

        # We need to count because pep8 reports an offset line number if there
        # are comments.
        cnt = 0
        line = result['line'] - 2
        while cnt < delete_linenum:
            if line < 0:
                break
            if not self.source[line].strip():
                self.source[line] = ''
                cnt += 1
            line -= 1

    def fix_e401(self, result):
        line_index = result['line'] - 1
        target = self.source[line_index]

        # Take care of semicolons first
        if ';' in target:
            self.source[line_index] = self._fix_multiple_statements(target)
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

    def _fix_multiple_statements(self, target):
        non_whitespace_index = len(target) - len(target.lstrip())
        indentation = target[:non_whitespace_index]
        f = [indentation + t.strip() for t in target.split(";") if t.strip()]
        return '\n'.join(f) + '\n'

    def fix_e702(self, result):
        target = self.source[result['line'] - 1]
        self.source[result['line'] - 1] = self._fix_multiple_statements(target)

    def fix_w291(self, result):
        fixed_line = self.source[result['line'] - 1].rstrip()
        self.source[result['line'] - 1] = "%s%s" % (fixed_line, self.newline)

    def fix_w293(self, result):
        self.source[result['line'] - 1] = self.newline

    def fix_w391(self, result):
        source = copy.copy(self.source)
        source.reverse()
        found_notblank = False
        blank_count = 0
        for line in source:
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
        pass

    def fix_w602(self, result):
        line = self.source[result['line'] - 1]
        sio = StringIO(line)
        fixed_line = ""
        is_found_raise = False
        for tokens in tokenize.generate_tokens(sio.readline):
            if tokens[0] is token.INDENT:
                fixed_line += tokens[1]
            elif tokens[1] == 'raise':
                fixed_line += "raise "
                is_found_raise = True
            elif tokens[0] is token.NAME and is_found_raise:
                fixed_line += "%s(" % tokens[1]
            elif tokens[0] is token.NEWLINE:
                fixed_line += ")%s" % tokens[1]
                break
            elif tokens[0] not in (token.OP, token.DEDENT):
                fixed_line += tokens[1]
        self.source[result['line'] - 1] = fixed_line


def _get_difftext(old, new, filename):
    diff = unified_diff(old, new, 'original/' + filename, 'fixed/' + filename)
    difftext = [line for line in diff]
    return "".join(difftext)


def main():
    """tool main"""
    parser = OptionParser(version="autopep8: %s" % __version__,
                          description=__doc__)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                      help='print to verbose result.')
    parser.add_option('-d', '--diff', action='store_true', dest='diff',
                      help='diff print of fixed source.')
    parser.add_option('-p', '--pep8-passes', default=5, type='int',
                      help='maximum number of additional pep8 passes')
    opts, args = parser.parse_args()
    if not len(args):
        print parser.format_help()
        return 1
    filename = args[0]
    original_filename = filename
    tmp_source = open(filename).read()
    fix = FixPEP8(filename, opts)
    fixed_source = fix.fix()
    original_source = copy.copy(fix.original_source)
    for cnt in range(opts.pep8_passes):
        if fixed_source == tmp_source:
            break
        tmp_source = copy.copy(fixed_source)
        filename = tempfile.mkstemp()[1]
        fp = open(filename, 'w')
        fp.write(fixed_source)
        fp.close()
        fix = FixPEP8(filename, opts)
        fixed_source = fix.fix()
        os.remove(filename)
    if opts.diff:
        new = StringIO("".join(fix.source))
        new = new.readlines()
        print _get_difftext(original_source, new, original_filename),
    else:
        print fixed_source,

if __name__ == '__main__':
    main()

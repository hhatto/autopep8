#!/usr/bin/env python
"""This tool is automatic generate to pep8 checked code."""
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

__version__ = '0.1.2'


pep8bin = 'pep8'
CR = '\r'
LF = '\n'
CRLF = '\r\n'


class FixPEP8(object):

    """fix invalid code

    [fixed method list]
    - e201
    - e203
    - e211
    - e231
    - e261
    - e262
    - e302
    - e303
    - e401
    - e701
    - e702
    - w291
    - w293
    - w391
    """
    def __init__(self, filename, options):
        self.filename = filename
        self.source = open(filename).readlines()
        self.original_source = copy.copy(self.source)
        self.newline = self._find_newline(self.source)
        self.results = []
        self.options = options
        self.indent_word = self._get_indentword("".join(self.source))

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
        indent_word = ""
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
        info = " ".join(tmp[3:])
        pep8id = info.lstrip().split()[0]
        return dict(id=pep8id, filename=filename, line=line,
                    column=column, info=info)

    def _execute_pep8(self, targetfile):
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
        self.results = [self._analyze_pep8result(line) for line in pep8result]
        self._fix_source()
        return "".join(self.source)

    def fix_e201(self, result):
        self._fix_whitespace(result, r"(\( )", "(")

    def fix_e203(self, result):
        self._fix_whitespace(result, r"(\) )", ")")

    def fix_e211(self, result):
        self._fix_whitespace(result, r"( \()", "(")

    def fix_e225(self, result):
        target = self.source[result['line'] - 1]
        offset = result['column']
        fixed = ""
        if target[offset - 2] not in tokenize.Whitespace:
            fixed = target[:offset - 1] + " " + target[offset - 1]
        else:
            fixed = target[:offset - 1]
        if target[offset] not in tokenize.Whitespace:
            fixed += " " + target[offset:]
        else:
            fixed += target[offset:]
        self.source[result['line'] - 1] = fixed

    def fix_e231(self, result):
        target = self.source[result['line'] - 1]
        fixed = ""
        fixed_end = 0
        for i in re.finditer(",\S", target):
            fixed += target[fixed_end:i.start()] + ", "
            fixed_end = i.end() - 1
        fixed += target[fixed_end:]
        self.source[result['line'] - 1] = fixed

    def fix_e261(self, result):
        target = self.source[result['line'] - 1]
        c = result['column']
        fixed = target[:c] + " " + target[c:]
        self.source[result['line'] - 1] = fixed

    def fix_e262(self, result):
        self._fix_whitespace(result, r"##*", "#")

    def fix_e302(self, result):
        add_linenum = 2 - int(result['info'].split()[-1])
        cr = self.newline * add_linenum
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fix_e303(self, result):
        delete_linenum = int(result['info'].split("(")[1].split(")")[0]) - 2
        for cnt in range(delete_linenum):
            self.source[result['line'] - 2 - cnt] = ''

    def fix_e401(self, result):
        target = self.source[result['line'] - 1]
        modules = target.split("import ")[1].split(",")
        fixed_modulelist = ["import %s" % m.lstrip() for m in modules]
        self.source[result['line'] - 1] = self.newline.join(fixed_modulelist)

    def fix_e701(self, result):
        target = self.source[result['line'] - 1]
        c = result['column']
        indent_level = self._get_indentlevel(target)
        fixed_source = target[:c] + self.newline + \
                       self.indent_word * indent_level + target[c:].lstrip()
        self.source[result['line'] - 1] = fixed_source

    def fix_e702(self, result):
        # FIXME: when multiple statements.
        target = self.source[result['line'] - 1]
        f = target.split(";")
        fixed = "".join(f)
        self.source[result['line'] - 1] = fixed

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
        for cnt, line in enumerate(source):
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


def _get_difftext(old, new):
    diff = unified_diff(old, new, 'oiginal', 'fixed')
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
    opts, args = parser.parse_args()
    if not len(args):
        print parser.format_help()
        return 1
    fix = FixPEP8(args[0], opts)
    fixed_source = fix.fix()
    if opts.diff:
        new = StringIO("".join(fix.source))
        new = new.readlines()
        print _get_difftext(fix.original_source, new),
    else:
        print fixed_source,

if __name__ == '__main__':
    main()

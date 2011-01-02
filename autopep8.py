import copy
import os
import re
import sys
from optparse import OptionParser
from subprocess import Popen, PIPE

__version__ = '0.1'


pep8bin = 'pep8'


class FixPEP8(object):

    """fix invalid code

    [fixed mothod list]
    - e231
    - e302
    - e303
    - e401
    - w291
    - w293
    - w391
    """
    def __init__(self, filename):
        self.filename = filename
        self.source = open(filename).readlines()

    def _analyze_pep8result(self, result):
        tmp = result.split(":")
        filename = tmp[0]
        line = int(tmp[1])
        column = tmp[2]
        info = " ".join(tmp[3:])
        pep8id = info.lstrip().split()[0]
        #print pep8id
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

    def _fixed_source(self):
        for result in self.results:
            #print result
            fixed_methodname = "fixed_%s" % result['id'].lower()
            if hasattr(self, fixed_methodname):
                fix = getattr(self, fixed_methodname)
                fix(result)
            else:
                print >>sys.stderr, "'%s' is not defined." % fixed_methodname

    def fix(self):
        pep8result = self._execute_pep8(self.filename)
        self.results = [self._analyze_pep8result(line) for line in pep8result]
        self._fixed_source()
        return "".join(self.source)

    def fixed_e231(self, result):
        target = self.source[result['line'] - 1]
        fixed = ""
        fixed_end = 0
        for i in re.finditer(",\S", target):
            fixed += target[fixed_end:i.start()] + ", "
            fixed_end = i.end() - 1
        fixed += target[fixed_end:]
        self.source[result['line'] - 1] = fixed

    def fixed_e302(self, result):
        add_linenum = 2 - int(result['info'].split()[-1])
        # TODO: found logic, cr or lf or crlf in source code
        cr = "\n" * add_linenum
        self.source[result['line'] - 1] = cr + self.source[result['line'] - 1]

    def fixed_e303(self, result):
        delete_linenum = int(result['info'].split("(")[1].split(")")[0]) - 2
        for cnt in range(delete_linenum):
            self.source[result['line'] - 2 - cnt] = ''

    def fixed_e401(self, result):
        target = self.source[result['line'] - 1]
        modules = target.split("import ")[1].split(",")
        fixed_modulelist = ["import %s" % m.lstrip() for m in modules]
        # TODO: found logic, cr or lf or crlf in source code
        self.source[result['line'] - 1] = "\n".join(fixed_modulelist)

    def fixed_w291(self, result):
        fixed_line = self.source[result['line'] - 1].strip()
        # TODO: found logic, cr or lf or crlf in source code
        self.source[result['line'] - 1] = "%s\n" % fixed_line

    def fixed_w293(self, result):
        # TODO: found logic, cr or lf or crlf in source code
        self.source[result['line'] - 1] = "\n"

    def fixed_w391(self, result):
        source = copy.copy(self.source)
        source.reverse()
        found_notblank = False
        for cnt, line in enumerate(source):
            if re.match("^$", line):
                source[cnt] = ''
                found_notblank = True
            if found_notblank and not re.match("^$", line):
                source[cnt] = line.split("\n")[0]
                break
        source.reverse()
        self.source = source


def main():
    """tool main"""
    parser = OptionParser(version="autopep8: %s" % __version__,
                          description=__doc__)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                      help='print to verbose result.')
    opts, args = parser.parse_args()
    fix = FixPEP8(args[0])
    print fix.fix()

if __name__ == '__main__':
    main()

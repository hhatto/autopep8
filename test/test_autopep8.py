import os
import sys
import unittest
import contextlib
from subprocess import Popen, PIPE
from tempfile import mkstemp
try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

ROOT_DIR = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

sys.path.insert(0, ROOT_DIR)
import autopep8

if 'AUTOPEP8_COVERAGE' in os.environ and int(os.environ['AUTOPEP8_COVERAGE']):
    AUTOPEP8_CMD_TUPLE = ('coverage', 'run', '--branch', '--parallel',
                          os.path.join(ROOT_DIR, 'autopep8.py'),)
else:
    # We need to specify the executable to make sure the correct Python
    # interpreter gets used.
    AUTOPEP8_CMD_TUPLE = (sys.executable,
                          os.path.join(ROOT_DIR, 'autopep8.py'),)


def py27_and_above(func):
    if sys.version_info[0] == 2 and sys.version_info[1] < 7:
        func = None
    return func


def only_py2(func):
    if sys.version_info[0] != 2:
        func = None
    return func


class TestUtils(unittest.TestCase):

    def test_find_newline_only_cr(self):
        source = ["print 1\r", "print 2\r", "print3\r"]
        self.assertEqual(autopep8.CR, autopep8.find_newline(source))

    def test_find_newline_only_lf(self):
        source = ["print 1\n", "print 2\n", "print3\n"]
        self.assertEqual(autopep8.LF, autopep8.find_newline(source))

    def test_find_newline_only_crlf(self):
        source = ["print 1\r\n", "print 2\r\n", "print3\r\n"]
        self.assertEqual(autopep8.CRLF, autopep8.find_newline(source))

    def test_find_newline_cr1_and_lf2(self):
        source = ["print 1\n", "print 2\r", "print3\n"]
        self.assertEqual(autopep8.LF, autopep8.find_newline(source))

    def test_find_newline_cr1_and_crlf2(self):
        source = ["print 1\r\n", "print 2\r", "print3\r\n"]
        self.assertEqual(autopep8.CRLF, autopep8.find_newline(source))

    def test_shorten_comment(self):
        self.assertEqual('# ' + 'x' * 77 + '\n',
                         autopep8.shorten_comment('# ' + 'x' * 100 + '\n',
                                                  '\n'))

    def test_detect_encoding(self):
        self.assertEqual(
            'utf-8',
            autopep8.detect_encoding(
                os.path.join(ROOT_DIR, 'setup.py')))

    def test_read_from_filename_with_bad_encoding(self):
        """Bad encoding should not cause an exception."""
        self.assertEqual(
            '# -*- coding: zlatin-1 -*-\n',
            autopep8.read_from_filename(
                os.path.join(ROOT_DIR, 'test', 'bad_encoding.py')))

    def test_read_from_filename_with_bad_encoding2(self):
        """Bad encoding should not cause an exception."""
        self.assertTrue(autopep8.read_from_filename(
            os.path.join(ROOT_DIR, 'test', 'bad_encoding2.py')))

    def test_fix_whitespace(self):
        self.assertEqual(
            'a b',
            autopep8.fix_whitespace('a    b', offset=1, replacement=' '))

    def test_fix_whitespace_with_tabs(self):
        self.assertEqual(
            'a b',
            autopep8.fix_whitespace('a\t  \t  b', offset=1, replacement=' '))


class TestFixPEP8Error(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=""):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        opts, _ = autopep8.parse_args(options.split() + [self.tempfile[1]])
        sio = StringIO()
        autopep8.fix_file(filename=self.tempfile[1],
                          opts=opts,
                          output=sio)
        self.result = sio.getvalue()

    def test_e101(self):
        line = """
while True:
    if True:
    \t1
""".lstrip()
        fixed = """
while True:
    if True:
        1
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_with_comments(self):
        line = """
while True:  # My inline comment
             # with a hanging
             # comment.
    # Hello
    if True:
    \t# My comment
    \t1
    \t# My other comment
""".lstrip()
        fixed = """
while True:  # My inline comment
             # with a hanging
             # comment.
    # Hello
    if True:
        # My comment
        1
        # My other comment
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_skip_if_bad_indentation(self):
        line = """
try:
\t    pass
    except:
        pass
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e111_short(self):
        line = "class Dummy:\n  def __init__(self):\n    pass\n"
        fixed = "class Dummy:\n    def __init__(self):\n        pass\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e111_long(self):
        line = "class Dummy:\n     def __init__(self):\n          pass\n"
        fixed = "class Dummy:\n    def __init__(self):\n        pass\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e111_longer(self):
        line = """
while True:
      if True:
            1
      elif True:
            2
""".lstrip()
        fixed = """
while True:
    if True:
        1
    elif True:
        2
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e111_multiple_levels(self):
        line = """
while True:
    if True:
       1

# My comment
print('abc')

""".lstrip()
        fixed = """
while True:
    if True:
        1

# My comment
print('abc')
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e111_with_dedent(self):
        line = """
def foo():
    if True:
         2
    1
""".lstrip()
        fixed = """
def foo():
    if True:
        2
    1
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e111_with_other_errors(self):
        line = """
def foo():
    if True:
         (2 , 1)
    1
    if True:
           print('hello')  
    2
""".lstrip()
        fixed = """
def foo():
    if True:
        (2, 1)
    1
    if True:
        print('hello')
    2
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e12_reindent(self):
        line = """

def foo_bar(baz, frop,
    fizz, bang):  # E128
    pass

if True:
    x = {
         }  # E123
#: E121
print "E121", (
  "dent")
#: E122
print "E122", (
"dent")
#: E124
print "E124", ("visual",
               "indent_two"
              )
#: E125
if (row < 0 or self.moduleCount <= row or
    col < 0 or self.moduleCount <= col):
    raise Exception("%s,%s - %s" % (row, col, self.moduleCount))
#: E126
print "E126", (
            "dent")
#: E127
print "E127", ("over-",
                  "over-indent")
#: E128
print "E128", ("under-",
              "under-indent")
"""
        fixed = """

def foo_bar(baz, frop,
            fizz, bang):  # E128
    pass

if True:
    x = {
    }  # E123
#: E121
print "E121", (
    "dent")
#: E122
print "E122", (
    "dent")
#: E124
print "E124", ("visual",
               "indent_two"
               )
#: E125
if (row < 0 or self.moduleCount <= row or
        col < 0 or self.moduleCount <= col):
    raise Exception("%s,%s - %s" % (row, col, self.moduleCount))
#: E126
print "E126", (
    "dent")
#: E127
print "E127", ("over-",
               "over-indent")
#: E128
print "E128", ("under-",
               "under-indent")
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e12_reindent_with_multiple_fixes(self):
        line="""

sql = 'update %s set %s %s' % (from_table,
                               ','.join(['%s=%s' % (col, col) for col in cols]),
        where_clause)
"""
        fixed = """

sql = 'update %s set %s %s' % (from_table,
                               ','.join(
                                   ['%s=%s' % (col, col) for col in cols]),
                               where_clause)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e12_tricky(self):
        line="""
#: E126
if (
    x == (
        3
    ) or
    x == (
    3
    ) or
        y == 4):
    pass
"""
        fixed = """
#: E126
if (
    x == (
        3
    ) or
    x == (
        3
    ) or
        y == 4):
    pass
"""
        self._inner_setup(line)
        #self.assertEqual(self.result, fixed)

    def test_e191(self):
        line = """
while True:
\tif True:
\t\t1
""".lstrip()
        fixed = """
while True:
    if True:
        1
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e201(self):
        line = "(   1)\n"
        fixed = "(1)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e202(self):
        line = "(1   )\n[2  ]\n{3  }\n"
        fixed = "(1)\n[2]\n{3}\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e203_colon(self):
        line = "{4 : 3}\n"
        fixed = "{4: 3}\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e203_comma(self):
        line = "[1 , 2  , 3]\n"
        fixed = "[1, 2, 3]\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e203_semicolon(self):
        line = "print(a, end=' ') ; nl = 0\n"
        fixed = "print(a, end=' '); nl = 0\n"
        self._inner_setup(line, options='--select=E203')
        self.assertEqual(self.result, fixed)

    def test_e203_with_newline(self):
        line = "print(a\n, end=' ')\n"
        fixed = "print(a, end=' ')\n"
        self._inner_setup(line, options='--select=E203')
        self.assertEqual(self.result, fixed)

    def test_e211(self):
        line = "d = [1, 2, 3]\nprint d  [0]\n"
        fixed = "d = [1, 2, 3]\nprint d[0]\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e221(self):
        line = "a = 1  + 1\n"
        fixed = "a = 1 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e222(self):
        line = "a = 1 +  1\n"
        fixed = "a = 1 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e223(self):
        line = "a = 1	+ 1\n"  # include TAB
        fixed = "a = 1 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e223_double(self):
        line = "a = 1		+ 1\n"  # include TAB
        fixed = "a = 1 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e223_with_tab_indentation(self):
        line = """
class Foo():
\tdef __init__(self):
\t\tx= 1\t+ 3
""".lstrip()
        fixed = """
class Foo():
\tdef __init__(self):
\t\tx = 1 + 3
""".lstrip()
        self._inner_setup(line, options='--ignore=W191')
        self.assertEqual(self.result, fixed)

    def test_e224(self):
        line = "a = 11 +	1\n"    # include TAB
        fixed = "a = 11 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e224_double(self):
        line = "a = 11 +		1\n"    # include TAB
        fixed = "a = 11 + 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e224_with_tab_indentation(self):
        line = """
class Foo():
\tdef __init__(self):
\t\tx= \t3
""".lstrip()
        fixed = """
class Foo():
\tdef __init__(self):
\t\tx = 3
""".lstrip()
        self._inner_setup(line, options='--ignore=W191')
        self.assertEqual(self.result, fixed)

    def test_e225(self):
        line = "1+1\n2 +2\n3+ 3\n"
        fixed = "1 + 1\n2 + 2\n3 + 3\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e225_with_indentation_fix(self):
        line = """
class Foo(object):
  def bar(self):
    return self.elephant!=None
""".lstrip()
        fixed = """
class Foo(object):
    def bar(self):
        return self.elephant != None
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e231(self):
        line = "[1,2,3]\n"
        fixed = "[1, 2, 3]\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e241(self):
        line = "l = (1,  2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, "--ignore W")
        self.assertEqual(self.result, fixed)

    def test_e241_double(self):
        line = "l = (1,   2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, "--ignore W")
        self.assertEqual(self.result, fixed)

    def test_e242(self):
        line = "l = (1,\t2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, "--ignore W")
        self.assertEqual(self.result, fixed)

    def test_e242_double(self):
        line = "l = (1,\t\t2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, "--ignore W")
        self.assertEqual(self.result, fixed)

    def test_e251(self):
        line = "def a(arg = 1):\n    print arg\n"
        fixed = "def a(arg=1):\n    print arg\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e251_with_escaped_newline(self):
        line = "1\n\n\ndef a(arg=\\\n1):\n    print(arg)\n"
        fixed = "1\n\n\ndef a(arg=1):\n    print(arg)\n"
        self._inner_setup(line, options='--select=E251')
        self.assertEqual(self.result, fixed)

    def test_e251_with_calling(self):
        line = "foo(bar= True)\n"
        fixed = "foo(bar=True)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e261(self):
        line = "print 'a b '# comment\n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e261_with_dictionary(self):
        line = "d = {# comment\n1: 2}\n"
        fixed = "d = {  # comment\n    1: 2}\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e261_with_dictionary_no_space(self):
        line = "d = {#comment\n1: 2}\n"
        fixed = "d = {  # comment\n    1: 2}\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_more_space(self):
        line = "print 'a b '  #  comment\n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_with_no_comment(self):
        line = "1  #\n123\n"
        fixed = "1\n123\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_none_space(self):
        line = "print 'a b '  #comment\n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_hash_in_string(self):
        line = "print 'a b  #string'  #comment\n"
        fixed = "print 'a b  #string'  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_hash_in_string_and_multiple_hashes(self):
        line = "print 'a b  #string'  #comment #comment\n"
        fixed = "print 'a b  #string'  # comment #comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_empty_comment(self):
        line = "print 'a b'  #\n"
        fixed = "print 'a b'\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_more_complex(self):
        line = "print 'a b '  #comment\n123\n"
        fixed = "print 'a b '  # comment\n123\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e271(self):
        line = "True and  False\n"
        fixed = "True and False\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e272(self):
        line = "True  and False\n"
        fixed = "True and False\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e273(self):
        line = "True and\tFalse\n"
        fixed = "True and False\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e274(self):
        line = "True\tand False\n"
        fixed = "True and False\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e301(self):
        line = "class k:\n    s = 0\n    def f():\n        print 1\n"
        fixed = "class k:\n    s = 0\n\n    def f():\n        print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e302(self):
        line = "def f():\n    print 1\n\ndef ff():\n    print 2\n"
        fixed = "def f():\n    print 1\n\n\ndef ff():\n    print 2\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e303(self):
        line = "\n\n\n# alpha\n\n1\n"
        fixed = "\n\n# alpha\n1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e304(self):
        line = "@contextmanager\n\ndef f():\n    print 1\n"
        fixed = "@contextmanager\ndef f():\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e304_with_comment(self):
        line = "@contextmanager\n#comment\n\ndef f():\n    print 1\n"
        fixed = "@contextmanager\n#comment\ndef f():\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e401(self):
        line = "import os, sys\n"
        fixed = "import os\nimport sys\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e401_with_indentation(self):
        line = "def a():\n    import os, sys\n"
        fixed = "def a():\n    import os\n    import sys\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_basic(self):
        line = \
"""print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = \
"""print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333,
      333, 333, 333)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_indent(self):
        line = \
"""def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = \
"""def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222,
          222, 333, 333, 333, 333)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_arithmetic_operator_with_indent(self):
        line = \
"""def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        fixed = \
"""def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + \\
        222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_more_complicated(self):
        line = \
"""blahblah = os.environ.get('blahblah') or os.environ.get('blahblahblah') or os.environ.get('blahblahblahblah')
"""
        fixed = \
"""blahblah = os.environ.get('blahblah') or os.environ.get(
    'blahblahblah') or os.environ.get('blahblahblahblah')
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_skip_even_more_complicated(self):
        line = \
"""if True:
    if True:
        if True:
            blah = blah.blah_blah_blah_bla_bl(blahb.blah, blah.blah,
                                              blah=blah.label, blah_blah=blah_blah,
                                              blah_blah2=blah_blah)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_prefer_to_break_at_begnning(self):
        """We prefer not to leave part of the arguments hanging."""
        line = \
"""looooooooooooooong = foo(one, two, three, four, five, six, seven, eight, nine, ten)
"""
        fixed = \
"""looooooooooooooong = foo(
    one, two, three, four, five, six, seven, eight, nine, ten)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_do_not_break_on_keyword(self):
        # We don't want to put a newline after equals for keywords as this
        # violates PEP 8.
        line = \
"""if True:
    long_variable_name = tempfile.mkstemp(prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        fixed = \
"""if True:
    long_variable_name = tempfile.mkstemp(
        prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_do_not_begin_line_with_comma(self):
        # This fix is incomplete. (The line is still too long.) But it is here
        # just to confirm that we do not put a comma at the beginning of a
        # line.
        line = """

def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction( [MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine() )
"""
        fixed = """

def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction([MODIFY70.text, OBJECTBINDING71.text, COLON72.text],
                                      MODIFY70.getLine(), MODIFY70.getCharPositionInLine())
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_do_not_break_if_useless(self):
        line = \
"""
123
('bbb', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
"""
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_with_comment(self):
        line = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap.
"""
        fixed = """123
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap.
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_more_comments(self):
        line = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap.
                        # This is the next line.
"""
        fixed = """123
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap.
                        # This is the next line.
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_should_cut_comment_pattern(self):
        line = """123
# -- Randy's datastructure -----------------------------------------------------
321
"""
        fixed = """123
# -- Randy's datastructure ----------------------------------------------------
321
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e502(self):
        line = "print('abc'\\\n      'def')\n"
        fixed = "print('abc'\n      'def')\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e701(self):
        line = "if True: print True\n"
        fixed = "if True:\n    print True\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702(self):
        line = "print 1; print 2\n"
        fixed = "print 1\nprint 2\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_more_complicated(self):
        line = """\
def foo():
    if bar : bar+=1;  bar=bar*bar   ; return bar
"""
        fixed = """\
def foo():
    if bar:
        bar += 1
        bar = bar * bar
        return bar
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_semicolon_in_string(self):
        line = 'print(";");\n'
        fixed = 'print(";")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_semicolon_in_string_to_the_right(self):
        line = 'x = "x"; y = "y;y"\n'
        fixed = 'x = "x"\ny = "y;y"\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_skip_with_triple_quote(self):
        # We do not support this yet.
        # We would expect '"""\n      hello\n   """\n1\n'.
        line = '"""\n      hello\n   """; 1\n'
        fixed = line
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_semicolon_after_string(self):
        line = """
raise IOError('abc '
              'def.');
""".lstrip()
        fixed = """
raise IOError('abc '
              'def.')
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)


class TestFixPEP8Warning(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=()):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        opts, _ = autopep8.parse_args([self.tempfile[1]] + list(options))
        sio = StringIO()
        autopep8.fix_file(filename=self.tempfile[1],
                          opts=opts,
                          output=sio)
        self.result = sio.getvalue()

    def test_w291(self):
        line = "print 'a b '\t \n"
        fixed = "print 'a b '\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w291_with_comment(self):
        line = "print 'a b '  # comment\t \n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w292(self):
        line = "1\n2"
        fixed = "1\n2\n"
        self._inner_setup(line, options=['--select=W292'])
        self.assertEqual(self.result, fixed)

    def test_w293(self):
        line = "1\n \n2\n"
        fixed = "1\n\n2\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w391(self):
        line = "  \n"
        fixed = ""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w391_more_complex(self):
        line = "123\n456\n  \n"
        fixed = "123\n456\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601(self):
        line = "a = {0: 1}\na.has_key(0)\n"
        fixed = "a = {0: 1}\n0 in a\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_word(self):
        line = "my_dict = {0: 1}\nmy_dict.has_key(0)\n"
        fixed = "my_dict = {0: 1}\n0 in my_dict\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_conditional(self):
        line = "a = {0: 1}\nif a.has_key(0):\n    print 1\n"
        fixed = "a = {0: 1}\nif 0 in a:\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_self(self):
        line = "self.a.has_key(0)\n"
        fixed = "0 in self.a\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_self_with_conditional(self):
        line = "if self.a.has_key(0):\n    print 1\n"
        fixed = "if 0 in self.a:\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_skip_multiple(self):
        # We don't support this case
        line = "a.has_key(0) and b.has_key(0)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w601_skip_multiple_nested(self):
        # We don't support this case
        line = "alpha.has_key(nested.has_key(12)) and beta.has_key(1)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w601_precedence(self):
        line = "if self.a.has_key(1 + 2):\n    print 1\n"
        fixed = "if (1 + 2) in self.a:\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_skip_parens(self):
        # We don't support this case
        line = "alpha.has_key(foo(12))\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w601_skip_multi_line(self):
        # We don't support this case
        line = """
a.has_key(
    0
)
""".lstrip()
        fixed = line
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_arg_is_string(self):
        line = "raise ValueError, \"w602 test\"\n"
        fixed = "raise ValueError(\"w602 test\")\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_arg_is_string_with_comment(self):
        line = "raise ValueError, \"w602 test\"  # comment\n"
        fixed = "raise ValueError(\"w602 test\")  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_skip_ambiguous_case(self):
        line = "raise 'a', 'b', 'c'\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    @only_py2
    def test_w602_skip_logic(self):
        line = "raise TypeError, e or 'hello'\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    @only_py2
    def test_w602_triple_quotes(self):
        line = 'raise ValueError, """hello"""\n1\n'
        fixed = 'raise ValueError("""hello""")\n1\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline(self):
        line = 'raise ValueError, """\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_skip_complex_multiline(self):
        # We do not handle formatted multiline strings
        line = 'raise ValueError, """\nhello %s %s""" % (\n    1, 2)\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    @only_py2
    def test_w602_multiline_with_trailing_spaces(self):
        line = 'raise ValueError, """\nhello"""    \n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline_with_escaped_newline(self):
        line = 'raise ValueError, \\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline_with_escaped_newline_and_comment(self):
        line = 'raise ValueError, \\\n"""\nhello"""  # comment\n'
        fixed = 'raise ValueError("""\nhello""")  # comment\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline_with_multiple_escaped_newlines(self):
        line = 'raise ValueError, \\\n\\\n\\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline_with_nested_quotes(self):
        line = 'raise ValueError, """hello\'\'\'blah"a"b"c"""\n'
        fixed = 'raise ValueError("""hello\'\'\'blah"a"b"c""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_skip_multiline_with_single_quotes(self):
        line = "raise ValueError, '''\nhello'''\n"
        fixed = "raise ValueError('''\nhello''')\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiline_string_stays_the_same(self):
        line = 'raise """\nhello"""\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    @only_py2
    def test_w602_escaped_lf(self):
        line = 'raise ValueError, \\\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_escaped_crlf(self):
        line = 'raise ValueError, \\\r\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_indentation(self):
        line = 'def foo():\n    raise ValueError, "hello"\n'
        fixed = 'def foo():\n    raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    # Doesn't work because pep8 doesn't seem to work with CR line endings
    #def test_w602_escaped_cr(self):
    #    line = 'raise ValueError, \\\r"hello"\n'
    #    fixed = 'raise ValueError("hello")\n'
    #    self._inner_setup(line)
    #    self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_multiple_statements(self):
        line = 'raise ValueError, "hello";print 1\n'
        fixed = 'raise ValueError("hello")\nprint 1\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_raise_argument_triple(self):
        line = 'raise ValueError, "info", traceback\n'
        fixed = 'raise ValueError("info"), None, traceback\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_raise_argument_triple_skip_with_indentation(self):
        # We do not handle this properly yet.
        line = 'if True:\n    raise TypeError, "error", tb\n'
        fixed = line
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_raise_argument_triple_with_comment(self):
        line = 'raise ValueError, "info", traceback  # comment\n'
        fixed = 'raise ValueError("info"), None, traceback  # comment\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @only_py2
    def test_w602_raise_argument_triple_fake(self):
        line = 'raise ValueError, "info, info2"\n'
        fixed = 'raise ValueError("info, info2")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w603(self):
        line = "if 2 <> 2:\n    print False"
        fixed = "if 2 != 2:\n    print False\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w604(self):
        line = "`1`\n"
        fixed = "repr(1)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w604_skip_multiple_instances(self):
        # We do not support this yet
        line = "``1`` + ``b``\n"
        fixed = line
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w604_skip_multiple_lines(self):
        # We do not support this yet
        line = "`(1\n  )`\n"
        fixed = line
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)


class TestOptions(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1]] + options,
                  stdout=PIPE)
        self.result = p.communicate()[0].decode('utf8')

    def test_diff(self):
        line = "'abc'  \n"
        fixed = "-'abc'  \n+'abc'\n"
        self._inner_setup(line, ['--diff'])
        self.assertEqual('\n'.join(self.result.split('\n')[3:]), fixed)

    def test_pep8_passes(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        self._inner_setup(line, ['--pep8-passes', '0'])
        self.assertEqual(self.result, fixed)

    def test_pep8_ignore(self):
        line = "'abc'  \n"
        self._inner_setup(line, ['--ignore=E,W'])
        self.assertEqual(self.result, line)

    @py27_and_above
    def test_help(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['-h'],
                  stdout=PIPE)
        self.assertIn('Usage:', p.communicate()[0].decode('utf8'))

    @py27_and_above
    def test_verbose(self):
        line = 'bad_syntax)'
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '--verbose'],
                  stdout=PIPE, stderr=PIPE)
        verbose_error = p.communicate()[1].decode('utf8')
        self.assertIn("'fix_e901' is not defined", verbose_error)

    @py27_and_above
    def test_verbose_diff(self):
        line = 'bad_syntax)'
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  [self.tempfile[1], '--verbose', '--diff'],
                  stdout=PIPE, stderr=PIPE)
        verbose_error = p.communicate()[1].decode('utf8')
        self.assertIn("'fix_e901' is not defined", verbose_error)

    def test_in_place(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"

        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '--in-place'])
        p.wait()

        f = open(self.tempfile[1])
        self.assertEqual(f.read(), fixed)
        f.close()

    def test_in_place_and_diff(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '--in-place', '--diff'],
                  stderr=PIPE)
        result = p.communicate()[1].decode('utf8')
        self.assertTrue('--in-place and --diff are mutually exclusive' in result)

    def test_recursive(self):
        import tempfile
        temp_directory = tempfile.mkdtemp(dir='.')
        try:
            with open(os.path.join(temp_directory, 'a.py'), 'w') as output:
                output.write("'abc'  \n")

            os.mkdir(os.path.join(temp_directory, 'd'))
            with open(os.path.join(temp_directory, 'd', 'b.py'),
                      'w') as output:
                output.write("123  \n")

            p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                      [temp_directory, '--recursive', '--diff'],
                      stdout=PIPE)
            result = p.communicate()[0].decode('utf8')

            self.assertEqual(
                "-'abc'  \n+'abc'",
                '\n'.join(result.split('\n')[3:5]))

            self.assertEqual(
                '-123  \n+123',
                '\n'.join(result.split('\n')[8:10]))
        finally:
            import shutil
            shutil.rmtree(temp_directory)

    def test_only_recursive(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '--recursive'],
                  stderr=PIPE)
        result = p.communicate()[1].decode('utf8')
        self.assertTrue('must be used with --in-place or --diff' in result)


class TestSpawnPEP8Process(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=""):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        opts, _ = autopep8.parse_args(options.split() + [self.tempfile[1]])
        sio = StringIO()

        # Monkey patch pep8 to trigger spawning
        original_pep8 = autopep8.pep8
        try:
            autopep8.pep8 = None
            autopep8.fix_file(filename=self.tempfile[1],
                              opts=opts,
                              output=sio)
        finally:
            autopep8.pep8 = original_pep8

        self.result = sio.getvalue()

    def test_basic(self):
        line = "print('abc' )    \n1*1\n"
        fixed = "print('abc')\n1 * 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)


class TestCoverage(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=""):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)

    def test_fixpep8_class_constructor(self):
        line = "print 1\nprint 2\n"
        self._inner_setup(line)
        pep8obj = autopep8.FixPEP8(self.tempfile[1], None)
        self.assertEqual("".join(pep8obj.source), line)

    def test_no_argument(self):
        with disable_stderr():
            try:
                autopep8.parse_args([])
                self.assertEqual("not work", "test has failed!!")
            except SystemExit as e:
                self.assertEqual(e.code, 2)

    def test_inplace_with_multi_files(self):
        with disable_stderr():
            try:
                autopep8.parse_args(['test.py', 'dummy.py'])
                self.assertEqual("not work", "test has failed!!")
            except SystemExit as e:
                self.assertEqual(e.code, 2)


@contextlib.contextmanager
def disable_stderr():
    with open('/dev/null', 'w') as fake_stderr:
        _tmp = sys.stderr
        sys.stderr = fake_stderr
        try:
            yield
        finally:
            sys.stderr = _tmp


if __name__ == '__main__':
    unittest.main()

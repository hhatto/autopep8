# coding: utf-8
import os
import sys
import codecs
import locale

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import contextlib
from subprocess import Popen, PIPE
from tempfile import mkstemp

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

    def test_break_multi_line(self):
        self.assertEqual(
            'foo_bar_zap_bing_bang_boom(\n    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
            autopep8.break_multi_line(
                'foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
                newline='\n', indent_word='    ',
                max_line_length=79))

    def test_break_multi_line_should_not_break_too_long_line(self):
        self.assertEqual(
            None,
            autopep8.break_multi_line(
                'foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom(333,\n',
                newline='\n', indent_word='    ',
                max_line_length=79))

    def test_break_multi_line_should_not_modify_comment(self):
        self.assertEqual(
            None,
            autopep8.break_multi_line(
                '# foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
                newline='\n', indent_word='    ',
                max_line_length=79))

    def test_multiline_string_lines(self):
        self.assertEqual(
            set([2]),
            autopep8.multiline_string_lines(
                """
'''
'''
""".lstrip()))

    def test_multiline_string_lines_with_many(self):
        self.assertEqual(
            set([2, 7, 10, 11, 12]),
            autopep8.multiline_string_lines(
                """
'''
'''
''''''
''''''
''''''
'''
'''

'''


'''
""".lstrip()))

    def test_multiline_string_should_not_report_single_line(self):
        self.assertEqual(
            set(),
            autopep8.multiline_string_lines(
                """
'''abc'''
""".lstrip()))

    def test_multiline_string_should_not_report_docstrings(self):
        self.assertEqual(
            set([5]),
            autopep8.multiline_string_lines(
                """
def foo():
    '''Foo.
    Bar.'''
    hello = '''
'''
""".lstrip()))

    def test_supported_fixes(self):
        self.assertIn('E101', [f[0] for f in autopep8.supported_fixes()])

    def test_shorten_comment(self):
        self.assertEqual('# ' + '=' * 72 + '\n',
                         autopep8.shorten_comment('# ' + '=' * 100 + '\n',
                                                  '\n',
                                                  max_line_length=79))

    def test_shorten_comment_should_not_split_numbers(self):
        line = '# ' + '0' * 100 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  newline='\n',
                                                  max_line_length=79))

    def test_shorten_comment_should_not_split_words(self):
        line = '# ' + 'a' * 100 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  newline='\n',
                                                  max_line_length=79))

    def test_shorten_comment_should_not_modify_special_comments(self):
        line = '#!/bin/blah ' + ' x' * 90 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  newline='\n',
                                                  max_line_length=79))

    def test_format_block_comments(self):
        self.assertEqual(
            '# abc',
            autopep8.format_block_comments('#abc'))

        self.assertEqual(
            '# abc',
            autopep8.format_block_comments('####abc'))

    def test_format_block_comments_with_multiple_lines(self):
        self.assertEqual(
            """
# abc
  # blah blah
    # four space indentation
''' #do not modify strings
#do not modify strings
#do not modify strings
#do not modify strings'''
#
""".lstrip(),
            autopep8.format_block_comments("""
# abc
  #blah blah
    #four space indentation
''' #do not modify strings
#do not modify strings
#do not modify strings
#do not modify strings'''
#
""".lstrip()))

    def test_format_block_comments_should_not_corrupt_special_comments(self):
        self.assertEqual(
            '#: abc',
            autopep8.format_block_comments('#: abc'))

    def test_fix_file(self):
        self.assertIn(
            'import ',
            autopep8.fix_file(
                filename=os.path.join(ROOT_DIR, 'test', 'example.py')))

    def test_normalize_line_endings(self):
        self.assertEqual(
            'abc\ndef\n123\nhello\nworld\n',
            autopep8.normalize_line_endings(
                'abc\ndef\n123\rhello\r\nworld\r'))

    def test_normalize_line_endings_with_crlf(self):
        self.assertEqual(
            'abc\r\ndef\r\n123\r\nhello\r\nworld\r\n',
            autopep8.normalize_line_endings(
                'abc\ndef\r\n123\r\nhello\r\nworld\r'))


class TestFixPEP8Error(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=()):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        opts, _ = autopep8.parse_args([self.tempfile[1]] + list(options))
        self.result = autopep8.fix_file(
            filename=self.tempfile[1],
            opts=opts)

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

    def test_e101_should_not_expand_non_indentation_tabs(self):
        line = """
while True:
    if True:
    \t1 == '\t'
""".lstrip()
        fixed = """
while True:
    if True:
        1 == '\t'
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_should_ignore_multiline_strings(self):
        line = """
x = '''
while True:
    if True:
    \t1
'''
""".lstrip()
        fixed = """
x = '''
while True:
    if True:
    \t1
'''
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_should_fix_docstrings(self):
        line = """
class Bar(object):
    def foo():
        '''
\tdocstring
        '''
""".lstrip()
        fixed = """
class Bar(object):
    def foo():
        '''
        docstring
        '''
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_when_pep8_mistakes_first_tab_in_string(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multi-line string.
        line = """
x = '''
\tHello.
'''
if True:
    123
""".lstrip()
        fixed = """
x = '''
\tHello.
'''
if True:
    123
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e101_should_ignore_multiline_strings_complex(self):
        line = """
print(3 <> 4, '''
while True:
    if True:
    \t1
\t''', 4 <> 5)
""".lstrip()
        fixed = """
print(3 != 4, '''
while True:
    if True:
    \t1
\t''', 4 != 5)
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

    def test_e101_skip_innocuous(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multi-line string. If we don't filter the innocuous
        # report properly, the below command will take a long time.
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  ['-vvv', '--select=E101', '--diff',
                   os.path.join(ROOT_DIR, 'test', 'e101_example.py')],
                  stdout=PIPE, stderr=PIPE)
        output = [x.decode('utf-8') for x in p.communicate()][0]
        self.assertEqual('', output)

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
           print('hello')\t
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

    def test_e111_should_not_modify_string_contents(self):
        line = """
if True:
 x = '''
 1
 '''
""".lstrip()
        fixed = """
if True:
    x = '''
 1
 '''
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
        line = """

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
        line = """
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
        self.assertEqual(self.result, fixed)

    def test_e12_large(self):
        self.maxDiff = None

        line = """
class BogusController(controller.CementBaseController):
    class Meta:
        pass

class BogusController2(controller.CementBaseController):
    class Meta:
        pass

class BogusController3(controller.CementBaseController):
    class Meta:
        pass

class BogusController4(controller.CementBaseController):
    class Meta:
        pass

class TestBaseController(controller.CementBaseController):
    class Meta:
        pass

class TestBaseController2(controller.CementBaseController):
    class Meta:
        pass

class TestStackedController(controller.CementBaseController):
    class Meta:
        arguments = [
            ]

class TestDuplicateController(controller.CementBaseController):
    class Meta:

        config_defaults = dict(
            foo='bar',
            )

        arguments = [
            (['-f2', '--foo2'], dict(action='store'))
            ]

    def my_command(self):
        pass
"""
        fixed = """

class BogusController(controller.CementBaseController):
    class Meta:
        pass


class BogusController2(controller.CementBaseController):
    class Meta:
        pass


class BogusController3(controller.CementBaseController):
    class Meta:
        pass


class BogusController4(controller.CementBaseController):
    class Meta:
        pass


class TestBaseController(controller.CementBaseController):
    class Meta:
        pass


class TestBaseController2(controller.CementBaseController):
    class Meta:
        pass


class TestStackedController(controller.CementBaseController):
    class Meta:
        arguments = [
        ]


class TestDuplicateController(controller.CementBaseController):
    class Meta:

        config_defaults = dict(
            foo='bar',
        )

        arguments = [
            (['-f2', '--foo2'], dict(action='store'))
        ]

    def my_command(self):
        pass
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e12_with_bad_indentation(self):
        line = r"""


def bar():
    foo(1,
      2)


def baz():
     pass

    pass
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, line)

    def test_e123(self):
        line = """
if True:
    foo = (
        )
"""
        fixed = """
if True:
    foo = (
    )
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, fixed)

    def test_e125(self):
        line = """
for k, v in sys.modules.items():
    if k in ('setuptools', 'pkg_resources') or (
        not os.path.exists(os.path.join(v.__path__[0], '__init__.py'))):
        sys.modules.pop(k)
"""
        fixed = """
for k, v in sys.modules.items():
    if k in ('setuptools', 'pkg_resources') or (
            not os.path.exists(os.path.join(v.__path__[0], '__init__.py'))):
        sys.modules.pop(k)
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, fixed)

    def test_e126(self):
        line = """
if True:
    posted = models.DateField(
            default=datetime.date.today,
            help_text="help"
    )
"""
        fixed = """
if True:
    posted = models.DateField(
        default=datetime.date.today,
        help_text="help"
    )
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, fixed)

    def test_e127(self):
        line = """
if True:
    if True:
        chksum = (sum([int(value[i]) for i in xrange(0, 9, 2)]) * 7 -
                          sum([int(value[i]) for i in xrange(1, 9, 2)])) % 10
"""
        fixed = """
if True:
    if True:
        chksum = (sum([int(value[i]) for i in xrange(0, 9, 2)]) * 7 -
                  sum([int(value[i]) for i in xrange(1, 9, 2)])) % 10
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, fixed)

    def test_e127_align_visual_indent(self):
        line = """
def draw(self):
    color = [([0.2, 0.1, 0.3], [0.2, 0.1, 0.3], [0.2, 0.1, 0.3]),
               ([0.9, 0.3, 0.5], [0.5, 1.0, 0.5], [0.3, 0.3, 0.9])  ][self._p._colored ]
    self.draw_background(color)
""".lstrip()
        fixed = """
def draw(self):
    color = [([0.2, 0.1, 0.3], [0.2, 0.1, 0.3], [0.2, 0.1, 0.3]),
             ([0.9, 0.3, 0.5], [0.5, 1.0, 0.5], [0.3, 0.3, 0.9])][self._p._colored]
    self.draw_background(color)
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e127_with_backslash(self):
        line = r"""
if True:
    if True:
        self.date = meta.session.query(schedule.Appointment)\
            .filter(schedule.Appointment.id ==
                                      appointment_id).one().agenda.endtime
""".lstrip()
        fixed = r"""
if True:
    if True:
        self.date = meta.session.query(schedule.Appointment)\
            .filter(schedule.Appointment.id ==
                    appointment_id).one().agenda.endtime
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e12_with_backslash(self):
        line = r"""
if True:
    assert reeval == parsed, \
            'Repr gives different object:\n  %r !=\n  %r' % (parsed, reeval)
"""
        fixed = r"""
if True:
    assert reeval == parsed, \
        'Repr gives different object:\n  %r !=\n  %r' % (parsed, reeval)
"""
        self._inner_setup(line, options=['--select=E12'])
        self.assertEqual(self.result, fixed)

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

    def test_e202_skip_multiline(self):
        """We skip this since pep8 reports the error as being on line 1."""
        line = """

('''
a
b
c
''' )
"""
        self._inner_setup(line)
        self.assertEqual(self.result, line)

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
        self._inner_setup(line, options=['--select=E203'])
        self.assertEqual(self.result, fixed)

    def test_e203_with_newline(self):
        line = "print(a\n, end=' ')\n"
        fixed = "print(a, end=' ')\n"
        self._inner_setup(line, options=['--select=E203'])
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
        self._inner_setup(line, options=['--ignore=W191'])
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
        self._inner_setup(line, options=['--ignore=W191'])
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
    return self.elephant is not None
""".lstrip()
        fixed = """
class Foo(object):
    def bar(self):
        return self.elephant is not None
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
        self._inner_setup(line, ['--ignore=W'])
        self.assertEqual(self.result, fixed)

    def test_e241_double(self):
        line = "l = (1,   2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, ['--ignore=W'])
        self.assertEqual(self.result, fixed)

    def test_e242(self):
        line = "l = (1,\t2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, ['--ignore=W'])
        self.assertEqual(self.result, fixed)

    def test_e242_double(self):
        line = "l = (1,\t\t2)\n"
        fixed = "l = (1, 2)\n"
        self._inner_setup(line, ['--ignore=W'])
        self.assertEqual(self.result, fixed)

    def test_e251(self):
        line = "def a(arg = 1):\n    print arg\n"
        fixed = "def a(arg=1):\n    print arg\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e251_with_escaped_newline(self):
        line = "1\n\n\ndef a(arg=\\\n1):\n    print(arg)\n"
        fixed = "1\n\n\ndef a(arg=1):\n    print(arg)\n"
        self._inner_setup(line, options=['--select=E251'])
        self.assertEqual(self.result, fixed)

    def test_e251_with_calling(self):
        line = "foo(bar= True)\n"
        fixed = "foo(bar=True)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e251_with_argument_on_next_line(self):
        line = 'foo(bar\n=None)\n'
        fixed = 'foo(bar=None)\n'
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

    def test_e261_with_comma(self):
        line = "{1: 2 # comment\n , }\n"
        fixed = "{1: 2  # comment\n , }\n"
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
        line = "@contextmanager\n# comment\n\ndef f():\n    print 1\n"
        fixed = "@contextmanager\n# comment\ndef f():\n    print 1\n"
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

    def test_e401_should_ignore_commented_comma(self):
        line = "import bdist_egg, egg  # , not a module, neither is this\n"
        fixed = "import bdist_egg\nimport egg  # , not a module, neither is this\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e401_should_ignore_commented_comma_with_indentation(self):
        line = "if True:\n    import bdist_egg, egg  # , not a module, neither is this\n"
        fixed = "if True:\n    import bdist_egg\n    import egg  # , not a module, neither is this\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e401_should_ignore_false_positive(self):
        line = "import bdist_egg; bdist_egg.write_safety_flag(cmd.egg_info, safe)\n"
        self._inner_setup(line, options=['--select=E401'])
        self.assertEqual(self.result, line)

    def test_e501_basic(self):
        line = """

print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333,
      333, 333, 333)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_shorter_length(self):
        line = "foooooooooooooooooo('abcdefghijklmnopqrstuvwxyz')\n"
        fixed = "foooooooooooooooooo(\n    'abcdefghijklmnopqrstuvwxyz')\n"
        self._inner_setup(line, options=['--max-line-length=40'])
        self.assertEqual(self.result, fixed)

    def test_e501_with_indent(self):
        line = """

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222,
          222, 333, 333, 333, 333)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_alone_with_indentation(self):
        line = """

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222,
          222, 333, 333, 333, 333)
"""
        self._inner_setup(line, options=['--select=E501'])
        self.assertEqual(self.result, fixed)

    def test_e501_alone_with_tuple(self):
        line = """

fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime', 'FLOAT')
                                                           ]
"""
        fixed = """

fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime',
                                                             'FLOAT')
                                                           ]
"""
        self._inner_setup(line, options=['--select=E501'])
        self.assertEqual(self.result, fixed)

    def test_e501_arithmetic_operator_with_indent(self):
        line = """

def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        fixed = """

def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + \\
        222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_more_complicated(self):
        line = """

blahblah = os.environ.get('blahblah') or os.environ.get('blahblahblah') or os.environ.get('blahblahblahblah')
"""
        fixed = """

blahblah = os.environ.get('blahblah') or os.environ.get(
    'blahblahblah') or os.environ.get('blahblahblahblah')
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_skip_even_more_complicated(self):
        line = """

if True:
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
        line = """

looooooooooooooong = foo(one, two, three, four, five, six, seven, eight, nine, ten)
"""
        fixed = """

looooooooooooooong = foo(
    one, two, three, four, five, six, seven, eight, nine, ten)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_multiple_lines(self):
        line = """

foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,
                           111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333)
"""
        fixed = """

foo_bar_zap_bing_bang_boom(
    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,
    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333)
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_multiple_lines_and_quotes(self):
        line = """

if True:
    xxxxxxxxxxx = xxxxxxxxxxxxxxxxx(xxxxxxxxxxx, xxxxxxxxxxxxxxxx={'xxxxxxxxxxxx': 'xxxxx',
                                                                   'xxxxxxxxxxx': xx,
                                                                   'xxxxxxxx': False,
                                                                   })
"""
        fixed = """

if True:
    xxxxxxxxxxx = xxxxxxxxxxxxxxxxx(
        xxxxxxxxxxx, xxxxxxxxxxxxxxxx={'xxxxxxxxxxxx': 'xxxxx',
                                       'xxxxxxxxxxx': xx,
                                       'xxxxxxxx': False,
                                       })
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_do_not_break_on_keyword(self):
        # We don't want to put a newline after equals for keywords as this
        # violates PEP 8.
        line = """

if True:
    long_variable_name = tempfile.mkstemp(prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        fixed = """

if True:
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
                object = ModifyAction([MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine())
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_do_not_break_if_useless(self):
        line = """

123
('bbb', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
"""
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_should_not_break_on_dot(self):
        line = """
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx('xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_with_comment(self):
        line = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
"""
        fixed = """123
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap to be within 72 characters.
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_comment_should_not_modify_docstring(self):
        line = '''
def foo():
    """
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
    """
'''.lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_should_only_modify_last_comment(self):
        line = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
"""
        fixed = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I
                        # will wrap it using textwrap to be within 72
                        # characters.
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_should_not_interfere_with_non_comment(self):
        line = '''

"""
# not actually a comment %d. 12345678901234567890, 12345678901234567890, 12345678901234567890.
""" % (0,)
'''
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_e501_should_cut_comment_pattern(self):
        line = """123
# -- Useless lines ----------------------------------------------------------------------
321
"""
        fixed = """123
# -- Useless lines -------------------------------------------------------
321
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e501_with_function_should_not_break_on_colon(self):
        line = r"""
class Useless(object):
    def _table_field_is_plain_widget(self, widget):
        if widget.__class__ == Widget or\
                (widget.__class__ == WidgetMeta and Widget in widget.__bases__):
            return True

        return False
""".lstrip()

        self._inner_setup(line)
        self.assertEqual(self.result, line)

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

    def test_e701_with_escaped_newline(self):
        line = "if True:\\\nprint True\n"
        fixed = "if True:\n    print True\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e701_with_escaped_newline_and_spaces(self):
        line = "if True:    \\   \nprint True\n"
        fixed = "if True:\n    print True\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702(self):
        line = "print 1; print 2\n"
        fixed = "print 1\nprint 2\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_whitespace(self):
        line = "print 1 ; print 2\n"
        fixed = "print 1\nprint 2\n"
        self._inner_setup(line, options=['--select=E702'])
        self.assertEqual(self.result, fixed)

    def test_e702_with_non_ascii_file(self):
        line = """
# -*- coding: utf-8 -*-
# French comment with accent é
# Un commentaire en français avec un accent é

import time

time.strftime('%d-%m-%Y');
""".lstrip()

        fixed = """
# -*- coding: utf-8 -*-
# French comment with accent é
# Un commentaire en français avec un accent é

import time

time.strftime('%d-%m-%Y')
""".lstrip()

        if sys.version_info[0] < 3:
            line = unicode(line, 'utf-8')
            fixed = unicode(fixed, 'utf-8')
            self._inner_setup(line.encode('utf-8'))
            self.assertEqual(self.result, fixed)
        else:
            self._inner_setup(line)
            self.assertEqual(self.result, fixed)

    def test_e702_with_escaped_newline(self):
        line = '1; \\\n2\n'
        fixed = '1\n2\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_escaped_newline_with_indentation(self):
        line = '1; \\\n    2\n'
        fixed = '1\n2\n'
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

    def test_e702_indent_correctly(self):
        line = """

(
    1,
    2,
    3); 4; 5; 5  # pyflakes
"""
        fixed = """

(
    1,
    2,
    3)
4
5
5  # pyflakes
"""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_triple_quote(self):
        line = '"""\n      hello\n   """; 1\n'
        fixed = '"""\n      hello\n   """\n1\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e702_with_triple_quote_and_indent(self):
        line = '    """\n      hello\n   """; 1\n'
        fixed = '    """\n      hello\n   """\n    1\n'
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

    def test_e711(self):
        line = 'foo == None\n'
        fixed = 'foo is None\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, fixed)

    def test_e711_in_conditional(self):
        line = 'if foo == None and None == foo:\npass\n'
        fixed = 'if foo is None and None == foo:\npass\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, fixed)

    def test_e711_in_conditional_with_multiple_instances(self):
        line = 'if foo == None and bar == None:\npass\n'
        fixed = 'if foo is None and bar is None:\npass\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, fixed)

    def test_e711_with_not_equals_none(self):
        line = 'foo != None\n'
        fixed = 'foo is not None\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, fixed)

    def test_e711_should_not_modify_sql_alchemy_query(self):
        line = 'filter(User.name == None)\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, line)

    def test_e711_should_not_modify_sql_alchemy_query_with_not_equals(self):
        line = 'filter(User.name != None)\n'
        self._inner_setup(line, options=['--aggressive'])
        self.assertEqual(self.result, line)

    def test_e721(self):
        line = "type('') == type('')\n"
        fixed = "isinstance('', type(''))\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e721_with_str(self):
        line = "str == type('')\n"
        fixed = "isinstance('', str)\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e721_in_conditional(self):
        line = "if str == type(''):\n    pass\n"
        fixed = "if isinstance('', str):\n    pass\n"
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

        self.result = autopep8.fix_file(
            filename=self.tempfile[1],
            opts=opts)

    def test_w191_should_ignore_multiline_strings(self):
        line = """
print(3 <> 4, '''
while True:
    if True:
    \t1
\t''', 4 <> 5)
if True:
\t123
""".lstrip()
        fixed = """
print(3 != 4, '''
while True:
    if True:
    \t1
\t''', 4 != 5)
if True:
    123
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w191_should_ignore_tabs_in_strings(self):
        line = """
if True:
\tx = '''
\t\tblah
\tif True:
\t1
\t'''
if True:
\t123
else:
\t32
""".lstrip()
        fixed = """
if True:
    x = '''
\t\tblah
\tif True:
\t1
\t'''
if True:
    123
else:
    32
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

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

    def test_w601_with_multiple(self):
        line = "a.has_key(0) and b.has_key(0)\n"
        fixed = "0 in a and 0 in b\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_with_multiple_nested(self):
        line = "alpha.has_key(nested.has_key(12)) and beta.has_key(1)\n"
        fixed = "(12 in nested) in alpha and 1 in beta\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_with_more_complexity(self):
        line = 'y.has_key(0) + x.has_key(x.has_key(0) + x.has_key(x.has_key(0) + x.has_key(1)))\n'
        fixed = '(0 in y) + ((0 in x) + ((0 in x) + (1 in x) in x) in x)\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_precedence(self):
        line = "if self.a.has_key(1 + 2):\n    print 1\n"
        fixed = "if 1 + 2 in self.a:\n    print 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601_with_parens(self):
        line = "foo(12) in alpha\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w601_with_multi_line(self):
        line = """

a.has_key(
    0
)
""".lstrip()
        fixed = '0 in a\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    @unittest.skipIf(sys.version_info < (2, 6, 4),
                     'older versions of 2.6 may be buggy')
    def test_w601_with_non_ascii(self):
        line = """
# -*- coding: utf-8 -*-
## éはe
correct = dict().has_key('good syntax ?')
""".lstrip()

        fixed = """
# -*- coding: utf-8 -*-
## éはe
correct = 'good syntax ?' in dict()
""".lstrip()

        if sys.version_info[0] < 3:
            line = unicode(line, 'utf-8')
            fixed = unicode(fixed, 'utf-8')
            self._inner_setup(line.encode('utf-8'))
            self.assertEqual(self.result, fixed)
        else:
            self._inner_setup(line)
            self.assertEqual(self.result, fixed)

    def test_w602_arg_is_string(self):
        line = "raise ValueError, \"w602 test\"\n"
        fixed = "raise ValueError(\"w602 test\")\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_arg_is_string_with_comment(self):
        line = "raise ValueError, \"w602 test\"  # comment\n"
        fixed = "raise ValueError(\"w602 test\")  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_skip_ambiguous_case(self):
        line = "raise 'a', 'b', 'c'\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w602_with_logic(self):
        line = "raise TypeError, e or 'hello'\n"
        fixed = "raise TypeError(e or 'hello')\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_triple_quotes(self):
        line = 'raise ValueError, """hello"""\n1\n'
        fixed = 'raise ValueError("""hello""")\n1\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline(self):
        line = 'raise ValueError, """\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_with_complex_multiline(self):
        line = 'raise ValueError, """\nhello %s %s""" % (\n    1, 2)\n'
        fixed = 'raise ValueError("""\nhello %s %s""" % (\n    1, 2))\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_with_trailing_spaces(self):
        line = 'raise ValueError, """\nhello"""    \n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_with_escaped_newline(self):
        line = 'raise ValueError, \\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_with_escaped_newline_and_comment(self):
        line = 'raise ValueError, \\\n"""\nhello"""  # comment\n'
        fixed = 'raise ValueError("""\nhello""")  # comment\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_with_multiple_escaped_newlines(self):
        line = 'raise ValueError, \\\n\\\n\\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_with_nested_quotes(self):
        line = 'raise ValueError, """hello\'\'\'blah"a"b"c"""\n'
        fixed = 'raise ValueError("""hello\'\'\'blah"a"b"c""")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_with_multiline_with_single_quotes(self):
        line = "raise ValueError, '''\nhello'''\n"
        fixed = "raise ValueError('''\nhello''')\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiline_string_stays_the_same(self):
        line = 'raise """\nhello"""\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w602_escaped_lf(self):
        line = 'raise ValueError, \\\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_escaped_crlf(self):
        line = 'raise ValueError, \\\r\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_indentation(self):
        line = 'def foo():\n    raise ValueError, "hello"\n'
        fixed = 'def foo():\n    raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_escaped_cr(self):
        line = 'raise ValueError, \\\r"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_multiple_statements(self):
        line = 'raise ValueError, "hello";print 1\n'
        fixed = 'raise ValueError("hello")\nprint 1\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_raise_argument_with_indentation(self):
        line = 'if True:\n    raise ValueError, "error"\n'
        fixed = 'if True:\n    raise ValueError("error")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_skip_raise_argument_triple(self):
        line = 'raise ValueError, "info", traceback\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w602_skip_raise_argument_triple_with_comment(self):
        line = 'raise ValueError, "info", traceback  # comment\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w602_raise_argument_triple_fake(self):
        line = 'raise ValueError, "info, info2"\n'
        fixed = 'raise ValueError("info, info2")\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_with_list_comprehension(self):
        line = "raise Error, [x[0] for x in probs]\n"
        fixed = "raise Error([x[0] for x in probs])\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_with_bad_syntax(self):
        line = "raise Error, 'abc\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

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

    def test_w604_with_multiple_instances(self):
        line = '``1`` + ``b``\n'
        fixed = 'repr(repr(1)) + repr(repr(b))\n'
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w604_with_multiple_lines(self):
        line = "`(1\n      )`\n"
        fixed = "repr((1\n      ))\n"
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
        self.result = p.communicate()[0].decode('utf-8')

    def test_diff(self):
        line = "'abc'  \n"
        fixed = "-'abc'  \n+'abc'\n"
        self._inner_setup(line, ['--diff'])
        self.assertEqual('\n'.join(self.result.split('\n')[3:]), fixed)

    def test_diff_wtih_empty_file(self):
        self._inner_setup('', ['--diff'])
        self.assertEqual('\n'.join(self.result.split('\n')[3:]), '')

    def test_pep8_passes(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        self._inner_setup(line, ['--pep8-passes', '0'])
        self.assertEqual(self.result, fixed)

    def test_pep8_ignore(self):
        line = "'abc'  \n"
        self._inner_setup(line, ['--ignore=E,W'])
        self.assertEqual(self.result, line)

    def test_help(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['-h'],
                  stdout=PIPE)
        self.assertIn('Usage:', p.communicate()[0].decode('utf-8'))

    def test_verbose(self):
        line = 'bad_syntax)'
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '-vvv'],
                  stdout=PIPE, stderr=PIPE)
        verbose_error = p.communicate()[1].decode('utf-8')
        self.assertIn("'fix_e901' is not defined", verbose_error)

    def test_verbose_diff(self):
        line = 'bad_syntax)'
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  [self.tempfile[1], '-vvv', '--diff'],
                  stdout=PIPE, stderr=PIPE)
        verbose_error = p.communicate()[1].decode('utf-8')
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
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(
            list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1],
                                        '--in-place', '--diff'],
            stderr=PIPE)
        result = p.communicate()[1].decode('utf-8')
        self.assertIn('--in-place and --diff are mutually exclusive', result)

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
            result = p.communicate()[0].decode('utf-8')

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
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [self.tempfile[1], '--recursive'],
                  stderr=PIPE)
        result = p.communicate()[1].decode('utf-8')
        self.assertIn('must be used with --in-place or --diff', result)

    def test_list_fixes(self):
        self._inner_setup('', options=['--list-fixes'])
        self.assertIn('E101', self.result)


class TestSpawnPEP8Process(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line, options=()):
        with open(self.tempfile[1], 'w') as temp_file:
            temp_file.write(line)
        opts, _ = autopep8.parse_args(list(options) + [self.tempfile[1]])

        # Monkey patch pep8 to trigger spawning
        original_pep8 = autopep8.pep8
        try:
            autopep8.pep8 = None
            self.result = autopep8.fix_file(
                filename=self.tempfile[1],
                opts=opts)
        finally:
            autopep8.pep8 = original_pep8

    def test_basic(self):
        line = "print('abc' )    \n1*1\n"
        fixed = "print('abc')\n1 * 1\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_verbose(self):
        line = "print('abc' )    \n1*1\n"
        fixed = "print('abc')\n1 * 1\n"
        sio = StringIO()
        with capture_stderr(sio):
            self._inner_setup(line, options=['--verbose'])
        self.assertEqual(self.result, fixed)
        self.assertIn('compatibility mode', sio.getvalue())

    def test_max_line_length(self):
        line = "foooooooooooooooooo('abcdefghijklmnopqrstuvwxyz')\n"
        fixed = "foooooooooooooooooo(\n    'abcdefghijklmnopqrstuvwxyz')\n"
        self._inner_setup(line, options=['--max-line-length=40'])
        self.assertEqual(self.result, fixed)

    def test_format_block_comments(self):
        line = """
foo(  )
# abc
bar()#bizz
  #blah blah
    #four space indentation
if True:
    1
""".lstrip()
        fixed = """
foo()
# abc
bar()  # bizz
  # blah blah
    # four space indentation
if True:
    1
""".lstrip()
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)


@contextlib.contextmanager
def temporary_file_context(text):
    tempfile = mkstemp()
    with open(tempfile[1], 'w') as temp_file:
        temp_file.write(text)
    yield tempfile[1]
    os.remove(tempfile[1])


class TestCoverage(unittest.TestCase):

    def test_fixpep8_class_constructor(self):
        line = "print 1\nprint 2\n"
        with temporary_file_context(line) as filename:
            pep8obj = autopep8.FixPEP8(filename, None)
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

    def test_standard_out_should_use_native_line_ending(self):
        line = '1\r\n2\r\n3\r\n'
        with temporary_file_context(line) as filename:
            process = Popen(list(AUTOPEP8_CMD_TUPLE) +
                            [filename],
                            stdout=PIPE)
            self.assertEqual(
                os.linesep.join(['1', '2', '3', '']),
                process.communicate()[0].decode('utf-8'))

    def test_standard_out_should_use_native_line_ending_with_cr_input(self):
        line = '1\r2\r3\r'
        with temporary_file_context(line) as filename:
            process = Popen(list(AUTOPEP8_CMD_TUPLE) +
                            [filename],
                            stdout=PIPE)
            self.assertEqual(
                os.linesep.join(['1', '2', '3', '']),
                process.communicate()[0].decode('utf-8'))


@contextlib.contextmanager
def disable_stderr():
    sio = StringIO()
    with capture_stderr(sio):
        yield


@contextlib.contextmanager
def capture_stderr(sio):
    _tmp = sys.stderr
    sys.stderr = sio
    try:
        yield
    finally:
        sys.stderr = _tmp


if __name__ == '__main__':
    unittest.main()

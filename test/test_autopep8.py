#!/usr/bin/env python
# coding: utf-8

from __future__ import unicode_literals

import os
import sys

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
                          '--omit=*/site-packages/*',
                          os.path.join(ROOT_DIR, 'autopep8.py'),)
else:
    # We need to specify the executable to make sure the correct Python
    # interpreter gets used.
    AUTOPEP8_CMD_TUPLE = (sys.executable,
                          os.path.join(ROOT_DIR,
                                       'autopep8.py'),)  # pragma: no cover


class UnitTests(unittest.TestCase):

    def test_find_newline_only_cr(self):
        source = ['print 1\r', 'print 2\r', 'print3\r']
        self.assertEqual(autopep8.CR, autopep8.find_newline(source))

    def test_find_newline_only_lf(self):
        source = ['print 1\n', 'print 2\n', 'print3\n']
        self.assertEqual(autopep8.LF, autopep8.find_newline(source))

    def test_find_newline_only_crlf(self):
        source = ['print 1\r\n', 'print 2\r\n', 'print3\r\n']
        self.assertEqual(autopep8.CRLF, autopep8.find_newline(source))

    def test_find_newline_cr1_and_lf2(self):
        source = ['print 1\n', 'print 2\r', 'print3\n']
        self.assertEqual(autopep8.LF, autopep8.find_newline(source))

    def test_find_newline_cr1_and_crlf2(self):
        source = ['print 1\r\n', 'print 2\r', 'print3\r\n']
        self.assertEqual(autopep8.CRLF, autopep8.find_newline(source))

    def test_detect_encoding(self):
        self.assertEqual(
            'utf-8',
            autopep8.detect_encoding(
                os.path.join(ROOT_DIR, 'setup.py')))

    def test_detect_encoding_with_cookie(self):
        self.assertEqual(
            'iso-8859-1',
            autopep8.detect_encoding(
                os.path.join(ROOT_DIR, 'test', 'iso_8859_1.py')))

    def test_read_from_filename_with_bad_encoding(self):
        """Bad encoding should not cause an exception."""
        self.assertEqual(
            '# -*- coding: zlatin-1 -*-\n',
            autopep8.read_from_filename(
                os.path.join(ROOT_DIR, 'test', 'bad_encoding.py')))

    def test_read_from_filename_with_bad_encoding2(self):
        """Bad encoding should not cause an exception."""
        # This causes a warning on Python 3.
        import warnings
        with warnings.catch_warnings(record=True):
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

    def test_break_multiline(self):
        self.assertEqual(
            'foo_bar_zap_bing_bang_boom(\n    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
            autopep8.break_multiline(
                'foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
                newline='\n', indent_word='    '))

    def test_break_multiline_with_percent(self):
        self.assertEqual(
            'foo_bar_zap_bing_bang_boom(\n    "                                                                         %s" %\n',
            autopep8.break_multiline(
                'foo_bar_zap_bing_bang_boom("                                                                         %s" %\n',
                newline='\n', indent_word='    '))

    def test_break_multiline_with_long_function(self):
        self.assertEqual(
            'foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom(\n'
            '    333,\n',
            autopep8.break_multiline(
                'foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom_foo_bar_zap_bing_bang_boom(333,\n',
                newline='\n', indent_word='    '))

    def test_break_multiline_should_not_break_too_short_line(self):
        self.assertEqual(
            None,
            autopep8.break_multiline(
                'fo(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333,\n',
                newline='\n', indent_word='    '))

    def test_break_multiline_should_not_modify_comment(self):
        self.assertEqual(
            None,
            autopep8.break_multiline(
                '# foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,\n',
                newline='\n', indent_word='    '))

    def test_break_multiline_should_not_modify_lonely_brace(self):
        self.assertEqual(
            None,
            autopep8.break_multiline(
                '(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 222, 222, 222, 222, 333,\n',
                newline='\n', indent_word='    '))

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

    def test_shorten_comment_should_not_split_urls(self):
        line = '# http://foo.bar/' + 'abc-' * 100 + '\n'
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
            autopep8.fix_e26('#abc'))

        self.assertEqual(
            '# abc',
            autopep8.fix_e26('####abc'))

        self.assertEqual(
            '# abc',
            autopep8.fix_e26('##   #   ##abc'))

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
            autopep8.fix_e26("""
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
            autopep8.fix_e26('#: abc'))

        self.assertEqual(
            '#!/bin/bash\n',
            autopep8.fix_e26('#!/bin/bash\n'))

    def test_format_block_comments_should_only_touch_real_comments(self):
        commented_out_code = '#x = 1'
        self.assertEqual(
            commented_out_code,
            autopep8.fix_e26(commented_out_code))

    def test_fix_file(self):
        self.assertIn(
            'import ',
            autopep8.fix_file(
                filename=os.path.join(ROOT_DIR, 'test', 'example.py')))

    def test_fix_file_with_diff(self):
        filename = os.path.join(ROOT_DIR, 'test', 'example.py')

        self.assertIn(
            '@@',
            autopep8.fix_file(
                filename=filename,
                options=autopep8.parse_args(['--diff', filename])[0]))

    def test_fix_lines(self):
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_lines(['print( 123 )\n'],
                               options=autopep8.parse_args([''])[0]))

    def test_fix_string(self):
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_string('print( 123 )\n'))

    def test_fix_string_with_empty_string(self):
        self.assertEqual(
            '',
            autopep8.fix_string(''))

    def test_fix_string_with_multiple_lines(self):
        self.assertEqual(
            'print(123)\nx = 4\n',
            autopep8.fix_string('print( 123 )\nx   =4'))

    def test_normalize_line_endings(self):
        self.assertEqual(
            ['abc\n', 'def\n', '123\n', 'hello\n', 'world\n'],
            autopep8.normalize_line_endings(
                ['abc\n', 'def\n', '123\r', 'hello\r\n', 'world\r']))

    def test_normalize_line_endings_with_crlf(self):
        self.assertEqual(
            ['abc\r\n', 'def\r\n', '123\r\n', 'hello\r\n', 'world\r\n'],
            autopep8.normalize_line_endings(
                ['abc\n', 'def\r\n', '123\r\n', 'hello\r\n', 'world\r']))

    def test_code_match(self):
        self.assertTrue(autopep8.code_match('E2', select='E2,E3', ignore=''))
        self.assertTrue(autopep8.code_match('E26', select='E2,E3', ignore=''))

        self.assertFalse(autopep8.code_match('E26', select='', ignore='E'))
        self.assertFalse(
            autopep8.code_match('E2', select='E2,E3', ignore='E2'))
        self.assertFalse(autopep8.code_match('E26', select='W', ignore=''))
        self.assertFalse(autopep8.code_match('E26', select='W', ignore='E1'))

    def test_split_at_offsets(self):
        self.assertEqual([''], autopep8.split_at_offsets('', [0]))
        self.assertEqual(['1234'], autopep8.split_at_offsets('1234', [0]))
        self.assertEqual(['1', '234'], autopep8.split_at_offsets('1234', [1]))
        self.assertEqual(['12', '34'], autopep8.split_at_offsets('1234', [2]))
        self.assertEqual(['12', '3', '4'],
                         autopep8.split_at_offsets('1234', [2, 3]))

    def test_split_at_offsets_with_out_of_order(self):
        self.assertEqual(['12', '3', '4'],
                         autopep8.split_at_offsets('1234', [3, 2]))

    def test_is_probably_inside_string_or_comment(self):
        self.assertTrue(autopep8.is_probably_inside_string_or_comment(
            '# abc', 1))

        self.assertFalse(autopep8.is_probably_inside_string_or_comment(
            'hello # abc', 1))

        self.assertTrue(autopep8.is_probably_inside_string_or_comment(
            '"abc"', 1))

        self.assertFalse(autopep8.is_probably_inside_string_or_comment(
            'hello "abc"', 1))

        self.assertTrue(autopep8.is_probably_inside_string_or_comment(
            '"abc"', 0))

        self.assertFalse(autopep8.is_probably_inside_string_or_comment(
            ' "abc"', 0))

    def test_fix_w6(self):
        self.assertEqual(
            'try: pass\nexcept ValueError as e: pass\n',
            autopep8.fix_w6('try: pass\nexcept ValueError, e: pass\n'))

        self.assertEqual(
            'while True: pass\n',
            autopep8.fix_w6('while 1: pass\n'))

        self.assertEqual(
            """\
import sys
sys.maxsize
""",
            autopep8.fix_w6("""\
import sys
sys.maxint
"""))

    def test_is_python_file(self):
        self.assertTrue(autopep8.is_python_file(
            os.path.join(ROOT_DIR, 'autopep8.py')))

        with temporary_file_context('#!/usr/bin/env python') as filename:
            self.assertTrue(autopep8.is_python_file(filename))

        with temporary_file_context('#!/usr/bin/python') as filename:
            self.assertTrue(autopep8.is_python_file(filename))

        with temporary_file_context('#!/usr/bin/python3') as filename:
            self.assertTrue(autopep8.is_python_file(filename))

        with temporary_file_context('#!/usr/bin/pythonic') as filename:
            self.assertFalse(autopep8.is_python_file(filename))

        with temporary_file_context('###!/usr/bin/python') as filename:
            self.assertFalse(autopep8.is_python_file(filename))

        self.assertFalse(autopep8.is_python_file(os.devnull))
        self.assertFalse(autopep8.is_python_file('/bin/bash'))

    def test_match_file(self):
        with temporary_file_context('', suffix='.py', prefix='.') as filename:
            self.assertFalse(autopep8.match_file(filename, exclude=[]),
                             msg=filename)

        self.assertFalse(autopep8.match_file(os.devnull, exclude=[]))

        with temporary_file_context('', suffix='.py', prefix='') as filename:
            self.assertTrue(autopep8.match_file(filename, exclude=[]),
                            msg=filename)

    def test_line_shortening_rank(self):
        self.assertGreater(
            autopep8.line_shortening_rank('(1\n+1)\n',
                                          newline='\n', indent_word='    '),
            autopep8.line_shortening_rank('(1+\n1)\n',
                                          newline='\n', indent_word='    '))

        self.assertGreaterEqual(
            autopep8.line_shortening_rank('(1+\n1)\n',
                                          newline='\n', indent_word='    '),
            autopep8.line_shortening_rank('(1+1)\n',
                                          newline='\n', indent_word='    '))

        self.assertGreater(
            autopep8.line_shortening_rank('\n',
                                          newline='\n', indent_word='    '),
            autopep8.line_shortening_rank('x\n',
                                          newline='\n', indent_word='    '))

        self.assertGreater(
            autopep8.line_shortening_rank('[foo(\nx) for x in y]\n',
                                          newline='\n', indent_word='    '),
            autopep8.line_shortening_rank('[foo(x)\nfor x in y]\n',
                                          newline='\n', indent_word='    '))

    def test_extract_code_from_function(self):
        def fix_e123():
            pass  # pragma: no cover
        self.assertEqual('e123', autopep8.extract_code_from_function(fix_e123))

        def foo():
            pass  # pragma: no cover
        self.assertEqual(None, autopep8.extract_code_from_function(foo))

        def fix_foo():
            pass  # pragma: no cover
        self.assertEqual(None, autopep8.extract_code_from_function(fix_foo))

        def e123():
            pass  # pragma: no cover
        self.assertEqual(None, autopep8.extract_code_from_function(e123))

        def fix_():
            pass  # pragma: no cover
        self.assertEqual(None, autopep8.extract_code_from_function(fix_))

    def test_reindenter(self):
        reindenter = autopep8.Reindenter(['if True:\n', '  pass\n'],
                                         '\n')

        self.assertEqual(set([1, 2]), reindenter.run())

        self.assertEqual(['if True:\n', '    pass\n'],
                         reindenter.fixed_lines())

    def test_reindenter_with_good_input(self):
        lines = ['if True:\n', '    pass\n']

        reindenter = autopep8.Reindenter(lines,
                                         '\n')

        self.assertEqual(set(), reindenter.run())

        self.assertEqual(lines,
                         reindenter.fixed_lines())

    def test_reindenter_should_leave_stray_comment_alone(self):
        lines = ['  #\n', 'if True:\n', '  pass\n']

        reindenter = autopep8.Reindenter(lines,
                                         '\n')

        self.assertEqual(set([1, 2, 3]), reindenter.run())

        self.assertEqual(['  #\n', 'if True:\n', '    pass\n'],
                         reindenter.fixed_lines())

    def test_fix_e225_avoid_failure(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='    1\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e225({'line': 1,
                               'column': 5}))

    def test_fix_e271_ignore_redundant(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='x = 1\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e271({'line': 1,
                               'column': 2}))

    def test_fix_e401_avoid_non_import(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='    1\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e401({'line': 1,
                               'column': 5}))

    def test_fix_e401_avoid_semicolon(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='import foo; import bar\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e401({'line': 1,
                               'column': 5}))

    def test_fix_e711_avoid_failure(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='None == x\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e711({'line': 1,
                               'column': 6}))

        self.assertEqual(
            [],
            fix_pep8.fix_e711({'line': 1,
                               'column': 700}))

        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='x <> None\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e711({'line': 1,
                               'column': 3}))

    def test_fix_e712_avoid_failure(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='True == x\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e712({'line': 1,
                               'column': 5}))

        self.assertEqual(
            [],
            fix_pep8.fix_e712({'line': 1,
                               'column': 700}))

        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='x != True\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e712({'line': 1,
                               'column': 3}))

        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='x == False\n')

        self.assertEqual(
            [],
            fix_pep8.fix_e712({'line': 1,
                               'column': 3}))

    def test_get_logical_with_empty_string(self):
        fix_pep8 = autopep8.FixPEP8(filename='',
                                    options=autopep8.parse_args(['']),
                                    contents='')

        self.assertEqual(None,
                         fix_pep8._get_logical({'line': 1,
                                                'column': 1}))

    def test_get_diff_text(self):
        # We ignore the first two lines since it differs on Python 2.6.
        self.assertEqual(
            """\
-foo
+bar
""",
            '\n'.join(autopep8.get_diff_text(['foo\n'],
                                             ['bar\n'],
                                             '').split('\n')[3:]))

    def test_get_diff_text_without_newline(self):
        # We ignore the first two lines since it differs on Python 2.6.
        self.assertEqual(
            """\
-foo
\\ No newline at end of file
+foo
""",
            '\n'.join(autopep8.get_diff_text(['foo'],
                                             ['foo\n'],
                                             '').split('\n')[3:]))

    def test_count_unbalanced_brackets(self):
        self.assertEqual(
            0,
            autopep8.count_unbalanced_brackets('()'))

        self.assertEqual(
            1,
            autopep8.count_unbalanced_brackets('('))

        self.assertEqual(
            2,
            autopep8.count_unbalanced_brackets('(['))

        self.assertEqual(
            1,
            autopep8.count_unbalanced_brackets('[])'))

        self.assertEqual(
            1,
            autopep8.count_unbalanced_brackets(
                "'','.join(['%s=%s' % (col, col)')"))

    def test_refactor_with_2to3(self):
        self.assertEqual(
            '1 in {}\n',
            autopep8.refactor_with_2to3('{}.has_key(1)\n', ['has_key']))

    def test_refactor_with_2to3_should_handle_syntax_error_gracefully(self):
        self.assertEqual(
            '{}.has_key(1\n',
            autopep8.refactor_with_2to3('{}.has_key(1\n', ['has_key']))

    def test_commented_out_code_lines(self):
        self.assertEqual(
            [1, 4],
            autopep8.commented_out_code_lines("""\
#x = 1
#Hello
#Hello world.
#html_use_index = True
"""))


class SystemTests(unittest.TestCase):

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_when_pep8_mistakes_first_tab_in_string(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multiline string.
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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_skip_if_bad_indentation(self):
        line = """
try:
\t    pass
    except:
        pass
""".lstrip()
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e101_skip_innocuous(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multiline string. If we don't filter the innocuous
        # report properly, the below command will take a long time.
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  ['-vvv', '--select=E101', '--diff',
                   os.path.join(ROOT_DIR, 'test', 'e101_example.py')],
                  stdout=PIPE, stderr=PIPE)
        output = [x.decode('utf-8') for x in p.communicate()][0]
        self.assertEqual('', output)

    def test_e111_short(self):
        line = 'class Dummy:\n\n  def __init__(self):\n    pass\n'
        fixed = 'class Dummy:\n\n    def __init__(self):\n        pass\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e111_long(self):
        line = 'class Dummy:\n\n     def __init__(self):\n          pass\n'
        fixed = 'class Dummy:\n\n    def __init__(self):\n        pass\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e12_large(self):
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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e12_with_bad_indentation(self):
        line = r"""


def bar():
    foo(1,
      2)


def baz():
     pass

    pass
"""
        fixed = r"""


def bar():
    foo(1,
        2)


def baz():
     pass

    pass
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e121_with_stupid_fallback(self):
        line = """\
list(''.join([
    '%d'
       % 1,
    list(''),
    ''
]))
"""
        fixed = """\
list(''.join([
    '%d'
    % 1,
    list(''),
    ''
]))
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e122_with_fallback(self):
        line = """\
foooo('',
      scripts=[''],
      classifiers=[
      'Development Status :: 4 - Beta',
      'Environment :: Console',
      'Intended Audience :: Developers',
      ])
"""
        fixed = """\
foooo('',
      scripts=[''],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
      ])
"""
        with autopep8_context(line, options=[]) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e123_with_escaped_newline(self):
        line = r"""
x = \
    (
)
"""
        fixed = r"""
x = \
    (
    )
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e125_with_multiline_string(self):
        line = """
for foo in '''
    abc
    123
    '''.strip().split():
    print(foo)
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(line, result)

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
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e126_should_not_interfere_with_other_fixes(self):
        line = """\
self.assertEqual('bottom 1',
    SimpleNamedNode.objects.filter(id__gt=1).exclude(
        name='bottom 3').filter(
            name__in=['bottom 3', 'bottom 1'])[0].name)
"""
        fixed = """\
self.assertEqual('bottom 1',
                 SimpleNamedNode.objects.filter(id__gt=1).exclude(
                     name='bottom 3').filter(
                     name__in=['bottom 3', 'bottom 1'])[0].name)
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e127_with_bracket_then_parenthesis(self):
        line = r"""
if True:
    foo = [food(1)
               for bar in bars]
""".lstrip()
        fixed = r"""
if True:
    foo = [food(1)
           for bar in bars]
""".lstrip()
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_w191(self):
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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e201(self):
        line = '(   1)\n'
        fixed = '(1)\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e202(self):
        line = '(1   )\n[2  ]\n{3  }\n'
        fixed = '(1)\n[2]\n{3}\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e202_skip_multiline(self):
        """We skip this since pep8 reports the error as being on line 1."""
        line = """

('''
a
b
c
''' )
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e202_skip_multiline_with_escaped_newline(self):
        """We skip this since pep8 reports the error as being on line 1."""
        line = r"""

('c\
' )
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e203_colon(self):
        line = '{4 : 3}\n'
        fixed = '{4: 3}\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e203_comma(self):
        line = '[1 , 2  , 3]\n'
        fixed = '[1, 2, 3]\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e203_semicolon(self):
        line = "print(a, end=' ') ; nl = 0\n"
        fixed = "print(a, end=' '); nl = 0\n"
        with autopep8_context(line, options=['--select=E203']) as result:
            self.assertEqual(fixed, result)

    def test_e203_with_newline(self):
        line = "print(a\n, end=' ')\n"
        fixed = "print(a, end=' ')\n"
        with autopep8_context(line, options=['--select=E203']) as result:
            self.assertEqual(fixed, result)

    def test_e211(self):
        line = 'd = [1, 2, 3]\nprint d  [0]\n'
        fixed = 'd = [1, 2, 3]\nprint d[0]\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e221(self):
        line = 'a = 1  + 1\n'
        fixed = 'a = 1 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e221_should_skip_multiline(self):
        line = '''
    def javascript(self):
        return u"""
<script type="text/javascript" src="++resource++ptg.shufflegallery/jquery.promptu-menu.js"></script>
<script type="text/javascript">
$(function(){
    $('ul.promptu-menu').promptumenu({width: %(width)i, height: %(height)i, rows: %(rows)i, columns: %(columns)i, direction: '%(direction)s', intertia: %(inertia)i, pages: %(pages)i});
\t$('ul.promptu-menu a').click(function(e) {
        e.preventDefault();
    });
    $('ul.promptu-menu a').dblclick(function(e) {
        window.location.replace($(this).attr("href"));
    });
});
</script>
        """  % {
        }
'''.lstrip()
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e222(self):
        line = 'a = 1 +  1\n'
        fixed = 'a = 1 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e223(self):
        line = 'a = 1	+ 1\n'  # include TAB
        fixed = 'a = 1 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e223_double(self):
        line = 'a = 1		+ 1\n'  # include TAB
        fixed = 'a = 1 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--ignore=W191']) as result:
            self.assertEqual(fixed, result)

    def test_e224(self):
        line = 'a = 11 +	1\n'    # include TAB
        fixed = 'a = 11 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e224_double(self):
        line = 'a = 11 +		1\n'    # include TAB
        fixed = 'a = 11 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--ignore=W191']) as result:
            self.assertEqual(fixed, result)

    def test_e225(self):
        line = '1+1\n2 +2\n3+ 3\n'
        fixed = '1 + 1\n2 + 2\n3 + 3\n'
        with autopep8_context(line, options=['--select=E,W']) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e226(self):
        line = '1*1\n2*2\n3*3\n'
        fixed = '1 * 1\n2 * 2\n3 * 3\n'
        with autopep8_context(line, options=['--select=E22']) as result:
            self.assertEqual(fixed, result)

    def test_e227(self):
        line = '1&1\n2&2\n3&3\n'
        fixed = '1 & 1\n2 & 2\n3 & 3\n'
        with autopep8_context(line, options=['--select=E22']) as result:
            self.assertEqual(fixed, result)

    def test_e228(self):
        line = '1%1\n2%2\n3%3\n'
        fixed = '1 % 1\n2 % 2\n3 % 3\n'
        with autopep8_context(line, options=['--select=E22']) as result:
            self.assertEqual(fixed, result)

    def test_e231(self):
        line = '[1,2,3]\n'
        fixed = '[1, 2, 3]\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e231_with_many_commas(self):
        fixed = str(list(range(200))) + '\n'
        import re
        line = re.sub(', ', ',', fixed)
        with autopep8_context(line, options=['--select=E231']) as result:
            self.assertEqual(fixed, result)

    def test_e231_with_colon_after_comma(self):
        """ws_comma fixer ignores this case."""
        line = 'a[b1,:]\n'
        fixed = 'a[b1, :]\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e231_should_only_do_ws_comma_once(self):
        """If we don't check appropriately, we end up doing ws_comma multiple
        times and skipping all other fixes."""
        line = """\
print( 1 )
foo[0,:]
bar[zap[0][0]:zig[0][0],:]
"""
        fixed = """\
print(1)
foo[0, :]
bar[zap[0][0]:zig[0][0], :]
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e241(self):
        line = 'l = (1,  2)\n'
        fixed = 'l = (1, 2)\n'
        with autopep8_context(line, options=['--select=E']) as result:
            self.assertEqual(fixed, result)

    def test_e241_should_be_enabled_by_aggressive(self):
        line = 'l = (1,  2)\n'
        fixed = 'l = (1, 2)\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e241_double(self):
        line = 'l = (1,   2)\n'
        fixed = 'l = (1, 2)\n'
        with autopep8_context(line, options=['--select=E']) as result:
            self.assertEqual(fixed, result)

    def test_e242(self):
        line = 'l = (1,\t2)\n'
        fixed = 'l = (1, 2)\n'
        with autopep8_context(line, options=['--select=E']) as result:
            self.assertEqual(fixed, result)

    def test_e242_double(self):
        line = 'l = (1,\t\t2)\n'
        fixed = 'l = (1, 2)\n'
        with autopep8_context(line, options=['--select=E']) as result:
            self.assertEqual(fixed, result)

    def test_e251(self):
        line = 'def a(arg = 1):\n    print arg\n'
        fixed = 'def a(arg=1):\n    print arg\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e251_with_escaped_newline(self):
        line = '1\n\n\ndef a(arg=\\\n1):\n    print(arg)\n'
        fixed = '1\n\n\ndef a(arg=1):\n    print(arg)\n'
        with autopep8_context(line, options=['--select=E251']) as result:
            self.assertEqual(fixed, result)

    def test_e251_with_calling(self):
        line = 'foo(bar= True)\n'
        fixed = 'foo(bar=True)\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e251_with_argument_on_next_line(self):
        line = 'foo(bar\n=None)\n'
        fixed = 'foo(bar=None)\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e261(self):
        line = "print 'a b '# comment\n"
        fixed = "print 'a b '  # comment\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e261_with_inline_commented_out_code(self):
        line = '1 # 0 + 0\n'
        fixed = '1  # 0 + 0\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e261_with_dictionary(self):
        line = 'd = {# comment\n1: 2}\n'
        fixed = 'd = {  # comment\n    1: 2}\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e261_with_dictionary_no_space(self):
        line = 'd = {#comment\n1: 2}\n'
        fixed = 'd = {  # comment\n    1: 2}\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e261_with_comma(self):
        line = '{1: 2 # comment\n , }\n'
        fixed = '{1: 2  # comment\n , }\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e262_more_space(self):
        line = "print 'a b '  #  comment\n"
        fixed = "print 'a b '  # comment\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e262_none_space(self):
        line = "print 'a b '  #comment\n"
        fixed = "print 'a b '  # comment\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e262_hash_in_string(self):
        line = "print 'a b  #string'  #comment\n"
        fixed = "print 'a b  #string'  # comment\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e262_hash_in_string_and_multiple_hashes(self):
        line = "print 'a b  #string'  #comment #comment\n"
        fixed = "print 'a b  #string'  # comment #comment\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e262_more_complex(self):
        line = "print 'a b '  #comment\n123\n"
        fixed = "print 'a b '  # comment\n123\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e271(self):
        line = 'True and  False\n'
        fixed = 'True and False\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e272(self):
        line = 'True  and False\n'
        fixed = 'True and False\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e273(self):
        line = 'True and\tFalse\n'
        fixed = 'True and False\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e274(self):
        line = 'True\tand False\n'
        fixed = 'True and False\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e301(self):
        line = 'class k:\n    s = 0\n    def f():\n        print 1\n'
        fixed = 'class k:\n    s = 0\n\n    def f():\n        print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e301_extended(self):
        line = 'class Foo:\n    def bar():\n        print 1\n'
        fixed = 'class Foo:\n\n    def bar():\n        print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e301_extended_with_docstring(self):
        line = '''\
class Foo(object):
    """Test."""
    def foo(self):



        """Test."""
        def bar():
            pass
'''
        fixed = '''\
class Foo(object):

    """Test."""

    def foo(self):
        """Test."""
        def bar():
            pass
'''
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e302(self):
        line = 'def f():\n    print 1\n\ndef ff():\n    print 2\n'
        fixed = 'def f():\n    print 1\n\n\ndef ff():\n    print 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e303(self):
        line = '\n\n\n# alpha\n\n1\n'
        fixed = '\n\n# alpha\n1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e303_extended(self):
        line = '''\
def foo():

    """Document."""
'''
        fixed = '''\
def foo():
    """Document."""
'''
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e304(self):
        line = '@contextmanager\n\ndef f():\n    print 1\n'
        fixed = '@contextmanager\ndef f():\n    print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e304_with_comment(self):
        line = '@contextmanager\n# comment\n\ndef f():\n    print 1\n'
        fixed = '@contextmanager\n# comment\ndef f():\n    print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e401(self):
        line = 'import os, sys\n'
        fixed = 'import os\nimport sys\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e401_with_indentation(self):
        line = 'def a():\n    import os, sys\n'
        fixed = 'def a():\n    import os\n    import sys\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e401_should_ignore_commented_comma(self):
        line = 'import bdist_egg, egg  # , not a module, neither is this\n'
        fixed = 'import bdist_egg\nimport egg  # , not a module, neither is this\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e401_should_ignore_commented_comma_with_indentation(self):
        line = 'if True:\n    import bdist_egg, egg  # , not a module, neither is this\n'
        fixed = 'if True:\n    import bdist_egg\n    import egg  # , not a module, neither is this\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e401_should_ignore_false_positive(self):
        line = 'import bdist_egg; bdist_egg.write_safety_flag(cmd.egg_info, safe)\n'
        with autopep8_context(line, options=['--select=E401']) as result:
            self.assertEqual(line, result)

    def test_e401_with_escaped_newline_case(self):
        line = 'import foo, \\\n    bar\n'
        fixed = 'import foo\nimport \\\n    bar\n'
        with autopep8_context(line, options=['--select=E401']) as result:
            self.assertEqual(fixed, result)

    def test_e501_basic(self):
        line = """

print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

print(111, 111, 111, 111, 222, 222, 222, 222,
      222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_return(self):
        line = """\
def foo():
    return bar('                                  ', '                 ', 1234353423243)
"""
        fixed = """\
def foo():
    return (
        bar('                                  ',
            '                 ', 1234353423243)
    )
"""
        with autopep8_context(line, options=['--aggressive',
                                             '--select=E501']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_inline_comments(self):
        line = """\
'                                                          '  # Long inline comments should be moved above.
if True:
    '                                                          '  # Long inline comments should be moved above.
"""
        fixed = """\
# Long inline comments should be moved above.
'                                                          '
if True:
    # Long inline comments should be moved above.
    '                                                          '
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_inline_comments_should_skip_edge_cases(self):
        line = """\
if True:
    x = \\
        '                                                          '  # Long inline comments should be moved above.
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_basic_should_prefer_balanced_brackets(self):
        line = """\
if True:
    reconstructed = iradon(radon(image), filter="ramp", interpolation="nearest")
"""
        fixed = """\
if True:
    reconstructed = iradon(
        radon(image), filter="ramp", interpolation="nearest")
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_very_long_line(self):
        line = """\
x = [3244234243234, 234234234324, 234234324, 23424234, 234234234, 234234, 234243, 234243, 234234234324, 234234324, 23424234, 234234234, 234234, 234243, 234243]
"""
        fixed = """\
x = [
    3244234243234,
    234234234324,
    234234324,
    23424234,
    234234234,
    234234,
    234243,
    234243,
    234234234324,
    234234324,
    23424234,
    234234234,
    234234,
    234243,
    234243]
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_shorten_at_commas_skip(self):
        line = """\
parser.add_argument('source_corpus', help='corpus name/path relative to an nltk_data directory')
parser.add_argument('target_corpus', help='corpus name/path relative to an nltk_data directory')
"""
        fixed = """\
parser.add_argument(
    'source_corpus',
    help='corpus name/path relative to an nltk_data directory')
parser.add_argument(
    'target_corpus',
    help='corpus name/path relative to an nltk_data directory')
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_shorter_length(self):
        line = "foooooooooooooooooo('abcdefghijklmnopqrstuvwxyz')\n"
        fixed = "foooooooooooooooooo(\n    'abcdefghijklmnopqrstuvwxyz')\n"
        with autopep8_context(line, options=['--max-line-length=40']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_indent(self):
        line = """

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_alone_with_indentation(self):
        line = """

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(fixed, result)

    def test_e501_alone_with_tuple(self):
        line = """

fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime', 'FLOAT')
                                                           ]
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(line, result)

    def test_e501_should_avoid_making_things_ugly(self):
        line = """\
x = ('                                                                                             ')
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(line, result)

    def test_e501_should_not_try_to_break_at_every_paren_in_arithmetic(self):
        line = """\
term3 = w6 * c5 * (8.0 * psi4 * (11.0 - 24.0 * t2) - 28 * psi3 * (1 - 6.0 * t2) + psi2 * (1 - 32 * t2) - psi * (2.0 * t2) + t4) / 720.0
this_should_be_shortened = ('                                                                 ', '            ')
"""
        fixed = """\
term3 = w6 * c5 * (8.0 * psi4 * (11.0 - 24.0 * t2) - 28 * psi3 *
                   (1 - 6.0 * t2) + psi2 * (1 - 32 * t2) - psi * (2.0 * t2) + t4) / 720.0
this_should_be_shortened = (
    '                                                                 ',
    '            ')
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_arithmetic_operator_with_indent(self):
        line = """

def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        fixed = r"""

def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + \
        222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_more_complicated(self):
        line = """

blahblah = os.environ.get('blahblah') or os.environ.get('blahblahblah') or os.environ.get('blahblahblahblah')
"""
        fixed = """

blahblah = os.environ.get('blahblah') or os.environ.get(
    'blahblahblah') or os.environ.get('blahblahblahblah')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_skip_even_more_complicated(self):
        line = """

if True:
    if True:
        if True:
            blah = blah.blah_blah_blah_bla_bl(blahb.blah, blah.blah,
                                              blah=blah.label, blah_blah=blah_blah,
                                              blah_blah2=blah_blah)
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_prefer_to_break_at_begnning(self):
        """We prefer not to leave part of the arguments hanging."""
        line = """

looooooooooooooong = foo(one, two, three, four, five, six, seven, eight, nine, ten)
"""
        fixed = """

looooooooooooooong = foo(
    one, two, three, four, five, six, seven, eight, nine, ten)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_avoid_breaking_at_empty_parentheses_if_possible(self):
        line = """\
someverylongindenttionwhatnot().foo().bar().baz("and here is a long string 123456789012345678901234567890")
"""
        fixed = """\
someverylongindenttionwhatnot().foo().bar().baz(
    "and here is a long string 123456789012345678901234567890")
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
                object = ModifyAction(
                    [MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine())
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_should_not_break_on_dot(self):
        line = """
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx('xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
""".lstrip()

        fixed = """
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx(
            'xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
""".lstrip()

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_comment(self):
        line = """123
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        fixed = """123
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap to be within 72 characters.

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_comment_should_not_modify_docstring(self):
        line = '''
def foo():
    """
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
    """
'''.lstrip()
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_should_not_interfere_with_non_comment(self):
        line = '''

"""
# not actually a comment %d. 12345678901234567890, 12345678901234567890, 12345678901234567890.
""" % (0,)
'''
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_should_cut_comment_pattern(self):
        line = """123
# -- Useless lines ----------------------------------------------------------------------
321
"""
        fixed = """123
# -- Useless lines -------------------------------------------------------
321
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_function_should_not_break_on_colon(self):
        line = r"""
class Useless(object):

    def _table_field_is_plain_widget(self, widget):
        if widget.__class__ == Widget or\
                (widget.__class__ == WidgetMeta and Widget in widget.__bases__):
            return True

        return False
""".lstrip()

        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_with_aggressive(self):
        line = """\
models = {
    'auth.group': {
        'Meta': {'object_name': 'Group'},
        'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
    },
    'auth.permission': {
        'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
        'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
    },
}
"""
        fixed = """\
models = {
    'auth.group': {
        'Meta': {'object_name': 'Group'},
        'permissions': ('django.db.models.fields.related.ManyToManyField', [], {
                        'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
    },
    'auth.permission': {
        'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')",
                 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
        'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
    },
}
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_multiple_keys_and_aggressive(self):
        line = """\
one_two_three_four_five_six = {'one two three four five': 12345, 'asdfsdflsdkfjl sdflkjsdkfkjsfjsdlkfj sdlkfjlsfjs': '343',
                               1: 1}
"""
        fixed = """\
one_two_three_four_five_six = {
    'one two three four five': 12345,
    'asdfsdflsdkfjl sdflkjsdkfkjsfjsdlkfj sdlkfjlsfjs': '343',
    1: 1}
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_should_ignore_imports(self):
        line = """\
import logging, os, bleach, commonware, urllib2, json, time, requests, urlparse, re
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(line, result)

    def test_e501_should_not_do_useless_things(self):
        line = """\
foo('                                                                            ')
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_aggressive_with_percent(self):
        line = """\
raise MultiProjectException("Ambiguous workspace: %s=%s, %s" % ( varname, varname_path, os.path.abspath(config_filename)))
"""
        fixed = """\
raise MultiProjectException(
    "Ambiguous workspace: %s=%s, %s" %
    (varname, varname_path, os.path.abspath(config_filename)))
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_with_def(self):
        line = """\
def foo(sldfkjlsdfsdf, kksdfsdfsf,sdfsdfsdf, sdfsdfkdk, szdfsdfsdf, sdfsdfsdfsdlkfjsdlf, sdfsdfddf,sdfsdfsfd, sdfsdfdsf):
    pass
"""
        fixed = """\
def foo(sldfkjlsdfsdf, kksdfsdfsf, sdfsdfsdf, sdfsdfkdk,
        szdfsdfsdf, sdfsdfsdfsdlkfjsdlf, sdfsdfddf, sdfsdfsfd, sdfsdfdsf):
    pass
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_more_aggressive_with_def(self):
        line = """\
def foo(sldfkjlsdfsdf, kksdfsdfsf,sdfsdfsdf, sdfsdfkdk, szdfsdfsdf, sdfsdfsdfsdlkfjsdlf, sdfsdfddf,sdfsdfsfd, sdfsdfdsf):
    pass
"""
        fixed = """\


def foo(
    sldfkjlsdfsdf,
    kksdfsdfsf,
    sdfsdfsdf,
    sdfsdfkdk,
    szdfsdfsdf,
    sdfsdfsdfsdlkfjsdlf,
    sdfsdfddf,
    sdfsdfsfd,
        sdfsdfdsf):
    pass
"""
        with autopep8_context(line, options=['--aggressive', '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e502(self):
        line = "print('abc'\\\n      'def')\n"
        fixed = "print('abc'\n      'def')\n"
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e701(self):
        line = 'if True: print True\n'
        fixed = 'if True:\n    print True\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e701_with_escaped_newline(self):
        line = 'if True:\\\nprint True\n'
        fixed = 'if True:\n    print True\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e701_with_escaped_newline_and_spaces(self):
        line = 'if True:    \\   \nprint True\n'
        fixed = 'if True:\n    print True\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702(self):
        line = 'print 1; print 2\n'
        fixed = 'print 1\nprint 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_at_end(self):
        line = 'print 1;\n'
        fixed = 'print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_and_space_at_end(self):
        line = 'print 1; \n'
        fixed = 'print 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_whitespace(self):
        line = 'print 1 ; print 2\n'
        fixed = 'print 1\nprint 2\n'
        with autopep8_context(line, options=['--select=E702']) as result:
            self.assertEqual(fixed, result)

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

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_escaped_newline(self):
        line = '1; \\\n2\n'
        fixed = '1\n2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_escaped_newline_with_indentation(self):
        line = '1; \\\n    2\n'
        fixed = '1\n2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--select=E,W']) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_in_string(self):
        line = 'print(";");\n'
        fixed = 'print(";")\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_in_string_to_the_right(self):
        line = 'x = "x"; y = "y;y"\n'
        fixed = 'x = "x"\ny = "y;y"\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_triple_quote(self):
        line = '"""\n      hello\n   """; 1\n'
        fixed = '"""\n      hello\n   """\n1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_triple_quote_and_indent(self):
        line = '    """\n      hello\n   """; 1\n'
        fixed = '    """\n      hello\n   """\n    1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_after_string(self):
        line = """
raise IOError('abc '
              'def.');
""".lstrip()
        fixed = """
raise IOError('abc '
              'def.')
""".lstrip()
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e711(self):
        line = 'foo == None\n'
        fixed = 'foo is None\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e711_in_conditional(self):
        line = 'if foo == None and None == foo:\npass\n'
        fixed = 'if foo is None and None == foo:\npass\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e711_in_conditional_with_multiple_instances(self):
        line = 'if foo == None and bar == None:\npass\n'
        fixed = 'if foo is None and bar is None:\npass\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e711_with_not_equals_none(self):
        line = 'foo != None\n'
        fixed = 'foo is not None\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e712(self):
        line = 'foo == True\n'
        fixed = 'foo\n'
        with autopep8_context(line, options=['--aggressive', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_in_conditional_with_multiple_instances(self):
        line = 'if foo == True and bar == True:\npass\n'
        fixed = 'if foo and bar:\npass\n'
        with autopep8_context(line, options=['--aggressive', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_with_false(self):
        line = 'foo != False\n'
        fixed = 'foo\n'
        with autopep8_context(line, options=['--aggressive', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_only_if_aggressive(self):
        line = 'foo == True\n'
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e711_and_e712(self):
        line = 'if (foo == None and bar == True) or (foo != False and bar != None):\npass\n'
        fixed = 'if (foo is None and bar) or (foo and bar is not None):\npass\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e721(self):
        line = "type('') == type('')\n"
        fixed = "isinstance('', type(''))\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e721_with_str(self):
        line = "str == type('')\n"
        fixed = "isinstance('', str)\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e721_in_conditional(self):
        line = "if str == type(''):\n    pass\n"
        fixed = "if isinstance('', str):\n    pass\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_should_preserve_vertical_tab(self):
        line = """
#Memory Bu\vffer Register:
""".lstrip()
        fixed = """
# Memory Bu\vffer Register:
""".lstrip()

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w291(self):
        line = "print 'a b '\t \n"
        fixed = "print 'a b '\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w291_with_comment(self):
        line = "print 'a b '  # comment\t \n"
        fixed = "print 'a b '  # comment\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w292(self):
        line = '1\n2'
        fixed = '1\n2\n'
        with autopep8_context(line, options=['--aggressive',
                                             '--select=W292']) as result:
            self.assertEqual(fixed, result)

    def test_w293(self):
        line = '1\n \n2\n'
        fixed = '1\n\n2\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w391(self):
        line = '  \n'
        fixed = ''
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w391_more_complex(self):
        line = '123\n456\n  \n'
        fixed = '123\n456\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601(self):
        line = 'a = {0: 1}\na.has_key(0)\n'
        fixed = 'a = {0: 1}\n0 in a\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_word(self):
        line = 'my_dict = {0: 1}\nmy_dict.has_key(0)\n'
        fixed = 'my_dict = {0: 1}\n0 in my_dict\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_conditional(self):
        line = 'a = {0: 1}\nif a.has_key(0):\n    print 1\n'
        fixed = 'a = {0: 1}\nif 0 in a:\n    print 1\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_self(self):
        line = 'self.a.has_key(0)\n'
        fixed = '0 in self.a\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_self_with_conditional(self):
        line = 'if self.a.has_key(0):\n    print 1\n'
        fixed = 'if 0 in self.a:\n    print 1\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_with_multiple(self):
        line = 'a.has_key(0) and b.has_key(0)\n'
        fixed = '0 in a and 0 in b\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_with_multiple_nested(self):
        line = 'alpha.has_key(nested.has_key(12)) and beta.has_key(1)\n'
        fixed = '(12 in nested) in alpha and 1 in beta\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_with_more_complexity(self):
        line = 'y.has_key(0) + x.has_key(x.has_key(0) + x.has_key(x.has_key(0) + x.has_key(1)))\n'
        fixed = '(0 in y) + ((0 in x) + ((0 in x) + (1 in x) in x) in x)\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_precedence(self):
        line = 'if self.a.has_key(1 + 2):\n    print 1\n'
        fixed = 'if 1 + 2 in self.a:\n    print 1\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_with_parens(self):
        line = 'foo(12) in alpha\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w601_with_multiline(self):
        line = """

a.has_key(
    0
)
""".lstrip()
        fixed = '0 in a\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

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
# éはe
correct = 'good syntax ?' in dict()
""".lstrip()

        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_arg_is_string(self):
        line = "raise ValueError, \"w602 test\"\n"
        fixed = "raise ValueError(\"w602 test\")\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_arg_is_string_with_comment(self):
        line = "raise ValueError, \"w602 test\"  # comment\n"
        fixed = "raise ValueError(\"w602 test\")  # comment\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_skip_ambiguous_case(self):
        line = "raise 'a', 'b', 'c'\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w602_with_logic(self):
        line = "raise TypeError, e or 'hello'\n"
        fixed = "raise TypeError(e or 'hello')\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_triple_quotes(self):
        line = 'raise ValueError, """hello"""\n1\n'
        fixed = 'raise ValueError("""hello""")\n1\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline(self):
        line = 'raise ValueError, """\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_with_complex_multiline(self):
        line = 'raise ValueError, """\nhello %s %s""" % (\n    1, 2)\n'
        fixed = 'raise ValueError("""\nhello %s %s""" % (\n    1, 2))\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_with_trailing_spaces(self):
        line = 'raise ValueError, """\nhello"""    \n'
        fixed = 'raise ValueError("""\nhello""")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_with_escaped_newline(self):
        line = 'raise ValueError, \\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_with_escaped_newline_and_comment(self):
        line = 'raise ValueError, \\\n"""\nhello"""  # comment\n'
        fixed = 'raise ValueError("""\nhello""")  # comment\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_with_multiple_escaped_newlines(self):
        line = 'raise ValueError, \\\n\\\n\\\n"""\nhello"""\n'
        fixed = 'raise ValueError("""\nhello""")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_with_nested_quotes(self):
        line = 'raise ValueError, """hello\'\'\'blah"a"b"c"""\n'
        fixed = 'raise ValueError("""hello\'\'\'blah"a"b"c""")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_with_multiline_with_single_quotes(self):
        line = "raise ValueError, '''\nhello'''\n"
        fixed = "raise ValueError('''\nhello''')\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiline_string_stays_the_same(self):
        line = 'raise """\nhello"""\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w602_escaped_lf(self):
        line = 'raise ValueError, \\\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_escaped_crlf(self):
        line = 'raise ValueError, \\\r\n"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_indentation(self):
        line = 'def foo():\n    raise ValueError, "hello"\n'
        fixed = 'def foo():\n    raise ValueError("hello")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_escaped_cr(self):
        line = 'raise ValueError, \\\r"hello"\n'
        fixed = 'raise ValueError("hello")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_multiple_statements(self):
        line = 'raise ValueError, "hello";print 1\n'
        fixed = 'raise ValueError("hello")\nprint 1\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_raise_argument_with_indentation(self):
        line = 'if True:\n    raise ValueError, "error"\n'
        fixed = 'if True:\n    raise ValueError("error")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_skip_raise_argument_triple(self):
        line = 'raise ValueError, "info", traceback\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w602_skip_raise_argument_triple_with_comment(self):
        line = 'raise ValueError, "info", traceback  # comment\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w602_raise_argument_triple_fake(self):
        line = 'raise ValueError, "info, info2"\n'
        fixed = 'raise ValueError("info, info2")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_with_list_comprehension(self):
        line = 'raise Error, [x[0] for x in probs]\n'
        fixed = 'raise Error([x[0] for x in probs])\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_with_bad_syntax(self):
        line = "raise Error, 'abc\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_w603(self):
        line = 'if 2 <> 2:\n    print False'
        fixed = 'if 2 != 2:\n    print False\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w604(self):
        line = '`1`\n'
        fixed = 'repr(1)\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w604_with_multiple_instances(self):
        line = '``1`` + ``b``\n'
        fixed = 'repr(repr(1)) + repr(repr(b))\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w604_with_multiple_lines(self):
        line = '`(1\n      )`\n'
        fixed = 'repr((1\n      ))\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_trailing_whitespace_in_multiline_string(self):
        line = 'x = """ \nhello"""    \n'
        fixed = 'x = """ \nhello"""\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_trailing_whitespace_in_multiline_string_aggressive(self):
        line = 'x = """ \nhello"""    \n'
        fixed = 'x = """\nhello"""\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_execfile_in_lambda_should_not_be_modified(self):
        """Modifying this to the exec() form is invalid in Python 2."""
        line = 'lambda: execfile("foo.py")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_range(self):
        line = 'print( 1 )\nprint( 2 )\n print( 3 )\n'
        fixed = 'print( 1 )\nprint(2)\n print( 3 )\n'
        with autopep8_context(line, options=['--range', '2', '2']) as result:
            self.assertEqual(fixed, result)


class CommandLineTests(unittest.TestCase):

    def test_diff(self):
        line = "'abc'  \n"
        fixed = "-'abc'  \n+'abc'\n"
        with autopep8_subprocess(line, ['--diff']) as result:
            self.assertEqual(fixed, '\n'.join(result.split('\n')[3:]))

    def test_diff_with_empty_file(self):
        with autopep8_subprocess('', ['--diff']) as result:
            self.assertEqual('\n'.join(result.split('\n')[3:]), '')

    def test_diff_with_nonexistent_file(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['--diff', 'non_existent_file'],
                  stdout=PIPE, stderr=PIPE)
        error = p.communicate()[1].decode('utf-8')
        self.assertIn('non_existent_file', error)

    def test_pep8_passes(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        with autopep8_subprocess(line, ['--pep8-passes', '0']) as result:
            self.assertEqual(fixed, result)

    def test_pep8_ignore(self):
        line = "'abc'  \n"
        with autopep8_subprocess(line, ['--ignore=E,W']) as result:
            self.assertEqual(line, result)

    def test_help(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['-h'],
                  stdout=PIPE)
        self.assertIn('Usage:', p.communicate()[0].decode('utf-8'))

    def test_verbose(self):
        line = 'bad_syntax)'
        with temporary_file_context(line) as filename:
            p = Popen(list(AUTOPEP8_CMD_TUPLE) + [filename, '-vvv'],
                      stdout=PIPE, stderr=PIPE)
            verbose_error = p.communicate()[1].decode('utf-8')
        self.assertIn("'fix_e901' is not defined", verbose_error)

    def test_verbose_diff(self):
        line = '+'.join(100 * ['323424234234'])
        with temporary_file_context(line) as filename:
            p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                      [filename, '-vvvv', '--diff'],
                      stdout=PIPE, stderr=PIPE)
            verbose_error = p.communicate()[1].decode('utf-8')
        self.assertIn('------------', verbose_error)

    def test_in_place(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"

        with temporary_file_context(line) as filename:
            p = Popen(list(AUTOPEP8_CMD_TUPLE) + [filename, '--in-place'])
            p.wait()

            with open(filename) as f:
                self.assertEqual(fixed, f.read())

    def test_parallel_jobs(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"

        with temporary_file_context(line) as filename_a:
            with temporary_file_context(line) as filename_b:
                p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                          [filename_a, filename_b, '--jobs=3', '--in-place'])
                p.wait()

                with open(filename_a) as f:
                    self.assertEqual(fixed, f.read())

                with open(filename_b) as f:
                    self.assertEqual(fixed, f.read())

    def test_parallel_jobs_with_automatic_cpu_count(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"

        with temporary_file_context(line) as filename_a:
            with temporary_file_context(line) as filename_b:
                p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                          [filename_a, filename_b, '--jobs=0', '--in-place'])
                p.wait()

                with open(filename_a) as f:
                    self.assertEqual(fixed, f.read())

                with open(filename_b) as f:
                    self.assertEqual(fixed, f.read())

    def test_in_place_with_empty_file(self):
        line = ''

        with temporary_file_context(line) as filename:
            p = Popen(list(AUTOPEP8_CMD_TUPLE) + [filename, '--in-place'])
            p.wait()
            self.assertEqual(0, p.returncode)

            with open(filename) as f:
                self.assertEqual(f.read(), line)

    def test_in_place_and_diff(self):
        line = "'abc'  \n"
        with temporary_file_context(line) as filename:
            p = Popen(
                list(AUTOPEP8_CMD_TUPLE) + [filename,
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
                output.write('123  \n')

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

    def test_recursive_should_not_crash_on_unicode_filename(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  [os.path.join(ROOT_DIR, 'test', 'example'),
                   '--recursive',
                   '--diff'],
                  stdout=PIPE)
        self.assertFalse(p.communicate()[0])
        self.assertEqual(0, p.returncode)

    def test_recursive_should_ignore_hidden(self):
        import tempfile
        temp_directory = tempfile.mkdtemp(dir='.')
        temp_subdirectory = tempfile.mkdtemp(prefix='.', dir=temp_directory)
        try:
            with open(os.path.join(temp_subdirectory, 'a.py'), 'w') as output:
                output.write("'abc'  \n")

            p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                      [temp_directory, '--recursive', '--diff'],
                      stdout=PIPE)
            result = p.communicate()[0].decode('utf-8')

            self.assertEqual(0, p.returncode)
            self.assertEqual('', result)
        finally:
            import shutil
            shutil.rmtree(temp_directory)

    def test_exclude(self):
        import tempfile
        temp_directory = tempfile.mkdtemp(dir='.')
        try:
            with open(os.path.join(temp_directory, 'a.py'), 'w') as output:
                output.write("'abc'  \n")

            os.mkdir(os.path.join(temp_directory, 'd'))
            with open(os.path.join(temp_directory, 'd', 'b.py'),
                      'w') as output:
                output.write('123  \n')

            p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                      [temp_directory, '--recursive', '--exclude=a*',
                       '--diff'],
                      stdout=PIPE)
            result = p.communicate()[0].decode('utf-8')

            self.assertNotIn('abc', result)
            self.assertIn('123', result)
        finally:
            import shutil
            shutil.rmtree(temp_directory)

    def test_invalid_option_combinations(self):
        line = "'abc'  \n"
        with temporary_file_context(line) as filename:
            for options in [['--recursive', filename],  # without --diff
                            ['--jobs=2', filename],  # without --diff
                            ['--exclude=foo', filename],  # without --recursive
                            ['--max-line-length=0', filename],
                            [],  # no argument
                            ['-', '--in-place'],
                            ['-', '--recursive'],
                            ['-', filename],
                            ]:
                p = Popen(list(AUTOPEP8_CMD_TUPLE) + options,
                          stderr=PIPE)
                result = p.communicate()[1].decode('utf-8')
                self.assertNotEqual(0, p.returncode, msg=str(options))
                self.assertTrue(len(result))

    def test_list_fixes(self):
        with autopep8_subprocess('', options=['--list-fixes']) as result:
            self.assertIn('E101', result)

    def test_fixpep8_class_constructor(self):
        line = 'print 1\nprint 2\n'
        with temporary_file_context(line) as filename:
            pep8obj = autopep8.FixPEP8(filename, None)
        self.assertEqual(''.join(pep8obj.source), line)

    def test_inplace_with_multi_files(self):
        exception = None
        with disable_stderr():
            try:
                autopep8.parse_args(['test.py', 'dummy.py'])
            except SystemExit as e:
                exception = e
        self.assertTrue(exception)
        self.assertEqual(exception.code, 2)

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

    def test_standard_in(self):
        line = 'print( 1 )\n'
        fixed = 'print(1)' + os.linesep
        process = Popen(list(AUTOPEP8_CMD_TUPLE) +
                        ['-'],
                        stdout=PIPE,
                        stdin=PIPE)
        self.assertEqual(
            fixed,
            process.communicate(line.encode('utf-8'))[0].decode('utf-8'))


@contextlib.contextmanager
def autopep8_context(line, options=None):
    if not options:
        options = []

    with temporary_file_context(line) as filename:
        options, _ = autopep8.parse_args([filename] + list(options))
        yield autopep8.fix_file(filename=filename, options=options)


@contextlib.contextmanager
def autopep8_subprocess(line, options):
    with temporary_file_context(line) as filename:
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [filename] + options,
                  stdout=PIPE)
        yield p.communicate()[0].decode('utf-8')


@contextlib.contextmanager
def temporary_file_context(text, suffix='', prefix=''):
    tempfile = mkstemp(suffix=suffix, prefix=prefix)
    os.close(tempfile[0])
    with autopep8.open_with_encoding(tempfile[1],
                                     encoding='utf-8',
                                     mode='w') as temp_file:
        temp_file.write(text)
    yield tempfile[1]
    os.remove(tempfile[1])


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

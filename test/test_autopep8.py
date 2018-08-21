#!/usr/bin/env python
# coding: utf-8

"""Test suite for autopep8.

Unit tests go in "UnitTests". System tests go in "SystemTests".

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import sys

import contextlib
import io
import shutil
from subprocess import Popen, PIPE
from tempfile import mkstemp
import tempfile
import tokenize
import unittest
import warnings

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

ROOT_DIR = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

sys.path.insert(0, ROOT_DIR)
import autopep8


FAKE_CONFIGURATION = os.path.join(ROOT_DIR, 'test', 'fake_configuration')
FAKE_PYCODESTYLE_CONFIGURATION = os.path.join(
    ROOT_DIR, 'test', 'fake_pycodestyle_configuration'
)

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

    maxDiff = None

    def test_compile_value_error(self):
        source = '"\\xhh" \\'
        self.assertFalse(autopep8.check_syntax(source))

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

    def test_find_newline_should_default_to_lf(self):
        self.assertEqual(autopep8.LF, autopep8.find_newline([]))
        self.assertEqual(autopep8.LF, autopep8.find_newline(['', '']))

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

    def test_readlines_from_file_with_bad_encoding(self):
        """Bad encoding should not cause an exception."""
        self.assertEqual(
            ['# -*- coding: zlatin-1 -*-\n'],
            autopep8.readlines_from_file(
                os.path.join(ROOT_DIR, 'test', 'bad_encoding.py')))

    def test_readlines_from_file_with_bad_encoding2(self):
        """Bad encoding should not cause an exception."""
        # This causes a warning on Python 3.
        with warnings.catch_warnings(record=True):
            self.assertTrue(autopep8.readlines_from_file(
                os.path.join(ROOT_DIR, 'test', 'bad_encoding2.py')))

    def test_fix_whitespace(self):
        self.assertEqual(
            'a b',
            autopep8.fix_whitespace('a    b', offset=1, replacement=' '))

    def test_fix_whitespace_with_tabs(self):
        self.assertEqual(
            'a b',
            autopep8.fix_whitespace('a\t  \t  b', offset=1, replacement=' '))

    def test_multiline_string_lines(self):
        self.assertEqual(
            set([2]),
            autopep8.multiline_string_lines(
                """\
'''
'''
"""))

    def test_multiline_string_lines_with_many(self):
        self.assertEqual(
            set([2, 7, 10, 11, 12]),
            autopep8.multiline_string_lines(
                """\
'''
'''
''''''
''''''
''''''
'''
'''

'''


'''
"""))

    def test_multiline_string_should_not_report_single_line(self):
        self.assertEqual(
            set(),
            autopep8.multiline_string_lines(
                """\
'''abc'''
"""))

    def test_multiline_string_should_not_report_docstrings(self):
        self.assertEqual(
            set([5]),
            autopep8.multiline_string_lines(
                """\
def foo():
    '''Foo.
    Bar.'''
    hello = '''
'''
"""))

    def test_supported_fixes(self):
        self.assertIn('E121', [f[0] for f in autopep8.supported_fixes()])

    def test_shorten_comment(self):
        self.assertEqual('# ' + '=' * 72 + '\n',
                         autopep8.shorten_comment('# ' + '=' * 100 + '\n',
                                                  max_line_length=79))

    def test_shorten_comment_should_not_split_numbers(self):
        line = '# ' + '0' * 100 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  max_line_length=79))

    def test_shorten_comment_should_not_split_words(self):
        line = '# ' + 'a' * 100 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  max_line_length=79))

    def test_shorten_comment_should_not_split_urls(self):
        line = '# http://foo.bar/' + 'abc-' * 100 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  max_line_length=79))

    def test_shorten_comment_should_not_modify_special_comments(self):
        line = '#!/bin/blah ' + ' x' * 90 + '\n'
        self.assertEqual(line,
                         autopep8.shorten_comment(line,
                                                  max_line_length=79))

    def test_format_block_comments(self):
        self.assertEqual(
            '# abc',
            autopep8.fix_e265('#abc'))

        self.assertEqual(
            '# abc',
            autopep8.fix_e265('####abc'))

        self.assertEqual(
            '# abc',
            autopep8.fix_e265('##   #   ##abc'))

        self.assertEqual(
            '# abc "# noqa"',
            autopep8.fix_e265('# abc "# noqa"'))

        self.assertEqual(
            '# *abc',
            autopep8.fix_e265('#*abc'))

    def test_format_block_comments_should_leave_outline_alone(self):
        line = """\
###################################################################
##   Some people like these crazy things. So leave them alone.   ##
###################################################################
"""
        self.assertEqual(line, autopep8.fix_e265(line))

        line = """\
#################################################################
#   Some people like these crazy things. So leave them alone.   #
#################################################################
"""
        self.assertEqual(line, autopep8.fix_e265(line))

    def test_format_block_comments_with_multiple_lines(self):
        self.assertEqual(
            """\
# abc
  # blah blah
    # four space indentation
''' #do not modify strings
#do not modify strings
#do not modify strings
#do not modify strings'''
#
""",
            autopep8.fix_e265("""\
# abc
  #blah blah
    #four space indentation
''' #do not modify strings
#do not modify strings
#do not modify strings
#do not modify strings'''
#
"""))

    def test_format_block_comments_should_not_corrupt_special_comments(self):
        self.assertEqual(
            '#: abc',
            autopep8.fix_e265('#: abc'))

        self.assertEqual(
            '#!/bin/bash\n',
            autopep8.fix_e265('#!/bin/bash\n'))

    def test_format_block_comments_should_only_touch_real_comments(self):
        commented_out_code = '#x = 1'
        self.assertEqual(
            commented_out_code,
            autopep8.fix_e265(commented_out_code))

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
                options=autopep8.parse_args(['--diff', filename])))

    def test_fix_lines(self):
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_lines(['print( 123 )\n'],
                               options=autopep8.parse_args([''])))

    def test_fix_code(self):
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_code('print( 123 )\n'))

    def test_fix_code_with_empty_string(self):
        self.assertEqual(
            '',
            autopep8.fix_code(''))

    def test_fix_code_with_multiple_lines(self):
        self.assertEqual(
            'print(123)\nx = 4\n',
            autopep8.fix_code('print( 123 )\nx   =4'))

    def test_fix_code_byte_string(self):
        """This feature is here for friendliness to Python 2."""
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_code(b'print( 123 )\n'))

    def test_fix_code_with_options(self):
        self.assertEqual(
            'print(123)\n',
            autopep8.fix_code('print( 123 )\n', options={'ignore': ['W']}))

        self.assertEqual(
            'print( 123 )\n',
            autopep8.fix_code('print( 123 )\n', options={'ignore': ['E']}))

        self.assertEqual(
            'y in x\n',
            autopep8.fix_code('x.has_key(y)\n', options={'aggressive': True}))

    def test_fix_code_with_bad_options(self):
        with self.assertRaises(ValueError):
            autopep8.fix_code('print( 123 )\n', options={'ignor': ['W']})

        with self.assertRaises(ValueError):
            autopep8.fix_code('print( 123 )\n', options={'ignore': 'W'})

    def test_normalize_line_endings(self):
        self.assertEqual(
            ['abc\n', 'def\n', '123\n', 'hello\n', 'world\n'],
            autopep8.normalize_line_endings(
                ['abc\n', 'def\n', '123\n', 'hello\r\n', 'world\r'],
                '\n'))

    def test_normalize_line_endings_with_crlf(self):
        self.assertEqual(
            ['abc\r\n', 'def\r\n', '123\r\n', 'hello\r\n', 'world\r\n'],
            autopep8.normalize_line_endings(
                ['abc\n', 'def\r\n', '123\r\n', 'hello\r\n', 'world\r'],
                '\r\n'))

    def test_normalize_multiline(self):
        self.assertEqual('def foo(): pass',
                         autopep8.normalize_multiline('def foo():'))

        self.assertEqual('def _(): return 1',
                         autopep8.normalize_multiline('return 1'))

        self.assertEqual('@decorator\ndef _(): pass',
                         autopep8.normalize_multiline('@decorator\n'))

        self.assertEqual('class A: pass',
                         autopep8.normalize_multiline('class A:'))

    def test_code_match(self):
        self.assertTrue(autopep8.code_match('E2', select=['E2', 'E3'],
                                            ignore=[]))
        self.assertTrue(autopep8.code_match('E26', select=['E2', 'E3'],
                                            ignore=[]))

        self.assertFalse(autopep8.code_match('E26', select=[], ignore=['E']))
        self.assertFalse(autopep8.code_match('E2', select=['E2', 'E3'],
                                             ignore=['E2']))
        self.assertFalse(autopep8.code_match('E26', select=['W'], ignore=['']))
        self.assertFalse(autopep8.code_match('E26', select=['W'],
                                             ignore=['E1']))

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

    def test_fix_2to3(self):
        self.assertEqual(
            'try: pass\nexcept ValueError as e: pass\n',
            autopep8.fix_2to3('try: pass\nexcept ValueError, e: pass\n'))

        self.assertEqual(
            'while True: pass\n',
            autopep8.fix_2to3('while 1: pass\n'))

        self.assertEqual(
            """\
import sys
sys.maxsize
""",
            autopep8.fix_2to3("""\
import sys
sys.maxint
"""))

    def test_fix_2to3_subset(self):
        line = 'type(res) == type(42)\n'
        fixed = 'isinstance(res, type(42))\n'

        self.assertEqual(fixed, autopep8.fix_2to3(line))
        self.assertEqual(fixed, autopep8.fix_2to3(line, select=['E721']))
        self.assertEqual(fixed, autopep8.fix_2to3(line, select=['E7']))

        self.assertEqual(line, autopep8.fix_2to3(line, select=['W']))
        self.assertEqual(line, autopep8.fix_2to3(line, select=['E999']))
        self.assertEqual(line, autopep8.fix_2to3(line, ignore=['E721']))

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

    def test_find_files(self):
        temp_directory = tempfile.mkdtemp()
        try:
            target = os.path.join(temp_directory, 'dir')
            os.mkdir(target)
            with open(os.path.join(target, 'a.py'), 'w'):
                pass

            exclude = os.path.join(target, 'ex')
            os.mkdir(exclude)
            with open(os.path.join(exclude, 'b.py'), 'w'):
                pass

            sub = os.path.join(exclude, 'sub')
            os.mkdir(sub)
            with open(os.path.join(sub, 'c.py'), 'w'):
                pass

            # FIXME: Avoid changing directory. This may interfere with parallel
            # test runs.
            cwd = os.getcwd()
            os.chdir(temp_directory)
            try:
                files = list(autopep8.find_files(
                    ['dir'], True, [os.path.join('dir', 'ex')]))
            finally:
                os.chdir(cwd)

            file_names = [os.path.basename(f) for f in files]
            self.assertIn('a.py', file_names)
            self.assertNotIn('b.py', file_names)
            self.assertNotIn('c.py', file_names)
        finally:
            shutil.rmtree(temp_directory)

    def test_line_shortening_rank(self):
        self.assertGreater(
            autopep8.line_shortening_rank('(1\n+1)\n',
                                          indent_word='    ',
                                          max_line_length=79),
            autopep8.line_shortening_rank('(1+\n1)\n',
                                          indent_word='    ',
                                          max_line_length=79))

        self.assertGreaterEqual(
            autopep8.line_shortening_rank('(1+\n1)\n',
                                          indent_word='    ',
                                          max_line_length=79),
            autopep8.line_shortening_rank('(1+1)\n',
                                          indent_word='    ',
                                          max_line_length=79))

        # Do not crash.
        autopep8.line_shortening_rank('\n',
                                      indent_word='    ',
                                      max_line_length=79)

        self.assertGreater(
            autopep8.line_shortening_rank('[foo(\nx) for x in y]\n',
                                          indent_word='    ',
                                          max_line_length=79),
            autopep8.line_shortening_rank('[foo(x)\nfor x in y]\n',
                                          indent_word='    ',
                                          max_line_length=79))

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
        reindenter = autopep8.Reindenter('if True:\n  pass\n')

        self.assertEqual('if True:\n    pass\n',
                         reindenter.run())

    def test_reindenter_with_non_standard_indent_size(self):
        reindenter = autopep8.Reindenter('if True:\n  pass\n')

        self.assertEqual('if True:\n   pass\n',
                         reindenter.run(3))

    def test_reindenter_with_good_input(self):
        lines = 'if True:\n    pass\n'

        reindenter = autopep8.Reindenter(lines)

        self.assertEqual(lines,
                         reindenter.run())

    def test_reindenter_should_leave_stray_comment_alone(self):
        lines = '  #\nif True:\n  pass\n'

        reindenter = autopep8.Reindenter(lines)

        self.assertEqual('  #\nif True:\n    pass\n',
                         reindenter.run())

    @unittest.skipIf('AUTOPEP8_COVERAGE' in os.environ, 'exists form-feed')
    def test_reindenter_not_affect_with_formfeed(self):
        lines = """print('hello')

print('python')
"""
        reindenter = autopep8.Reindenter(lines)

        self.assertEqual(lines,
                         reindenter.run())

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

    def test_standard_deviation(self):
        self.assertAlmostEqual(
            2, autopep8.standard_deviation([2, 4, 4, 4, 5, 5, 7, 9]))

        self.assertAlmostEqual(0, autopep8.standard_deviation([]))
        self.assertAlmostEqual(0, autopep8.standard_deviation([1]))
        self.assertAlmostEqual(.5, autopep8.standard_deviation([1, 2]))

    def test_priority_key_with_non_existent_key(self):
        pep8_result = {'id': 'foobar'}
        self.assertGreater(autopep8._priority_key(pep8_result), 1)

    def test_decode_filename(self):
        self.assertEqual('foo.py', autopep8.decode_filename(b'foo.py'))

    def test_almost_equal(self):
        self.assertTrue(autopep8.code_almost_equal(
            """\
[1, 2, 3
    4, 5]
""",
            """\
[1, 2, 3
4, 5]
"""))

        self.assertTrue(autopep8.code_almost_equal(
            """\
[1,2,3
    4,5]
""",
            """\
[1, 2, 3
4,5]
"""))

        self.assertFalse(autopep8.code_almost_equal(
            """\
[1, 2, 3
    4, 5]
""",
            """\
[1, 2, 3, 4,
    5]
"""))

    def test_token_offsets(self):
        text = """\
1
"""
        string_io = io.StringIO(text)
        self.assertEqual(
            [(tokenize.NUMBER, '1', 0, 1),
             (tokenize.NEWLINE, '\n', 1, 2),
             (tokenize.ENDMARKER, '', 2, 2)],
            list(autopep8.token_offsets(
                tokenize.generate_tokens(string_io.readline))))

    def test_token_offsets_with_multiline(self):
        text = """\
x = '''
1
2
'''
"""
        string_io = io.StringIO(text)
        self.assertEqual(
            [(tokenize.NAME, 'x', 0, 1),
             (tokenize.OP, '=', 2, 3),
             (tokenize.STRING, "'''\n1\n2\n'''", 4, 15),
             (tokenize.NEWLINE, '\n', 15, 16),
             (tokenize.ENDMARKER, '', 16, 16)],
            list(autopep8.token_offsets(
                tokenize.generate_tokens(string_io.readline))))

    def test_token_offsets_with_escaped_newline(self):
        text = """\
True or \\
    False
"""
        string_io = io.StringIO(text)
        self.assertEqual(
            [(tokenize.NAME, 'True', 0, 4),
             (tokenize.NAME, 'or', 5, 7),
             (tokenize.NAME, 'False', 11, 16),
             (tokenize.NEWLINE, '\n', 16, 17),
             (tokenize.ENDMARKER, '', 17, 17)],
            list(autopep8.token_offsets(
                tokenize.generate_tokens(string_io.readline))))

    def test_shorten_line_candidates_are_valid(self):
        for text in [
            """\
[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx, y] = [1, 2]
""",
            """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx, y = [1, 2]
""",
            """\
lambda xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx: line_shortening_rank(x,
                                           indent_word,
                                           max_line_length)
""",
        ]:
            indent = autopep8._get_indentation(text)
            source = text[len(indent):]
            assert source.lstrip() == source
            tokens = list(autopep8.generate_tokens(source))

            for candidate in autopep8.shorten_line(
                    tokens, source, indent,
                    indent_word='    ',
                    max_line_length=79,
                    aggressive=10,
                    experimental=True,
                    previous_line=''):

                self.assertEqual(
                    re.sub(r'\s', '', text),
                    re.sub(r'\s', '', candidate))


class SystemTests(unittest.TestCase):

    maxDiff = None

    def test_e101(self):
        line = """\
while True:
    if True:
    \t1
"""
        fixed = """\
while True:
    if True:
        1
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_with_indent_size_0(self):
        line = """\
while True:
    if True:
    \t1
"""
        with autopep8_context(line, options=['--indent-size=0']) as result:
            self.assertEqual(line, result)

    def test_e101_with_indent_size_1(self):
        line = """\
while True:
    if True:
    \t1
"""
        fixed = """\
while True:
 if True:
  1
"""
        with autopep8_context(line, options=['--indent-size=1']) as result:
            self.assertEqual(fixed, result)

    def test_e101_with_indent_size_2(self):
        line = """\
while True:
    if True:
    \t1
"""
        fixed = """\
while True:
  if True:
    1
"""
        with autopep8_context(line, options=['--indent-size=2']) as result:
            self.assertEqual(fixed, result)

    def test_e101_with_indent_size_3(self):
        line = """\
while True:
    if True:
    \t1
"""
        fixed = """\
while True:
   if True:
      1
"""
        with autopep8_context(line, options=['--indent-size=3']) as result:
            self.assertEqual(fixed, result)

    def test_e101_should_not_expand_non_indentation_tabs(self):
        line = """\
while True:
    if True:
    \t1 == '\t'
"""
        fixed = """\
while True:
    if True:
        1 == '\t'
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_should_ignore_multiline_strings(self):
        line = """\
x = '''
while True:
    if True:
    \t1
'''
"""
        fixed = """\
x = '''
while True:
    if True:
    \t1
'''
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_should_fix_docstrings(self):
        line = """\
class Bar(object):

    def foo():
        '''
\tdocstring
        '''
"""
        fixed = """\
class Bar(object):

    def foo():
        '''
        docstring
        '''
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_when_pep8_mistakes_first_tab_in_string(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multiline string.
        line = """\
x = '''
\tHello.
'''
if True:
    123
"""
        fixed = """\
x = '''
\tHello.
'''
if True:
    123
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_should_ignore_multiline_strings_complex(self):
        line = """\
print(3 <> 4, '''
while True:
    if True:
    \t1
\t''', 4 <> 5)
"""
        fixed = """\
print(3 != 4, '''
while True:
    if True:
    \t1
\t''', 4 != 5)
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e101_with_comments(self):
        line = """\
while True:  # My inline comment
             # with a hanging
             # comment.
    # Hello
    if True:
    \t# My comment
    \t1
    \t# My other comment
"""
        fixed = """\
while True:  # My inline comment
             # with a hanging
             # comment.
    # Hello
    if True:
        # My comment
        1
        # My other comment
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e101_skip_if_bad_indentation(self):
        line = """\
try:
\t    pass
    except:
        pass
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e101_skip_innocuous(self):
        # pep8 will complain about this even if the tab indentation found
        # elsewhere is in a multiline string. If we don't filter the innocuous
        # report properly, the below command will take a long time.
        p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                  ['-vvv', '--select=E101', '--diff',
                   '--global-config={}'.format(os.devnull),
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
        line = """\
while True:
      if True:
            1
      elif True:
            2
"""
        fixed = """\
while True:
    if True:
        1
    elif True:
        2
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e111_multiple_levels(self):
        line = """\
while True:
    if True:
       1

# My comment
print('abc')

"""
        fixed = """\
while True:
    if True:
        1

# My comment
print('abc')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e111_with_dedent(self):
        line = """\
def foo():
    if True:
         2
    1
"""
        fixed = """\
def foo():
    if True:
        2
    1
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e111_with_other_errors(self):
        line = """\
def foo():
    if True:
         (2 , 1)
    1
    if True:
           print('hello')\t
    2
"""
        fixed = """\
def foo():
    if True:
        (2, 1)
    1
    if True:
        print('hello')
    2
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e111_should_not_modify_string_contents(self):
        line = """\
if True:
 x = '''
 1
 '''
"""
        fixed = """\
if True:
    x = '''
 1
 '''
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e112_should_leave_bad_syntax_alone(self):
        line = """\
if True:
pass
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e113(self):
        line = """\
a = 1
    b = 2
"""
        fixed = """\
a = 1
b = 2
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e113_bad_syntax(self):
        line = """\
    pass
"""
        fixed = """\
pass
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e114(self):
        line = """\
   # a = 1
"""
        fixed = """\
# a = 1
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e115(self):
        line = """\
if True:
# A comment.
    pass
"""
        fixed = """\
if True:
    # A comment.
    pass
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e116(self):
        line = """\
a = 1
    # b = 2
"""
        fixed = """\
a = 1
# b = 2
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e12_reindent(self):
        line = """\
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
        fixed = """\
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
        line = """\

sql = 'update %s set %s %s' % (from_table,
                               ','.join(['%s=%s' % (col, col) for col in cols]),
        where_clause)
"""
        fixed = """\

sql = 'update %s set %s %s' % (from_table,
                               ','.join(['%s=%s' % (col, col)
                                         for col in cols]),
                               where_clause)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e12_tricky(self):
        line = """\
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
        fixed = """\
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
        line = """\
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
        fixed = """\
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

    def test_e121_with_multiline_string(self):
        line = """\
testing = \\
'''inputs: d c b a
'''
"""
        fixed = """\
testing = \\
    '''inputs: d c b a
'''
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
        line = """\
if True:
    foo = (
        )
"""
        fixed = """\
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

    def test_e129(self):
        line = """\
if (a and
    b in [
        'foo',
    ] or
    c):
    pass
"""
        fixed = """\
if (a and
    b in [
        'foo',
    ] or
        c):
    pass
"""
        with autopep8_context(line, options=['--select=E129']) as result:
            self.assertEqual(fixed, result)

    def test_e125_with_multiline_string(self):
        line = """\
for foo in '''
    abc
    123
    '''.strip().split():
    print(foo)
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(line, result)

    def test_e125_with_multiline_string_okay(self):
        line = """\
def bar(
    a='''a'''):
    print(foo)
"""
        fixed = """\
def bar(
        a='''a'''):
    print(foo)
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e126(self):
        line = """\
if True:
    posted = models.DateField(
            default=datetime.date.today,
            help_text="help"
    )
"""
        fixed = """\
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
        line = """\
if True:
    if True:
        chksum = (sum([int(value[i]) for i in xrange(0, 9, 2)]) * 7 -
                          sum([int(value[i]) for i in xrange(1, 9, 2)])) % 10
"""
        fixed = """\
if True:
    if True:
        chksum = (sum([int(value[i]) for i in xrange(0, 9, 2)]) * 7 -
                  sum([int(value[i]) for i in xrange(1, 9, 2)])) % 10
"""
        with autopep8_context(line, options=['--select=E12']) as result:
            self.assertEqual(fixed, result)

    def test_e127_align_visual_indent(self):
        line = """\
def draw(self):
    color = [([0.2, 0.1, 0.3], [0.2, 0.1, 0.3], [0.2, 0.1, 0.3]),
               ([0.9, 0.3, 0.5], [0.5, 1.0, 0.5], [0.3, 0.3, 0.9])  ][self._p._colored ]
    self.draw_background(color)
"""
        fixed = """\
def draw(self):
    color = [([0.2, 0.1, 0.3], [0.2, 0.1, 0.3], [0.2, 0.1, 0.3]),
             ([0.9, 0.3, 0.5], [0.5, 1.0, 0.5], [0.3, 0.3, 0.9])][self._p._colored]
    self.draw_background(color)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e127_align_visual_indent_okay(self):
        """This is for code coverage."""
        line = """\
want = (have + _leading_space_count(
        after[jline - 1]) -
        _leading_space_count(lines[jline]))
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e127_with_backslash(self):
        line = r"""
if True:
    if True:
        self.date = meta.session.query(schedule.Appointment)\
            .filter(schedule.Appointment.id ==
                                      appointment_id).one().agenda.endtime
"""
        fixed = r"""
if True:
    if True:
        self.date = meta.session.query(schedule.Appointment)\
            .filter(schedule.Appointment.id ==
                    appointment_id).one().agenda.endtime
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e127_with_bracket_then_parenthesis(self):
        line = r"""
if True:
    foo = [food(1)
               for bar in bars]
"""
        fixed = r"""
if True:
    foo = [food(1)
           for bar in bars]
"""
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

    def test_e133(self):
        line = """\
if True:
    e = [
        1, 2
    ]
"""
        fixed = """\
if True:
    e = [
        1, 2
        ]
"""
        with autopep8_context(line, options=['--hang-closing']) as result:
            self.assertEqual(fixed, result)

    def test_e133_not_effected(self):
        line = """\
if True:
    e = [
        1, 2
        ]
"""
        with autopep8_context(line, options=['--hang-closing']) as result:
            self.assertEqual(line, result)

    def test_w191(self):
        line = """\
while True:
\tif True:
\t\t1
"""
        fixed = """\
while True:
    if True:
        1
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e131_with_select_option(self):
        line = 'd = f(\n    a="hello"\n        "world",\n    b=1)\n'
        fixed = 'd = f(\n    a="hello"\n    "world",\n    b=1)\n'
        with autopep8_context(line, options=['--select=E131']) as result:
            self.assertEqual(fixed, result)

    def test_e131_invalid_indent_with_select_option(self):
        line = 'd = (\n    "hello"\n  "world")\n'
        fixed = 'd = (\n    "hello"\n    "world")\n'
        with autopep8_context(line, options=['--select=E131']) as result:
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

    def test_e202_multiline(self):
        line = """\

('''
a
b
c
''' )
"""
        fixed = """\

('''
a
b
c
''')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e202_skip_multiline_with_escaped_newline(self):
        line = r"""

('c\
' )
"""
        fixed = r"""

('c\
')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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

    def test_e221_do_not_skip_multiline(self):
        line = '''\
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
'''
        fixed = '''\
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
    """ % {
    }
'''
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e222(self):
        line = 'a = 1 +  1\n'
        fixed = 'a = 1 + 1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e222_with_multiline(self):
        line = 'a =   \"\"\"bar\nbaz\"\"\"\n'
        fixed = 'a = \"\"\"bar\nbaz\"\"\"\n'
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
        line = """\
class Foo():

\tdef __init__(self):
\t\tx= 1\t+ 3
"""
        fixed = """\
class Foo():

\tdef __init__(self):
\t\tx = 1 + 3
"""
        with autopep8_context(line, options=['--ignore=E1,W191']) as result:
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
        line = """\
class Foo():

\tdef __init__(self):
\t\tx= \t3
"""
        fixed = """\
class Foo():

\tdef __init__(self):
\t\tx = 3
"""
        with autopep8_context(line, options=['--ignore=E1,W191']) as result:
            self.assertEqual(fixed, result)

    def test_e225(self):
        line = '1+1\n2 +2\n3+ 3\n'
        fixed = '1 + 1\n2 + 2\n3 + 3\n'
        with autopep8_context(line, options=['--select=E,W']) as result:
            self.assertEqual(fixed, result)

    def test_e225_with_indentation_fix(self):
        line = """\
class Foo(object):

  def bar(self):
    return self.elephant!='test'
"""
        fixed = """\
class Foo(object):

    def bar(self):
        return self.elephant != 'test'
"""
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

    def test_e252(self):
        line = 'def a(arg1: int=1, arg2: int =1, arg3: int= 1):\n    print arg\n'
        fixed = 'def a(arg1: int = 1, arg2: int = 1, arg3: int = 1):\n    print arg\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e252_with_argument_on_next_line(self):
        line = 'def a(arg: int\n=1):\n    print arg\n'
        fixed = 'def a(arg: int\n= 1):\n    print arg\n'
        with autopep8_context(line, options=['--select=E252']) as result:
            self.assertEqual(fixed, result)

    def test_e252_with_escaped_newline(self):
        line = 'def a(arg: int\\\n=1):\n    print arg\n'
        fixed = 'def a(arg: int\\\n= 1):\n    print arg\n'
        with autopep8_context(line, options=['--select=E252']) as result:
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

    def test_e271_with_multiline(self):
        line = 'if True and  False \\\n        True:\n    pass\n'
        fixed = 'if True and False \\\n        True:\n    pass\n'
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

    def test_e306(self):
        line = """
def test_descriptors(self):

        class descriptor(object):
            def __init__(self, fn):
                self.fn = fn
            def __get__(self, obj, owner):
                if obj is not None:
                    return self.fn(obj, obj)
                else:
                    return self
            def method(self):
                return 'method'
"""
        fixed = """
def test_descriptors(self):

    class descriptor(object):
        def __init__(self, fn):
            self.fn = fn

        def __get__(self, obj, owner):
            if obj is not None:
                return self.fn(obj, obj)
            else:
                return self

        def method(self):
            return 'method'
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e301(self):
        line = 'class k:\n    s = 0\n    def f():\n        print 1\n'
        fixed = 'class k:\n    s = 0\n\n    def f():\n        print 1\n'
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

    def test_not_e301_extended_with_comment(self):
        line = '''\
class Foo(object):

    """Test."""

    # A comment.
    def foo(self):
        pass
'''
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e302(self):
        line = 'def f():\n    print 1\n\ndef ff():\n    print 2\n'
        fixed = 'def f():\n    print 1\n\n\ndef ff():\n    print 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e302_bug(self):
        """Avoid creating bad syntax."""
        line = r"""def repeatable_expr():      return [bracketed_choice, simple_match, rule_ref],\
                                    Optional(repeat_operator)
# def match():                return [simple_match , mixin_rule_match] TODO
def simple_match():         return [str_match, re_match]
"""
        self.assertTrue(autopep8.check_syntax(line))
        with autopep8_context(line) as result:
            self.assertTrue(autopep8.check_syntax(result))

    def test_e303(self):
        line = '\n\n\n# alpha\n\n1\n'
        fixed = '\n\n# alpha\n\n1\n'
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

    def test_e305(self):
        line = 'def a():\n    pass\na()\n'
        fixed = 'def a():\n    pass\n\n\na()\n'
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
        line = """\

print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\

print(111, 111, 111, 111, 222, 222, 222, 222,
      222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_dictionary(self):
        line = """\
myDict = { 'kg': 1, 'tonnes': tonne, 't/y': tonne / year, 'Mt/y': 1e6 * tonne / year}
"""
        fixed = """\
myDict = {
    'kg': 1,
    'tonnes': tonne,
    't/y': tonne / year,
    'Mt/y': 1e6 * tonne / year}
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_in(self):
        line = """\
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            if True:
                                if k_left in ('any', k_curr) and k_right in ('any', k_curr):
                                    pass
"""
        fixed = """\
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            if True:
                                if k_left in ('any', k_curr) and k_right in ('any', k_curr):
                                    pass
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_commas_and_colons(self):
        line = """\
foobar = {'aaaaaaaaaaaa': 'bbbbbbbbbbbbbbbb', 'dddddd': 'eeeeeeeeeeeeeeee', 'ffffffffffff': 'gggggggg'}
"""
        fixed = """\
foobar = {'aaaaaaaaaaaa': 'bbbbbbbbbbbbbbbb',
          'dddddd': 'eeeeeeeeeeeeeeee', 'ffffffffffff': 'gggggggg'}
"""
        with autopep8_context(line) as result:
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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_inline_comments_should_skip_multiline(self):
        line = """\
'''This should be left alone. -----------------------------------------------------

'''  # foo

'''This should be left alone. -----------------------------------------------------

''' \\
# foo

'''This should be left alone. -----------------------------------------------------

''' \\
\\
# foo
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(line, result)

    def test_e501_with_inline_comments_should_skip_keywords(self):
        line = """\
'                                                          '  # noqa Long inline comments should be moved above.
if True:
    '                                                          '  # pylint: disable-msgs=E0001
    '                                                          '  # pragma: no cover
    '                                                          '  # pragma: no cover
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_e501_with_inline_comments_should_skip_keywords_without_aggressive(
            self):
        line = """\
'                                                          '  # noqa Long inline comments should be moved above.
if True:
    '                                                          '  # pylint: disable-msgs=E0001
    '                                                          '  # pragma: no cover
    '                                                          '  # pragma: no cover
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

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
    reconstructed = iradon(radon(image), filter="ramp",
                           interpolation="nearest")
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

    def test_e501_with_lambda(self):
        line = """\
self.mock_group.modify_state.side_effect = lambda *_: defer.fail(NoSuchScalingGroupError(1, 2))
"""
        fixed = """\
self.mock_group.modify_state.side_effect = lambda *_: defer.fail(
    NoSuchScalingGroupError(1, 2))
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_shorten_with_backslash(self):
        line = """\
class Bar(object):

    def bar(self, position):
        if 0 <= position <= self._blocks[-1].position + len(self._blocks[-1].text):
            pass
"""
        fixed = """\
class Bar(object):

    def bar(self, position):
        if 0 <= position <= self._blocks[-1].position + \\
                len(self._blocks[-1].text):
            pass
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

        with autopep8_context(line,
                              options=['--max-line-length=40']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_indent(self):
        line = """\

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_alone_with_indentation(self):
        line = """\

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\

if True:
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(fixed, result)

    def test_e501_alone_with_tuple(self):
        line = """\

fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime', 'FLOAT')
                                                           ]
"""
        fixed = """\

fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime',
                                                             'FLOAT')
                                                           ]
"""
        with autopep8_context(line, options=['--select=E501']) as result:
            self.assertEqual(fixed, result)

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
        line = """\
def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        fixed = r"""def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + \
        222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_more_complicated(self):
        line = """\

blahblah = os.environ.get('blahblah') or os.environ.get('blahblahblah') or os.environ.get('blahblahblahblah')
"""
        fixed = """\

blahblah = os.environ.get('blahblah') or os.environ.get(
    'blahblahblah') or os.environ.get('blahblahblahblah')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_skip_even_more_complicated(self):
        line = """\

if True:
    if True:
        if True:
            blah = blah.blah_blah_blah_bla_bl(blahb.blah, blah.blah,
                                              blah=blah.label, blah_blah=blah_blah,
                                              blah_blah2=blah_blah)
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

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

    def test_e501_with_logical_fix(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc,
    dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_logical_fix_and_physical_fix(self):
        line = """\
# ------------------------------------ ------------------------------------------
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
# ------------------------------------ -----------------------------------
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc,
    dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_logical_fix_and_adjacent_strings(self):
        line = """\
print('a-----------------------' 'b-----------------------' 'c-----------------------'
      'd-----------------------''e'"f"r"g")
"""
        fixed = """\
print(
    'a-----------------------'
    'b-----------------------'
    'c-----------------------'
    'd-----------------------'
    'e'
    "f"
    r"g")
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_multiple_lines(self):
        line = """\

foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,
                           111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333)
"""
        fixed = """\

foo_bar_zap_bing_bang_boom(
    111,
    111,
    111,
    111,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    333,
    333,
    111,
    111,
    111,
    111,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    222,
    333,
    333)
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_multiple_lines_and_quotes(self):
        line = """\

if True:
    xxxxxxxxxxx = xxxxxxxxxxxxxxxxx(xxxxxxxxxxx, xxxxxxxxxxxxxxxx={'xxxxxxxxxxxx': 'xxxxx',
                                                                   'xxxxxxxxxxx': xx,
                                                                   'xxxxxxxx': False,
                                                                   })
"""
        fixed = """\

if True:
    xxxxxxxxxxx = xxxxxxxxxxxxxxxxx(
        xxxxxxxxxxx,
        xxxxxxxxxxxxxxxx={
            'xxxxxxxxxxxx': 'xxxxx',
            'xxxxxxxxxxx': xx,
            'xxxxxxxx': False,
        })
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_do_not_break_on_keyword(self):
        # We don't want to put a newline after equals for keywords as this
        # violates PEP 8.
        line = """\

if True:
    long_variable_name = tempfile.mkstemp(prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        fixed = """\

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
        line = """\

def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction( [MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine() )
"""
        fixed = """\

def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction([MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(
                ), MODIFY70.getCharPositionInLine())
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_should_not_break_on_dot(self):
        line = """\
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx('xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
"""

        fixed = """\
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx(
            'xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
"""

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_comment(self):
        line = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        pass

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        fixed = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap to be within 72 characters.
                        pass

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_comment_should_not_modify_docstring(self):
        line = '''\
def foo():
    """
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
    """
'''
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    def test_e501_should_only_modify_last_comment(self):
        line = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
"""
        fixed = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I
                        # will wrap it using textwrap to be within 72
                        # characters.
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_should_not_interfere_with_non_comment(self):
        line = '''

"""
# not actually a comment %d. 12345678901234567890, 12345678901234567890, 12345678901234567890.
""" % (0,)
'''
        with autopep8_context(line, options=['--aggressive']) as result:
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
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_function_should_not_break_on_colon(self):
        line = r"""
class Useless(object):

    def _table_field_is_plain_widget(self, widget):
        if widget.__class__ == Widget or\
                (widget.__class__ == WidgetMeta and Widget in widget.__bases__):
            return True

        return False
"""

        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_should_break_before_tuple_start(self):
        line = """\
xxxxxxxxxxxxx(aaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbb, cccccccccc, (dddddddddddddddddddddd, eeeeeeeeeeee, fffffffffff, gggggggggg))
"""
        fixed = """\
xxxxxxxxxxxxx(aaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbb, cccccccccc,
              (dddddddddddddddddddddd, eeeeeeeeeeee, fffffffffff, gggggggggg))
"""

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

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
        'Meta': {
            'object_name': 'Group'},
        'permissions': (
            'django.db.models.fields.related.ManyToManyField',
            [],
            {
                'to': "orm['auth.Permission']",
                'symmetrical': 'False',
                'blank': 'True'})},
    'auth.permission': {
        'Meta': {
            'ordering': "('content_type__app_label', 'content_type__model', 'codename')",
            'unique_together': "(('content_type', 'codename'),)",
            'object_name': 'Permission'},
        'name': (
            'django.db.models.fields.CharField',
            [],
            {
                'max_length': '50'})},
}
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_multiple_logical_lines(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc,
    dddddddddddddddddddddddd)
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc,
    dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_multiple_logical_lines_with_math(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx([-1 + 5 / 10,
                                                                            100,
                                                                            -3 - 4])
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    [-1 + 5 / 10, 100, -3 - 4])
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_import(self):
        line = """\
from . import (xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
               yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy)
"""
        fixed = """\
from . import (
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy)
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_massive_number_of_logical_lines(self):
        """We do not care about results here.

        We just want to know that it doesn't take a ridiculous amount of
        time. Caching is currently required to avoid repeately trying
        the same line.

        """
        line = """\
# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

from provider.compat import user_model_label


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Adding model 'Client'
        db.create_table('oauth2_client', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm[user_model_label])),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=200)),
            ('redirect_uri', self.gf('django.db.models.fields.URLField')(max_length=200)),
            ('client_id', self.gf('django.db.models.fields.CharField')(default='37b581bdc702c732aa65', max_length=255)),
            ('client_secret', self.gf('django.db.models.fields.CharField')(default='5cf90561f7566aa81457f8a32187dcb8147c7b73', max_length=255)),
            ('client_type', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('oauth2', ['Client'])

        # Adding model 'Grant'
        db.create_table('oauth2_grant', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm[user_model_label])),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['oauth2.Client'])),
            ('code', self.gf('django.db.models.fields.CharField')(default='f0cda1a5f4ae915431ff93f477c012b38e2429c4', max_length=255)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2012, 2, 8, 10, 43, 45, 620301))),
            ('redirect_uri', self.gf('django.db.models.fields.CharField')(max_length=255, blank=True)),
            ('scope', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('oauth2', ['Grant'])

        # Adding model 'AccessToken'
        db.create_table('oauth2_accesstoken', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm[user_model_label])),
            ('token', self.gf('django.db.models.fields.CharField')(default='b10b8f721e95117cb13c', max_length=255)),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['oauth2.Client'])),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(2013, 2, 7, 10, 33, 45, 618854))),
            ('scope', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('oauth2', ['AccessToken'])

        # Adding model 'RefreshToken'
        db.create_table('oauth2_refreshtoken', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm[user_model_label])),
            ('token', self.gf('django.db.models.fields.CharField')(default='84035a870dab7c820c2c501fb0b10f86fdf7a3fe', max_length=255)),
            ('access_token', self.gf('django.db.models.fields.related.OneToOneField')(related_name='refresh_token', unique=True, to=orm['oauth2.AccessToken'])),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['oauth2.Client'])),
            ('expired', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('oauth2', ['RefreshToken'])


    def backwards(self, orm):

        # Deleting model 'Client'
        db.delete_table('oauth2_client')

        # Deleting model 'Grant'
        db.delete_table('oauth2_grant')

        # Deleting model 'AccessToken'
        db.delete_table('oauth2_accesstoken')

        # Deleting model 'RefreshToken'
        db.delete_table('oauth2_refreshtoken')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        user_model_label: {
            'Meta': {'object_name': user_model_label.split('.')[-1]},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'oauth2.accesstoken': {
            'Meta': {'object_name': 'AccessToken'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['oauth2.Client']"}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2013, 2, 7, 10, 33, 45, 624553)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'scope': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'token': ('django.db.models.fields.CharField', [], {'default': "'d5c1f65020ebdc89f20c'", 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['%s']" % user_model_label})
        },
        'oauth2.client': {
            'Meta': {'object_name': 'Client'},
            'client_id': ('django.db.models.fields.CharField', [], {'default': "'306fb26cbcc87dd33cdb'", 'max_length': '255'}),
            'client_secret': ('django.db.models.fields.CharField', [], {'default': "'7e5785add4898448d53767f15373636b918cf0e3'", 'max_length': '255'}),
            'client_type': ('django.db.models.fields.IntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'redirect_uri': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['%s']" % user_model_label})
        },
        'oauth2.grant': {
            'Meta': {'object_name': 'Grant'},
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['oauth2.Client']"}),
            'code': ('django.db.models.fields.CharField', [], {'default': "'310b2c63e27306ecf5307569dd62340cc4994b73'", 'max_length': '255'}),
            'expires': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2012, 2, 8, 10, 43, 45, 625956)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'redirect_uri': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'scope': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['%s']" % user_model_label})
        },
        'oauth2.refreshtoken': {
            'Meta': {'object_name': 'RefreshToken'},
            'access_token': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'refresh_token'", 'unique': 'True', 'to': "orm['oauth2.AccessToken']"}),
            'client': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['oauth2.Client']"}),
            'expired': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'default': "'ef0ab76037f17769ab2975a816e8f41a1c11d25e'", 'max_length': '255'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['%s']" % user_model_label})
        }
    }

    complete_apps = ['oauth2']
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(''.join(line.split()),
                             ''.join(result.split()))

    def test_e501_shorten_comment_with_aggressive(self):
        line = """\
# --------- ----------------------------------------------------------------------
"""
        fixed = """\
# --------- --------------------------------------------------------------
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_shorten_comment_without_aggressive(self):
        """Do nothing without aggressive."""
        line = """\
def foo():
    pass
# --------- ----------------------------------------------------------------------
"""
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_e501_with_aggressive_and_escaped_newline(self):
        line = """\
if True or \\
    False:  # test test test test test test test test test test test test test test
    pass
"""
        fixed = """\
if True or \\
        False:  # test test test test test test test test test test test test test test
    pass
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_multiline_string(self):
        line = """\
print('---------------------------------------------------------------------',
      ('================================================', '====================='),
      '''--------------------------------------------------------------------------------
      ''')
"""
        fixed = """\
print(
    '---------------------------------------------------------------------',
    ('================================================',
     '====================='),
    '''--------------------------------------------------------------------------------
      ''')
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_multiline_string_with_addition(self):
        line = '''\
def f():
    email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>"""
'''
        fixed = '''\
def f():
    email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>""" + despot["Nicholas"] + """<br>
<b>Minion: </b>""" + serf["Dmitri"] + """<br>
<b>Residence: </b>""" + palace["Winter"] + """<br>
</body>
</html>"""
'''
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_multiline_string_in_parens(self):
        line = '''\
def f():
    email_text += ("""<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>""")
'''
        fixed = '''\
def f():
    email_text += (
        """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>""" +
        despot["Nicholas"] +
        """<br>
<b>Minion: </b>""" +
        serf["Dmitri"] +
        """<br>
<b>Residence: </b>""" +
        palace["Winter"] +
        """<br>
</body>
</html>""")
'''
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_indentation(self):
        line = """\
if True:
    # comment here
    print(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
          bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,cccccccccccccccccccccccccccccccccccccccccc)
"""
        fixed = """\
if True:
    # comment here
    print(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
          bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,
          cccccccccccccccccccccccccccccccccccccccccc)
"""
        with autopep8_context(line, options=['-aa']) as result:
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
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_aggressive_and_carriage_returns_only(self):
        """Make sure _find_logical() does not crash."""
        line = 'if True:\r    from aaaaaaaaaaaaaaaa import bbbbbbbbbbbbbbbbbbb\r    \r    ccccccccccc = None\r'
        fixed = 'if True:\r    from aaaaaaaaaaaaaaaa import bbbbbbbbbbbbbbbbbbb\r\r    ccccccccccc = None\r'
        with autopep8_context(line, options=['-aa']) as result:
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
def foo(sldfkjlsdfsdf, kksdfsdfsf, sdfsdfsdf, sdfsdfkdk, szdfsdfsdf,
        sdfsdfsdfsdlkfjsdlf, sdfsdfddf, sdfsdfsfd, sdfsdfdsf):
    pass
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_more_aggressive_with_def(self):
        line = """\
def foobar(sldfkjlsdfsdf, kksdfsdfsf,sdfsdfsdf, sdfsdfkdk, szdfsdfsdf, sdfsdfsdfsdlkfjsdlf, sdfsdfddf,sdfsdfsfd, sdfsdfdsf):
    pass
"""
        fixed = """\


def foobar(
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
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_with_tuple(self):
        line = """\
def f():
    man_this_is_a_very_long_function_name(an_extremely_long_variable_name,
                                          ('a string that is long: %s'%'bork'))
"""
        fixed = """\
def f():
    man_this_is_a_very_long_function_name(
        an_extremely_long_variable_name,
        ('a string that is long: %s' % 'bork'))
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_with_tuple_in_list(self):
        line = """\
def f(self):
    self._xxxxxxxx(aaaaaa, bbbbbbbbb, cccccccccccccccccc,
                   [('mmmmmmmmmm', self.yyyyyyyyyy.zzzzzzz/_DDDDD)], eee, 'ff')
"""
        fixed = """\
def f(self):
    self._xxxxxxxx(aaaaaa, bbbbbbbbb, cccccccccccccccccc, [
                   ('mmmmmmmmmm', self.yyyyyyyyyy.zzzzzzz / _DDDDD)], eee, 'ff')
"""

        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_decorator(self):
        line = """\
@foo(('xxxxxxxxxxxxxxxxxxxxxxxxxx', users.xxxxxxxxxxxxxxxxxxxxxxxxxx), ('yyyyyyyyyyyy', users.yyyyyyyyyyyy), ('zzzzzzzzzzzzzz', users.zzzzzzzzzzzzzz))
"""
        fixed = """\
@foo(('xxxxxxxxxxxxxxxxxxxxxxxxxx', users.xxxxxxxxxxxxxxxxxxxxxxxxxx),
     ('yyyyyyyyyyyy', users.yyyyyyyyyyyy), ('zzzzzzzzzzzzzz', users.zzzzzzzzzzzzzz))
"""

        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_long_class_name(self):
        line = """\
class AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB):
    pass
"""
        fixed = """\
class AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(
        BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB):
    pass
"""

        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_long_comment_and_long_line(self):
        line = """\
def foo():
    # This is not a novel to be tossed aside lightly. It should be throw with great force.
    self.xxxxxxxxx(_('yyyyyyyyyyyyy yyyyyyyyyyyy yyyyyyyy yyyyyyyy y'), 'zzzzzzzzzzzzzzzzzzz', bork='urgent')
"""
        fixed = """\
def foo():
    # This is not a novel to be tossed aside lightly. It should be throw with
    # great force.
    self.xxxxxxxxx(
        _('yyyyyyyyyyyyy yyyyyyyyyyyy yyyyyyyy yyyyyyyy y'),
        'zzzzzzzzzzzzzzzzzzz',
        bork='urgent')
"""

        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_aggressive_intermingled_comments(self):
        line = """\
A = [
    # A comment
    ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbbbbbbbb', 'cccccccccccccccccccccc']
]
"""
        fixed = """\
A = [
    # A comment
    ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
     'bbbbbbbbbbbbbbbbbbbbbb',
     'cccccccccccccccccccccc']
]
"""

        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_if_line_over_limit(self):
        line = """\
if not xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    return 1
"""
        fixed = """\
if not xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa,
        bbbbbbbbbbbbbbbb,
        cccccccccccccc,
        dddddddddddddddddddddd):
    return 1
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_for_line_over_limit(self):
        line = """\
for aaaaaaaaa in xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    pass
"""
        fixed = """\
for aaaaaaaaa in xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa,
        bbbbbbbbbbbbbbbb,
        cccccccccccccc,
        dddddddddddddddddddddd):
    pass
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_while_line_over_limit(self):
        line = """\
while xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    pass
"""
        fixed = """\
while xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa,
        bbbbbbbbbbbbbbbb,
        cccccccccccccc,
        dddddddddddddddddddddd):
    pass
"""
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e501_avoid_breaking_at_opening_slice(self):
        """Prevents line break on slice notation, dict access in this example:

        GYakymOSMc=GYakymOSMW(GYakymOSMJ,GYakymOSMA,GYakymOSMr,GYakymOSMw[
                  'abc'],GYakymOSMU,GYakymOSMq,GYakymOSMH,GYakymOSMl,svygreNveyvarf=GYakymOSME)

        """
        line = """\
GYakymOSMc=GYakymOSMW(GYakymOSMJ,GYakymOSMA,GYakymOSMr,GYakymOSMw['abc'],GYakymOSMU,GYakymOSMq,GYakymOSMH,GYakymOSMl,svygreNveyvarf=GYakymOSME)
"""
        fixed = """\
GYakymOSMc = GYakymOSMW(GYakymOSMJ, GYakymOSMA, GYakymOSMr,
                        GYakymOSMw['abc'], GYakymOSMU, GYakymOSMq, GYakymOSMH, GYakymOSMl, svygreNveyvarf=GYakymOSME)
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e501_avoid_breaking_at_multi_level_slice(self):
        """Prevents line break on slice notation, dict access in this example:

        GYakymOSMc=GYakymOSMW(GYakymOSMJ,GYakymOSMA,GYakymOSMr,GYakymOSMw['abc'][
        'def'],GYakymOSMU,GYakymOSMq,GYakymOSMH,GYakymOSMl,svygreNveyvarf=GYakymOSME)

        """
        line = """\
GYakymOSMc=GYakymOSMW(GYakymOSMJ,GYakymOSMA,GYakymOSMr,GYakymOSMw['abc']['def'],GYakymOSMU,GYakymOSMq,GYakymOSMH,GYakymOSMl,svygreNveyvarf=GYakymOSME)
"""
        fixed = """\
GYakymOSMc = GYakymOSMW(GYakymOSMJ, GYakymOSMA, GYakymOSMr,
                        GYakymOSMw['abc']['def'], GYakymOSMU, GYakymOSMq, GYakymOSMH, GYakymOSMl, svygreNveyvarf=GYakymOSME)
"""
        with autopep8_context(line) as result:
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

    def test_e702_after_colon_should_be_untouched(self):
        # https://docs.python.org/2/reference/compound_stmts.html
        line = 'def foo(): print(1); print(2)\n'
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

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
        line = """\
# -*- coding: utf-8 -*-
# French comment with accent é
# Un commentaire en français avec un accent é

import time

time.strftime('%d-%m-%Y');
"""

        fixed = """\
# -*- coding: utf-8 -*-
# French comment with accent é
# Un commentaire en français avec un accent é

import time

time.strftime('%d-%m-%Y')
"""

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
        line = """\

(
    1,
    2,
    3); 4; 5; 5  # pyflakes
"""
        fixed = """\

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
        line = 'def f():\n    """\n      hello\n   """; 1\n'
        fixed = 'def f():\n    """\n      hello\n   """\n    1\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_semicolon_after_string(self):
        line = """\
raise IOError('abc '
              'def.');
"""
        fixed = """\
raise IOError('abc '
              'def.')
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e702_with_dict_semicolon(self):
        line = """\
MY_CONST = [
    {'A': 1},
    {'B': 2}
];
"""
        fixed = """\
MY_CONST = [
    {'A': 1},
    {'B': 2}
]
"""
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e703_with_inline_comment(self):
        line = 'a = 5;    # inline comment\n'
        fixed = 'a = 5    # inline comment\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e704(self):
        line = 'def f(x): return 2*x\n'
        fixed = 'def f(x):\n    return 2 * x\n'
        with autopep8_context(line, options=['-aaa']) as result:
            self.assertEqual(fixed, result)

    def test_e704_not_work_with_aa_option(self):
        line = 'def f(x): return 2*x\n'
        with autopep8_context(line, options=['-aa', '--select=E704']) as result:
            self.assertEqual(line, result)

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
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_in_conditional_with_multiple_instances(self):
        line = 'if foo == True and bar == True:\npass\n'
        fixed = 'if foo and bar:\npass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_with_false(self):
        line = 'foo != False\n'
        fixed = 'foo\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_with_special_case_equal_not_true(self):
        line = 'if foo != True:\n    pass\n'
        fixed = 'if not foo:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_with_special_case_equal_false(self):
        line = 'if foo == False:\n    pass\n'
        fixed = 'if not foo:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_with_dict_value(self):
        line = 'if d["key"] != True:\n    pass\n'
        fixed = 'if not d["key"]:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E712']) as result:
            self.assertEqual(fixed, result)

    def test_e712_only_if_aggressive_level_2(self):
        line = 'foo == True\n'
        with autopep8_context(line, options=['-a']) as result:
            self.assertEqual(line, result)

    def test_e711_and_e712(self):
        line = 'if (foo == None and bar == True) or (foo != False and bar != None):\npass\n'
        fixed = 'if (foo is None and bar) or (foo and bar is not None):\npass\n'
        with autopep8_context(line, options=['-aa']) as result:
            self.assertEqual(fixed, result)

    def test_e713(self):
        line = 'if not x in y:\n    pass\n'
        fixed = 'if x not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_more(self):
        line = 'if not "." in y:\n    pass\n'
        fixed = 'if "." not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_with_in(self):
        line = 'if not "." in y and "," in y:\n    pass\n'
        fixed = 'if "." not in y and "," in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_with_tuple(self):
        line = """
if not role in ("domaincontroller_master",
                "domaincontroller_backup",
                "domaincontroller_slave",
                "memberserver",
                ):
    pass
"""
        fixed = """
if role not in ("domaincontroller_master",
                "domaincontroller_backup",
                "domaincontroller_slave",
                "memberserver",
                ):
    pass
"""
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_chain(self):
        line = 'if "@" not in x or not "/" in y:\n    pass\n'
        fixed = 'if "@" not in x or "/" not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_chain2(self):
        line = 'if "@" not in x or "[" not in x or not "/" in y:\n    pass\n'
        fixed = 'if "@" not in x or "[" not in x or "/" not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_chain3(self):
        line = 'if not "@" in x or "[" not in x or not "/" in y:\n    pass\n'
        fixed = 'if "@" not in x or "[" not in x or "/" not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e713_chain4(self):
        line = 'if not "." in y and not "," in y:\n    pass\n'
        fixed = 'if "." not in y and "," not in y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E713']) as result:
            self.assertEqual(fixed, result)

    def test_e714(self):
        line = 'if not x is y:\n    pass\n'
        fixed = 'if x is not y:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E714']) as result:
            self.assertEqual(fixed, result)

    def test_e714_with_is(self):
        line = 'if not x is y or x is z:\n    pass\n'
        fixed = 'if x is not y or x is z:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E714']) as result:
            self.assertEqual(fixed, result)

    def test_e714_chain(self):
        line = 'if not x is y or not x is z:\n    pass\n'
        fixed = 'if x is not y or x is not z:\n    pass\n'
        with autopep8_context(line,
                              options=['-aa', '--select=E714']) as result:
            self.assertEqual(fixed, result)

    def test_e713_and_e714(self):
        line = """
if not x is y:
    pass
if not role in ("domaincontroller_master",
                "domaincontroller_backup",
                "domaincontroller_slave",
                "memberserver",
                ):
    pass
"""
        fixed = """
if x is not y:
    pass
if role not in ("domaincontroller_master",
                "domaincontroller_backup",
                "domaincontroller_slave",
                "memberserver",
                ):
    pass
"""
        with autopep8_context(line,
                              options=['-aa', '--select=E713,E714']) as result:
            self.assertEqual(fixed, result)

    def test_e713_with_single_quote(self):
        line = "if not 'DC IP' in info:\n"
        fixed = "if 'DC IP' not in info:\n"
        with autopep8_context(line,
                              options=['-aa', '--select=E713,E714']) as result:
            self.assertEqual(fixed, result)

    def test_e714_with_single_quote(self):
        line = "if not 'DC IP' is info:\n"
        fixed = "if 'DC IP' is not info:\n"
        with autopep8_context(line,
                              options=['-aa', '--select=E713,E714']) as result:
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

    def test_e722(self):
        line = "try:\n    print(a)\nexcept:\n    pass\n"
        fixed = "try:\n    print(a)\nexcept BaseException:\n    pass\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e722_with_if_else_stmt(self):
        line = "try:\n    print(a)\nexcept:\n    if a==b:\n        print(a)\n    else:\n        print(b)\n"
        fixed = "try:\n    print(a)\nexcept BaseException:\n    if a == b:\n        print(a)\n    else:\n        print(b)\n"
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e722_non_aggressive(self):
        line = "try:\n    print(a)\nexcept:\n    pass\n"
        with autopep8_context(line, options=[]) as result:
            self.assertEqual(line, result)

    def test_e731(self):
        line = 'a = lambda x: x * 2\n'
        fixed = 'def a(x): return x * 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e731_no_arg(self):
        line = 'a = lambda: x * 2\n'
        fixed = 'def a(): return x * 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e731_with_tuple_arg(self):
        line = 'a = lambda (x, y), z: x * 2\n'
        fixed = 'def a((x, y), z): return x * 2\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e731_with_args(self):
        line = 'a = lambda x, y: x * 2 + y\n'
        fixed = 'def a(x, y): return x * 2 + y\n'
        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_e731_with_select_option(self):
        line = 'a = lambda x: x * 2\n'
        fixed = 'def a(x): return x * 2\n'
        with autopep8_context(line, options=['--select=E731']) as result:
            self.assertEqual(fixed, result)

    def test_e731_with_default_arguments(self):
        line = 'a = lambda k, d=None: bar.get("%s/%s" % (prefix, k), d)\n'
        fixed = 'def a(k, d=None): return bar.get("%s/%s" % (prefix, k), d)\n'
        with autopep8_context(line, options=['--select=E731']) as result:
            self.assertEqual(fixed, result)

    def test_e901_should_cause_indentation_screw_up(self):
        line = """\
def tmp(g):
    g(4)))

    if not True:
        pass
        pass
"""

        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_should_preserve_vertical_tab(self):
        line = """\
#Memory Bu\vffer Register:
"""
        fixed = """\
# Memory Bu\vffer Register:
"""

        with autopep8_context(line) as result:
            self.assertEqual(fixed, result)

    def test_w191_should_ignore_multiline_strings(self):
        line = """\
print(3 <> 4, '''
while True:
    if True:
    \t1
\t''', 4 <> 5)
if True:
\t123
"""
        fixed = """\
print(3 != 4, '''
while True:
    if True:
    \t1
\t''', 4 != 5)
if True:
    123
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w191_should_ignore_tabs_in_strings(self):
        line = """\
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
"""
        fixed = """\
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
"""
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

    def test_w503(self):
        line = '(width == 0\n + height == 0)\n'
        fixed = '(width == 0 +\n height == 0)\n'
        with autopep8_context(line, options=['-aaa']) as result:
            self.assertEqual(fixed, result)

    def test_w503_skip_default(self):
        line = '(width == 0\n + height == 0)\n'
        with autopep8_context(line) as result:
            self.assertEqual(line, result)

    def test_w503_and_or(self):
        line = '(width == 0\n and height == 0\n or name == "")\n'
        fixed = '(width == 0 and\n height == 0 or\n name == "")\n'
        with autopep8_context(line, options=['-aaa']) as result:
            self.assertEqual(fixed, result)

    def test_w503_with_comment(self):
        line = '(width == 0  # this is comment\n + height == 0)\n'
        fixed = '(width == 0 +  # this is comment\n height == 0)\n'
        with autopep8_context(line, options=['-aaa']) as result:
            self.assertEqual(fixed, result)

    def test_w503_with_comment_double(self):
        line = """\
(
    1111  # C1
    and 22222222  # C2
    and 333333333333  # C3
)
"""
        fixed = """\
(
    1111 and  # C1
    22222222 and  # C2
    333333333333  # C3
)
"""
        with autopep8_context(line, options=['-aaa']) as result:
            self.assertEqual(fixed, result)

    def test_w503_over_5lines(self):
        line = """\
X = (
    1  # 1
    + 2  # 2
    + 3  # 3
    + 4  # 4
    + 5  # 5
    + 6  # 6
    + 7  # 7
)
"""
        fixed = """\
X = (
    1 +  # 1
    2 +  # 2
    3 +  # 3
    4 +  # 4
    5 +  # 5
    6 +  # 6
    7  # 7
)
"""
        with autopep8_context(line, options=['-aaa']) as result:
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
        line = """\
a.has_key(
    0
)
"""
        fixed = '0 in a\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w601_with_non_ascii(self):
        line = """\
# -*- coding: utf-8 -*-
## éはe
correct = dict().has_key('good syntax ?')
"""

        fixed = """\
# -*- coding: utf-8 -*-
# éはe
correct = 'good syntax ?' in dict()
"""

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
        line = 'raise ValueError, \\\r\n"hello"\r\n'
        fixed = 'raise ValueError("hello")\r\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_indentation(self):
        line = 'def foo():\n    raise ValueError, "hello"\n'
        fixed = 'def foo():\n    raise ValueError("hello")\n'
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_w602_escaped_cr(self):
        line = 'raise ValueError, \\\r"hello"\n\n'
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

    def test_w602_invalid_2to3_fixed_case(self):
        line = """\
raise (ValueError
       if True else TypeError)
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(line, result)

    @unittest.skip('TODO')
    def test_w602_invalid_2to3_fixed_case_with_valid_syntax(self):
        line = """\
raise (ValueError
       if True else TypeError)
raise ValueError, "error"
"""
        fixed = """\
raise (ValueError
       if True else TypeError)
raise ValueError("error")
"""
        with autopep8_context(line, options=['--aggressive']) as result:
            self.assertEqual(fixed, result)

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

    def test_w605_simple(self):
        line = "escape = '\.jpg'\n"
        fixed = "escape = r'\.jpg'\n"
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

    # FIXME: These tests should use multiline strings for readability.
    def test_range(self):
        line = 'print( 1 )\nprint( 2 )\n print( 3 )\n'
        fixed = 'print( 1 )\nprint(2)\n print( 3 )\n'
        with autopep8_context(line, options=['--line-range', '2', '2']) as result:
            self.assertEqual(fixed, result)

    def test_range_line_number_changes_from_one_line(self):
        line = 'a=12\na=1; b=2;c=3\nd=4;\n\ndef f(a = 1):\n    pass\n'
        fixed = 'a=12\na = 1\nb = 2\nc = 3\nd=4;\n\ndef f(a = 1):\n    pass\n'
        with autopep8_context(line, options=['--line-range', '2', '2']) as result:
            self.assertEqual(fixed, result)

    def test_range_indent_changes_small_range(self):
        line = '\nif True:\n  (1, \n    2,\n3)\nelif False:\n  a = 1\nelse:\n  a = 2\n\nc = 1\nif True:\n  c = 2\n  a = (1,\n2)\n'
        fixed2_5 = '\nif True:\n  (1,\n   2,\n   3)\nelif False:\n  a = 1\nelse:\n  a = 2\n\nc = 1\nif True:\n  c = 2\n  a = (1,\n2)\n'
        with autopep8_context(line, options=['--line-range', '2', '5']) as result:
            self.assertEqual(fixed2_5, result)

    def test_range_indent_deep_if_blocks_first_block(self):
        line = '\nif a:\n  if a = 1:\n    b = 1\n  else:\n    b = 2\nelif a == 0:\n  b = 3\nelse:\n  b = 4\n'
        with autopep8_context(line, options=['--line-range', '2', '5']) as result:
            self.assertEqual(line, result)

    def test_range_indent_deep_if_blocks_second_block(self):
        line = '\nif a:\n  if a = 1:\n    b = 1\n  else:\n    b = 2\nelif a == 0:\n  b = 3\nelse:\n  b = 4\n'
        with autopep8_context(line, options=['--line-range', '6', '9']) as result:
            self.assertEqual(line, result)

    def test_range_indent_continued_statements_partial(self):
        line = '\nif a == 1:\n\ttry:\n\t  foo\n\texcept AttributeError:\n\t  pass\n\telse:\n\t  "nooo"\n\tb = 1\n'
        with autopep8_context(line, options=['--line-range', '2', '6']) as result:
            self.assertEqual(line, result)

    def test_range_indent_continued_statements_last_block(self):
        line = '\nif a == 1:\n\ttry:\n\t  foo\n\texcept AttributeError:\n\t  pass\n\telse:\n\t  "nooo"\n\tb = 1\n'
        with autopep8_context(line, options=['--line-range', '6', '9']) as result:
            self.assertEqual(line, result)

    def test_range_with_broken_syntax(self):
        line = """\
if True:
   if True:
      pass
 else:
    pass
"""
        with autopep8_context(line, options=['--line-range', '1', '1']) as result:
            self.assertEqual(line, result)


class CommandLineTests(unittest.TestCase):

    maxDiff = None

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

    def test_diff_with_standard_in(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['--diff', '-'],
                  stdout=PIPE, stderr=PIPE)
        error = p.communicate()[1].decode('utf-8')
        self.assertIn('cannot', error)

    def test_pep8_passes(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        with autopep8_subprocess(line, ['--pep8-passes', '0']) as result:
            self.assertEqual(fixed, result)

    def test_pep8_ignore(self):
        line = "'abc'  \n"
        with autopep8_subprocess(line, ['--ignore=E,W']) as result:
            self.assertEqual(line, result)

    def test_pep8_ignore_should_handle_trailing_comma_gracefully(self):
        line = "'abc'  \n"
        fixed = "'abc'\n"
        with autopep8_subprocess(line, ['--ignore=,']) as result:
            self.assertEqual(fixed, result)

    def test_help(self):
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + ['-h'],
                  stdout=PIPE)
        self.assertIn('usage:', p.communicate()[0].decode('utf-8').lower())

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
            shutil.rmtree(temp_directory)

    def test_recursive_should_not_crash_on_unicode_filename(self):
        temp_directory = tempfile.mkdtemp(dir='.')
        try:
            for filename in ['x.py', 'é.py', 'é.txt']:
                with open(os.path.join(temp_directory, filename), 'w'):
                    pass

            p = Popen(list(AUTOPEP8_CMD_TUPLE) +
                      [temp_directory,
                       '--recursive',
                       '--diff'],
                      stdout=PIPE)
            self.assertFalse(p.communicate()[0])
            self.assertEqual(0, p.returncode)
        finally:
            shutil.rmtree(temp_directory)

    def test_recursive_should_ignore_hidden(self):
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
            shutil.rmtree(temp_directory)

    def test_exclude(self):
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
            shutil.rmtree(temp_directory)

    def test_invalid_option_combinations(self):
        line = "'abc'  \n"
        with temporary_file_context(line) as filename:
            for options in [['--recursive', filename],  # without --diff
                            ['--jobs=2', filename],  # without --diff
                            ['--max-line-length=0', filename],
                            [],  # no argument
                            ['-', '--in-place'],
                            ['-', '--recursive'],
                            ['-', filename],
                            ['--line-range', '0', '2', filename],
                            ['--line-range', '2', '1', filename],
                            ['--line-range', '-1', '-1', filename],
                            ]:
                p = Popen(list(AUTOPEP8_CMD_TUPLE) + options,
                          stderr=PIPE)
                result = p.communicate()[1].decode('utf-8')
                self.assertNotEqual(0, p.returncode, msg=str(options))
                self.assertTrue(len(result))

    def test_list_fixes(self):
        with autopep8_subprocess('', options=['--list-fixes']) as result:
            self.assertIn('E121', result)

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


class ConfigurationTests(unittest.TestCase):

    def test_local_config(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
             '--global-config={}'.format(os.devnull)],
            apply_config=True)
        self.assertEqual(args.indent_size, 2)

    def test_config_override(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
             '--indent-size=7'],
            apply_config=True)
        self.assertEqual(args.indent_size, 7)

    def test_config_false_with_local(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
             '--global-config=False'],
            apply_config=True)
        self.assertEqual(args.global_config, 'False')
        self.assertEqual(args.indent_size, 2)

    def test_config_false_with_local_space(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
             '--global-config', 'False'],
            apply_config=True)
        self.assertEqual(args.global_config, 'False')
        self.assertEqual(args.indent_size, 2)

    def test_local_pycodestyle_config_line_length(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_PYCODESTYLE_CONFIGURATION, 'foo.py'),
             '--global-config={}'.format(os.devnull)],
            apply_config=True)
        self.assertEqual(args.max_line_length, 40)

    def test_config_false_with_local_autocomplete(self):
        args = autopep8.parse_args(
            [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
             '--g', 'False'],
            apply_config=True)
        self.assertEqual(args.global_config, 'False')
        self.assertEqual(args.indent_size, 2)

    def test_config_false_without_local(self):
        args = autopep8.parse_args(['/nowhere/foo.py',
                                    '--global-config={}'.format(os.devnull)],
                                   apply_config=True)
        self.assertEqual(args.indent_size, 4)

    def test_global_config_with_locals(self):
        with temporary_file_context('[pep8]\nindent-size=3\n') as filename:
            args = autopep8.parse_args(
                [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
                 '--global-config={}'.format(filename)],
                apply_config=True)
            self.assertEqual(args.indent_size, 2)

    def test_global_config_ignore_locals(self):
        with temporary_file_context('[pep8]\nindent-size=3\n') as filename:
            args = autopep8.parse_args(
                [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
                 '--global-config={}'.format(filename),
                 '--ignore-local-config'],
                apply_config=True)
            self.assertEqual(args.indent_size, 3)

    def test_global_config_without_locals(self):
        with temporary_file_context('[pep8]\nindent-size=3\n') as filename:
            args = autopep8.parse_args(
                ['/nowhere/foo.py', '--global-config={}'.format(filename)],
                apply_config=True)
            self.assertEqual(args.indent_size, 3)

    def test_config_local_int_value(self):
        with temporary_file_context('[pep8]\naggressive=1\n') as filename:
            args = autopep8.parse_args(
                [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
                 '--global-config={}'.format(filename)],
                apply_config=True)
            self.assertEqual(args.aggressive, 1)

    def test_config_local_inclue_invalid_key(self):
        configstr = """\
[pep8]
count=True
aggressive=1
"""
        with temporary_file_context(configstr) as filename:
            args = autopep8.parse_args(
                [os.path.join(FAKE_CONFIGURATION, 'foo.py'),
                 '--global-config={}'.format(filename)],
                apply_config=True)
            self.assertEqual(args.aggressive, 1)


class ExperimentalSystemTests(unittest.TestCase):

    maxDiff = None

    def test_e501_experimental_basic(self):
        line = """\
print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\
print(111, 111, 111, 111, 222, 222, 222, 222,
      222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_commas_and_colons(self):
        line = """\
foobar = {'aaaaaaaaaaaa': 'bbbbbbbbbbbbbbbb', 'dddddd': 'eeeeeeeeeeeeeeee', 'ffffffffffff': 'gggggggg'}
"""
        fixed = """\
foobar = {'aaaaaaaaaaaa': 'bbbbbbbbbbbbbbbb',
          'dddddd': 'eeeeeeeeeeeeeeee', 'ffffffffffff': 'gggggggg'}
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_inline_comments(self):
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
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_inline_comments_should_skip_multiline(
            self):
        line = """\
'''This should be left alone. -----------------------------------------------------

'''  # foo

'''This should be left alone. -----------------------------------------------------

''' \\
# foo

'''This should be left alone. -----------------------------------------------------

''' \\
\\
# foo
"""
        fixed = """\
'''This should be left alone. -----------------------------------------------------

'''  # foo

'''This should be left alone. -----------------------------------------------------

'''  # foo

'''This should be left alone. -----------------------------------------------------

'''  # foo
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_inline_comments_should_skip_keywords(self):
        line = """\
'                                                          '  # noqa Long inline comments should be moved above.
if True:
    '                                                          '  # pylint: disable-msgs=E0001
    '                                                          '  # pragma: no cover
    '                                                          '  # pragma: no cover
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_with_inline_comments_should_skip_edge_cases(
            self):
        line = """\
if True:
    x = \\
        '                                                          '  # Long inline comments should be moved above.
"""
        fixed = """\
if True:
    # Long inline comments should be moved above.
    x = '                                                          '
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_basic_should_prefer_balanced_brackets(self):
        line = """\
if True:
    reconstructed = iradon(radon(image), filter="ramp", interpolation="nearest")
"""
        fixed = """\
if True:
    reconstructed = iradon(
        radon(image),
        filter="ramp", interpolation="nearest")
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_very_long_line(self):
        line = """\
x = [3244234243234, 234234234324, 234234324, 23424234, 234234234, 234234, 234243, 234243, 234234234324, 234234324, 23424234, 234234234, 234234, 234243, 234243]
"""
        fixed = """\
x = [3244234243234, 234234234324, 234234324, 23424234, 234234234, 234234, 234243,
     234243, 234234234324, 234234324, 23424234, 234234234, 234234, 234243, 234243]
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_shorten_at_commas_skip(self):
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
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_shorter_length(self):
        line = """\
foooooooooooooooooo('abcdefghijklmnopqrstuvwxyz')
"""
        fixed = """\
foooooooooooooooooo(
    'abcdefghijklmnopqrstuvwxyz')
"""
        with autopep8_context(line,
                              options=['--max-line-length=40',
                                       '--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_indent(self):
        line = """\

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\

def d():
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_alone_with_indentation(self):
        line = """\
if True:
    print(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\
if True:
    print(111, 111, 111, 111, 222, 222, 222, 222,
          222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        with autopep8_context(line, options=['--select=E501',
                                             '--experimental']) as result:
            self.assertEqual(fixed, result)

    @unittest.skip('Not sure why space is not removed anymore')
    def test_e501_experimental_alone_with_tuple(self):
        line = """\
fooooooooooooooooooooooooooooooo000000000000000000000000 = [1,
                                                            ('TransferTime', 'FLOAT')
                                                           ]
"""
        fixed = """\
fooooooooooooooooooooooooooooooo000000000000000000000000 = [
    1, ('TransferTime', 'FLOAT')]
"""
        with autopep8_context(line, options=['--select=E501',
                                             '--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_should_not_try_to_break_at_every_paren_in_arithmetic(
            self):
        line = """\
term3 = w6 * c5 * (8.0 * psi4 * (11.0 - 24.0 * t2) - 28 * psi3 * (1 - 6.0 * t2) + psi2 * (1 - 32 * t2) - psi * (2.0 * t2) + t4) / 720.0
this_should_be_shortened = ('                                                                 ', '            ')
"""
        fixed = """\
term3 = w6 * c5 * (8.0 * psi4 * (11.0 - 24.0 * t2) - 28 * psi3 * (1 - 6.0 * t2) +
                   psi2 * (1 - 32 * t2) - psi * (2.0 * t2) + t4) / 720.0
this_should_be_shortened = (
    '                                                                 ',
    '            ')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_arithmetic_operator_with_indent(self):
        line = """\
def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        fixed = """\
def d():
    111 + 111 + 111 + 111 + 111 + 222 + 222 + 222 + 222 + \\
        222 + 222 + 222 + 222 + 222 + 333 + 333 + 333 + 333
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_more_complicated(self):
        line = """\
blahblah = os.environ.get('blahblah') or os.environ.get('blahblahblah') or os.environ.get('blahblahblahblah')
"""
        fixed = """\
blahblah = os.environ.get('blahblah') or os.environ.get(
    'blahblahblah') or os.environ.get('blahblahblahblah')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_skip_even_more_complicated(self):
        line = """\
if True:
    if True:
        if True:
            blah = blah.blah_blah_blah_bla_bl(blahb.blah, blah.blah,
                                              blah=blah.label, blah_blah=blah_blah,
                                              blah_blah2=blah_blah)
"""
        fixed = """\
if True:
    if True:
        if True:
            blah = blah.blah_blah_blah_bla_bl(
                blahb.blah, blah.blah, blah=blah.label, blah_blah=blah_blah,
                blah_blah2=blah_blah)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_logical_fix(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_logical_fix_and_physical_fix(self):
        line = """\
# ------ ------------------------------------------------------------------------
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
# ------ -----------------------------------------------------------------
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc,
    dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_logical_fix_and_adjacent_strings(self):
        line = """\
print('a-----------------------' 'b-----------------------' 'c-----------------------'
      'd-----------------------''e'"f"r"g")
"""
        fixed = """\
print(
    'a-----------------------'
    'b-----------------------'
    'c-----------------------'
    'd-----------------------'
    'e'
    "f"
    r"g")
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_multiple_lines(self):
        line = """\
foo_bar_zap_bing_bang_boom(111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,
                           111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333)
"""
        fixed = """\
foo_bar_zap_bing_bang_boom(
    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333,
    111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_do_not_break_on_keyword(self):
        # We don't want to put a newline after equals for keywords as this
        # violates PEP 8.
        line = """\
if True:
    long_variable_name = tempfile.mkstemp(prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        fixed = """\
if True:
    long_variable_name = tempfile.mkstemp(
        prefix='abcdefghijklmnopqrstuvwxyz0123456789')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_do_not_begin_line_with_comma(self):
        line = """\
def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction( [MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine() )
"""
        fixed = """\
def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction(
                    [MODIFY70.text, OBJECTBINDING71.text, COLON72.text],
                    MODIFY70.getLine(),
                    MODIFY70.getCharPositionInLine())
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_should_not_break_on_dot(self):
        line = """\
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx('xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(d='xxxxxxxxxxxxxxx'))
"""
        fixed = """\
if True:
    if True:
        raise xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx(
            'xxxxxxxxxxxxxxxxx "{d}" xxxxxxxxxxxxxx'.format(
                d='xxxxxxxxxxxxxxx'))
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_comment(self):
        line = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        pass

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        fixed = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will
                        # wrap it using textwrap to be within 72 characters.
                        pass

# http://foo.bar/abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-abc-

# The following is ugly commented-out code and should not be touched.
#xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx = 1
"""
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_comment_should_not_modify_docstring(self):
        line = '''\
def foo():
    """
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
    """
'''
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_should_only_modify_last_comment(self):
        line = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
"""
        fixed = """123
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        # This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 1. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 2. This is a long comment that should be wrapped. I will wrap it using textwrap to be within 72 characters.
                        # 3. This is a long comment that should be wrapped. I
                        # will wrap it using textwrap to be within 72
                        # characters.
"""
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_should_not_interfere_with_non_comment(self):
        line = '''
"""
# not actually a comment %d. 12345678901234567890, 12345678901234567890, 12345678901234567890.
""" % (0,)
'''
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_should_cut_comment_pattern(self):
        line = """123
# -- Useless lines ----------------------------------------------------------------------
321
"""
        fixed = """123
# -- Useless lines -------------------------------------------------------
321
"""
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_function_should_not_break_on_colon(self):
        line = r"""
class Useless(object):

    def _table_field_is_plain_widget(self, widget):
        if widget.__class__ == Widget or\
                (widget.__class__ == WidgetMeta and Widget in widget.__bases__):
            return True

        return False
"""
        fixed = r"""
class Useless(object):

    def _table_field_is_plain_widget(self, widget):
        if widget.__class__ == Widget or(
                widget.__class__ == WidgetMeta and Widget in widget.__bases__):
            return True

        return False
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental(self):
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
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_and_multiple_logical_lines(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(aaaaaaaaaaaaaaaaaaaaaaa,
                             bbbbbbbbbbbbbbbbbbbbbbbbbbbb, cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
xxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    aaaaaaaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbbbbbbbbbbbbbb,
    cccccccccccccccccccccccccccc, dddddddddddddddddddddddd)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_and_multiple_logical_lines_with_math(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx([-1 + 5 / -10,
                                                                            100,
                                                                            -3 - 4])
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx(
    [-1 + 5 / -10, 100, -3 - 4])
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_and_import(self):
        line = """\
from . import (xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
               yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy)
"""
        fixed = """\
from . import (
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx,
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_shorten_comment_with_experimental(self):
        line = """\
# ------ -------------------------------------------------------------------------
"""
        fixed = """\
# ------ -----------------------------------------------------------------
"""
        with autopep8_context(line, options=['--experimental',
                                             '--aggressive']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_escaped_newline(self):
        line = """\
if True or \\
    False:  # test test test test test test test test test test test test test test
    pass
"""
        fixed = """\
if True or \\
        False:  # test test test test test test test test test test test test test test
    pass
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_multiline_string(self):
        line = """\
print('---------------------------------------------------------------------',
      ('================================================', '====================='),
      '''--------------------------------------------------------------------------------
      ''')
"""
        fixed = """\
print(
    '---------------------------------------------------------------------',
    ('================================================',
     '====================='),
    '''--------------------------------------------------------------------------------
      ''')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_multiline_string_with_addition(self):
        line = '''\
def f():
    email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>"""
'''
        fixed = '''\
def f():
    email_text += """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>"""
'''
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_multiline_string_in_parens(self):
        line = '''\
def f():
    email_text += ("""<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>""")
'''
        fixed = '''\
def f():
    email_text += (
        """<html>This is a really long docstring that goes over the column limit and is multi-line.<br><br>
<b>Czar: </b>"""+despot["Nicholas"]+"""<br>
<b>Minion: </b>"""+serf["Dmitri"]+"""<br>
<b>Residence: </b>"""+palace["Winter"]+"""<br>
</body>
</html>""")
'''
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_indentation(self):
        line = """\
if True:
    # comment here
    print(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
          bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,cccccccccccccccccccccccccccccccccccccccccc)
"""
        fixed = """\
if True:
    # comment here
    print(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,
          bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb,
          cccccccccccccccccccccccccccccccccccccccccc)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_multiple_keys_and_experimental(self):
        line = """\
one_two_three_four_five_six = {'one two three four five': 12345, 'asdfsdflsdkfjl sdflkjsdkfkjsfjsdlkfj sdlkfjlsfjs': '343',
                               1: 1}
"""
        fixed = """\
one_two_three_four_five_six = {
    'one two three four five': 12345,
    'asdfsdflsdkfjl sdflkjsdkfkjsfjsdlkfj sdlkfjlsfjs': '343', 1: 1}
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_with_experimental_and_carriage_returns_only(self):
        """Make sure _find_logical() does not crash."""
        line = 'if True:\r    from aaaaaaaaaaaaaaaa import bbbbbbbbbbbbbbbbbbb\r    \r    ccccccccccc = None\r'
        fixed = 'if True:\r    from aaaaaaaaaaaaaaaa import bbbbbbbbbbbbbbbbbbb\r\r    ccccccccccc = None\r'
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_should_ignore_imports(self):
        line = """\
import logging, os, bleach, commonware, urllib2, json, time, requests, urlparse, re
"""
        with autopep8_context(line, options=['--select=E501',
                                             '--experimental']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_should_not_do_useless_things(self):
        line = """\
foo('                                                                            ')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_with_percent(self):
        line = """\
raise MultiProjectException("Ambiguous workspace: %s=%s, %s" % ( varname, varname_path, os.path.abspath(config_filename)))
"""
        fixed = """\
raise MultiProjectException(
    "Ambiguous workspace: %s=%s, %s" %
    (varname, varname_path, os.path.abspath(config_filename)))
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_def(self):
        line = """\
def foobar(sldfkjlsdfsdf, kksdfsdfsf,sdfsdfsdf, sdfsdfkdk, szdfsdfsdf, sdfsdfsdfsdlkfjsdlf, sdfsdfddf,sdfsdfsfd, sdfsdfdsf):
    pass
"""
        fixed = """\
def foobar(sldfkjlsdfsdf, kksdfsdfsf, sdfsdfsdf, sdfsdfkdk, szdfsdfsdf,
           sdfsdfsdfsdlkfjsdlf, sdfsdfddf, sdfsdfsfd, sdfsdfdsf):
    pass
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_tuple(self):
        line = """\
def f():
    man_this_is_a_very_long_function_name(an_extremely_long_variable_name,
                                          ('a string that is long: %s'%'bork'))
"""
        fixed = """\
def f():
    man_this_is_a_very_long_function_name(
        an_extremely_long_variable_name,
        ('a string that is long: %s' % 'bork'))
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_tuple_in_list(self):
        line = """\
def f(self):
    self._xxxxxxxx(aaaaaa, bbbbbbbbb, cccccccccccccccccc,
                   [('mmmmmmmmmm', self.yyyyyyyyyy.zzzzzzzz/_DDDDDD)], eee, 'ff')
"""
        fixed = """\
def f(self):
    self._xxxxxxxx(
        aaaaaa, bbbbbbbbb, cccccccccccccccccc,
        [('mmmmmmmmmm', self.yyyyyyyyyy.zzzzzzzz / _DDDDDD)],
        eee, 'ff')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_complex_reformat(self):
        line = """\
bork(111, 111, 111, 111, 222, 222, 222, { 'foo': 222, 'qux': 222 }, ((['hello', 'world'], ['yo', 'stella', "how's", 'it'], ['going']), {str(i): i for i in range(10)}, {'bork':((x, x**x) for x in range(10))}), 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\
bork(
    111, 111, 111, 111, 222, 222, 222, {'foo': 222, 'qux': 222},
    ((['hello', 'world'],
      ['yo', 'stella', "how's", 'it'],
      ['going']),
     {str(i): i for i in range(10)},
     {'bork': ((x, x ** x) for x in range(10))}),
    222, 222, 222, 222, 333, 333, 333, 333)
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_dot_calls(self):
        line = """\
if True:
    logging.info('aaaaaa bbbbb dddddd ccccccc eeeeeee fffffff gg: %s',
        xxxxxxxxxxxxxxxxx.yyyyyyyyyyyyyyyyyyyyy(zzzzzzzzzzzzzzzzz.jjjjjjjjjjjjjjjjj()))
"""
        fixed = """\
if True:
    logging.info(
        'aaaaaa bbbbb dddddd ccccccc eeeeeee fffffff gg: %s',
        xxxxxxxxxxxxxxxxx.yyyyyyyyyyyyyyyyyyyyy(
            zzzzzzzzzzzzzzzzz.jjjjjjjjjjjjjjjjj()))
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_avoid_breaking_at_empty_parentheses_if_possible(
            self):
        line = """\
someverylongindenttionwhatnot().foo().bar().baz("and here is a long string 123456789012345678901234567890")
"""
        fixed = """\
someverylongindenttionwhatnot().foo().bar().baz(
    "and here is a long string 123456789012345678901234567890")
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_unicode(self):
        line = """\
someverylongindenttionwhatnot().foo().bar().baz("and here is a l안녕하세요 123456789012345678901234567890")
"""
        fixed = """\
someverylongindenttionwhatnot().foo().bar().baz(
    "and here is a l안녕하세요 123456789012345678901234567890")
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_tuple_assignment(self):
        line = """\
if True:
    (xxxxxxx,) = xxxx.xxxxxxx.xxxxx(xxxxxxxxxxxx.xx).xxxxxx(xxxxxxxxxxxx.xxxx == xxxx.xxxx).xxxxx()
"""
        fixed = """\
if True:
    (xxxxxxx,) = xxxx.xxxxxxx.xxxxx(xxxxxxxxxxxx.xx).xxxxxx(
        xxxxxxxxxxxx.xxxx == xxxx.xxxx).xxxxx()
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    @unittest.skip('To do')
    def test_e501_experimental_tuple_on_line(self):
        line = """\
def f():
    self.aaaaaaaaa(bbbbbb, ccccccccc, dddddddddddddddd,
                   ((x, y/eeeeeee) for x, y in self.outputs.total.iteritems()),
                   fff, 'GG')
"""
        fixed = """\
def f():
    self.aaaaaaaaa(
        bbbbbb, ccccccccc, dddddddddddddddd,
        ((x, y / eeeeeee) for x, y in self.outputs.total.iteritems()),
        fff, 'GG')
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_tuple_on_line_two_space_indent(self):
        line = """\
def f():
  self.aaaaaaaaa(bbbbbb, ccccccccc, dddddddddddddddd,
                 ((x, y/eeeeeee) for x, y in self.outputs.total.iteritems()),
                 fff, 'GG')
"""
        fixed = """\
def f():
  self.aaaaaaaaa(bbbbbb, ccccccccc, dddddddddddddddd,
                 ((x, y/eeeeeee) for x, y in self.outputs.total.iteritems()),
                 fff, 'GG')
"""
        with autopep8_context(line, options=['--experimental',
                                             '--indent-size=2']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_oversized_default_initializer(self):
        line = """\
aaaaaaaaaaaaaaaaaaaaa(lllll,mmmmmmmm,nnn,fffffffffff,ggggggggggg,hhh,ddddddddddddd=eeeeeeeee,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=ccccccccccccccccccccccccccccccccccccccccccccccccc,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=cccccccccccccccccccccccccccccccccccccccccccccccc)
"""
        fixed = """\
aaaaaaaaaaaaaaaaaaaaa(
    lllll, mmmmmmmm, nnn, fffffffffff, ggggggggggg, hhh,
    ddddddddddddd=eeeeeeeee,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=ccccccccccccccccccccccccccccccccccccccccccccccccc,
    bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=cccccccccccccccccccccccccccccccccccccccccccccccc)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_decorator(self):
        line = """\
@foo(('xxxxxxxxxxxxxxxxxxxxxxxxxx', users.xxxxxxxxxxxxxxxxxxxxxxxxxx), ('yyyyyyyyyyyy', users.yyyyyyyyyyyy), ('zzzzzzzzzzzzzz', users.zzzzzzzzzzzzzz))
"""
        fixed = """\


@foo(('xxxxxxxxxxxxxxxxxxxxxxxxxx', users.xxxxxxxxxxxxxxxxxxxxxxxxxx),
     ('yyyyyyyyyyyy', users.yyyyyyyyyyyy),
     ('zzzzzzzzzzzzzz', users.zzzzzzzzzzzzzz))
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_long_class_name(self):
        line = """\
class AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB):
    pass
"""
        fixed = """\
class AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA(
        BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB):
    pass
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_no_line_change(self):
        line = """\
def f():
    return '<a href="javascript:;" class="copy-to-clipboard-button" data-clipboard-text="%s" title="copy url to clipboard">Copy Link</a>' % url
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(line, result)

    def test_e501_experimental_splitting_small_arrays(self):
        line = """\
def foo():
    unspecified[service] = ('# The %s brown fox jumped over the lazy, good for nothing '
                            'dog until it grew tired and set its sights upon the cat!' % adj)
"""
        fixed = """\
def foo():
    unspecified[service] = (
        '# The %s brown fox jumped over the lazy, good for nothing '
        'dog until it grew tired and set its sights upon the cat!' % adj)
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_no_splitting_in_func_call(self):
        line = """\
def foo():
    if True:
        if True:
            function.calls('%r (%s): aaaaaaaa bbbbbbbbbb ccccccc ddddddd eeeeee (%d, %d)',
                           xxxxxx.yy, xxxxxx.yyyy, len(mmmmmmmmmmmmm['fnord']),
                           len(mmmmmmmmmmmmm['asdfakjhdsfkj']))
"""
        fixed = """\
def foo():
    if True:
        if True:
            function.calls(
                '%r (%s): aaaaaaaa bbbbbbbbbb ccccccc ddddddd eeeeee (%d, %d)',
                xxxxxx.yy, xxxxxx.yyyy, len(mmmmmmmmmmmmm['fnord']),
                len(mmmmmmmmmmmmm['asdfakjhdsfkj']))
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_no_splitting_at_dot(self):
        line = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx = [yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.MMMMMM_NNNNNNN_OOOOO,
                                yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.PPPPPP_QQQQQQQ_RRRRR,
                                yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.SSSSSS_TTTTTTT_UUUUU]
"""
        fixed = """\
xxxxxxxxxxxxxxxxxxxxxxxxxxxx = [
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.MMMMMM_NNNNNNN_OOOOO,
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.PPPPPP_QQQQQQQ_RRRRR,
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.SSSSSS_TTTTTTT_UUUUU]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_no_splitting_before_arg_list(self):
        line = """\
xxxxxxxxxxxx = [yyyyyy['yyyyyy'].get('zzzzzzzzzzz') for yyyyyy in x.get('aaaaaaaaaaa') if yyyyyy['yyyyyy'].get('zzzzzzzzzzz')]
"""
        fixed = """\
xxxxxxxxxxxx = [yyyyyy['yyyyyy'].get('zzzzzzzzzzz')
                for yyyyyy in x.get('aaaaaaaaaaa')
                if yyyyyy['yyyyyy'].get('zzzzzzzzzzz')]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_dont_split_if_looks_bad(self):
        line = """\
def f():
    if True:
        BAD(('xxxxxxxxxxxxx', 42), 'I died for beauty, but was scarce / Adjusted in the tomb %s', yyyyyyyyyyyyy)
"""
        fixed = """\
def f():
    if True:
        BAD(('xxxxxxxxxxxxx', 42),
            'I died for beauty, but was scarce / Adjusted in the tomb %s',
            yyyyyyyyyyyyy)
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_list_comp(self):
        line = """\
xxxxxxxxxxxs = [xxxxxxxxxxx for xxxxxxxxxxx in xxxxxxxxxxxs if not yyyyyyyyyyyy[xxxxxxxxxxx] or not yyyyyyyyyyyy[xxxxxxxxxxx].zzzzzzzzzz]
"""
        fixed = """\
xxxxxxxxxxxs = [
    xxxxxxxxxxx for xxxxxxxxxxx in xxxxxxxxxxxs
    if not yyyyyyyyyyyy[xxxxxxxxxxx] or
    not yyyyyyyyyyyy[xxxxxxxxxxx].zzzzzzzzzz]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

        line = """\
def f():
    xxxxxxxxxx = [f for f in yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.zzzzzzzzzzzzzzzzzzzzzzzz.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
"""
        fixed = """\
def f():
    xxxxxxxxxx = [
        f
        for f in
        yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy.zzzzzzzzzzzzzzzzzzzzzzzz.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_dict(self):
        line = """\
def f():
    zzzzzzzzzzzzz = {
        'aaaaaa/bbbbbb/ccccc/dddddddd/eeeeeeeee/fffffffffff/ggggggggg/hhhhhhhh.py':
            yyyyyyyyyyy.xxxxxxxxxxx(
                'aa/bbbbbbb/cc/ddddddd/eeeeeeeeeee/fffffffffff/ggggggggg/hhhhhhh/ggggg.py',
                '00000000',
                yyyyyyyyyyy.xxxxxxxxx.zzzz),
    }
"""
        fixed = """\
def f():
    zzzzzzzzzzzzz = {
        'aaaaaa/bbbbbb/ccccc/dddddddd/eeeeeeeee/fffffffffff/ggggggggg/hhhhhhhh.py':
        yyyyyyyyyyy.xxxxxxxxxxx(
            'aa/bbbbbbb/cc/ddddddd/eeeeeeeeeee/fffffffffff/ggggggggg/hhhhhhh/ggggg.py',
            '00000000', yyyyyyyyyyy.xxxxxxxxx.zzzz), }
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_indentation(self):
        line = """\
class Klass(object):

    '''Class docstring.'''

    def Quote(self, parameter_1, parameter_2, parameter_3, parameter_4, parameter_5):
        pass
"""
        fixed = """\
class Klass(object):

  '''Class docstring.'''

  def Quote(
      self, parameter_1, parameter_2, parameter_3, parameter_4,
          parameter_5):
    pass
"""

        with autopep8_context(line, options=['--experimental',
                                             '--indent-size=2']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_long_function_call_elements(self):
        line = """\
def g():
    pppppppppppppppppppppppppp1, pppppppppppppppppppppppp2 = (
        zzzzzzzzzzzz.yyyyyyyyyyyyyy(aaaaaaaaa=10, bbbbbbbbbbbbbbbb='2:3',
                                    cccccccc='{1:2}', dd=1, eeeee=0),
        zzzzzzzzzzzz.yyyyyyyyyyyyyy(dd=7, aaaaaaaaa=16, bbbbbbbbbbbbbbbb='2:3',
                                    cccccccc='{1:2}',
                                    eeeee=xxxxxxxxxxxxxxxxx.wwwwwwwwwwwww.vvvvvvvvvvvvvvvvvvvvvvvvv))
"""
        fixed = """\
def g():
    pppppppppppppppppppppppppp1, pppppppppppppppppppppppp2 = (
        zzzzzzzzzzzz.yyyyyyyyyyyyyy(
            aaaaaaaaa=10, bbbbbbbbbbbbbbbb='2:3', cccccccc='{1:2}', dd=1,
            eeeee=0),
        zzzzzzzzzzzz.yyyyyyyyyyyyyy(
            dd=7, aaaaaaaaa=16, bbbbbbbbbbbbbbbb='2:3', cccccccc='{1:2}',
            eeeee=xxxxxxxxxxxxxxxxx.wwwwwwwwwwwww.vvvvvvvvvvvvvvvvvvvvvvvvv))
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_long_nested_tuples_in_arrays(self):
        line = """\
def f():
    aaaaaaaaaaa.bbbbbbb([
        ('xxxxxxxxxx', 'yyyyyy', 'Heaven hath no wrath like love to hatred turned. Nor hell a fury like a woman scorned.'),
        ('xxxxxxx', 'yyyyyyyyyyy', "To the last I grapple with thee. From hell's heart I stab at thee. For hate's sake I spit my last breath at thee!")])
"""
        fixed = """\
def f():
    aaaaaaaaaaa.bbbbbbb(
        [('xxxxxxxxxx', 'yyyyyy',
          'Heaven hath no wrath like love to hatred turned. Nor hell a fury like a woman scorned.'),
         ('xxxxxxx', 'yyyyyyyyyyy',
          "To the last I grapple with thee. From hell's heart I stab at thee. For hate's sake I spit my last breath at thee!")])
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_func_call_open_paren_not_separated(self):
        # Don't separate the opening paren of a function call from the
        # function's name.
        line = """\
def f():
    owned_list = [o for o in owned_list if self.display['zzzzzzzzzzzzzz'] in aaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbb(o.qq, ccccccccccccccccccccccccccc.ddddddddd.eeeeeee)]
"""
        fixed = """\
def f():
    owned_list = [
        o for o in owned_list
        if self.display['zzzzzzzzzzzzzz'] in aaaaaaaaaaaaaaaaa.bbbbbbbbbbbbbbbbbbbb(
            o.qq, ccccccccccccccccccccccccccc.ddddddddd.eeeeeee)]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_long_dotted_object(self):
        # Don't separate a long dotted object too soon. Otherwise, it may end
        # up with most of its elements on separate lines.
        line = """\
def f(self):
  return self.xxxxxxxxxxxxxxx(aaaaaaa.bbbbb.ccccccc.ddd.eeeeee.fffffffff.ggggg.hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh)
"""
        fixed = """\
def f(self):
    return self.xxxxxxxxxxxxxxx(
        aaaaaaa.bbbbb.ccccccc.ddd.eeeeee.fffffffff.ggggg.
        hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh)
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_parsing_dict_with_comments(self):
        line = """\
self.display['xxxxxxxxxxxx'] = [{'title': _('Library'),  #. This is the first comment.
    'flag': aaaaaaaaaa.bbbbbbbbb.cccccccccc
    }, {'title': _('Original'),  #. This is the second comment.
    'flag': aaaaaaaaaa.bbbbbbbbb.dddddddddd
    }, {'title': _('Unknown'),  #. This is the third comment.
    'flag': aaaaaaaaaa.bbbbbbbbb.eeeeeeeeee}]
"""
        fixed = """\
self.display['xxxxxxxxxxxx'] = [{'title': _('Library'),  # . This is the first comment.
                                 'flag': aaaaaaaaaa.bbbbbbbbb.cccccccccc
                                 # . This is the second comment.
                                 }, {'title': _('Original'),
                                     'flag': aaaaaaaaaa.bbbbbbbbb.dddddddddd
                                     # . This is the third comment.
                                     }, {'title': _('Unknown'),
                                         'flag': aaaaaaaaaa.bbbbbbbbb.eeeeeeeeee}]
"""

        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_if_line_over_limit(self):
        line = """\
if not xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    return 1
"""
        fixed = """\
if not xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc,
        dddddddddddddddddddddd):
    return 1
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_for_line_over_limit(self):
        line = """\
for aaaaaaaaa in xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    pass
"""
        fixed = """\
for aaaaaaaaa in xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc,
        dddddddddddddddddddddd):
    pass
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_while_line_over_limit(self):
        line = """\
while xxxxxxxxxxxx(aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc, dddddddddddddddddddddd):
    pass
"""
        fixed = """\
while xxxxxxxxxxxx(
        aaaaaaaaaaaaaaaaaa, bbbbbbbbbbbbbbbb, cccccccccccccc,
        dddddddddddddddddddddd):
    pass
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    def test_e501_experimental_with_in(self):
        line = """\
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            if True:
                                if k_left in ('any', k_curr) and k_right in ('any', k_curr):
                                    pass
"""
        fixed = """\
if True:
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            if True:
                                if k_left in (
                                        'any', k_curr) and k_right in (
                                        'any', k_curr):
                                    pass
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)

    @unittest.skipIf(sys.version_info.major >= 3, 'syntax error in Python3')
    def test_e501_print_isnot_function(self):
        line = """\

def d():
    print "%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d" % (111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333, 333, 333, 333)
"""
        fixed = """\

def d():
    print "%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d%d" % (
        111, 111, 111, 111, 222, 222, 222, 222, 222, 222, 222, 222, 222, 333,
        333, 333, 333)
"""
        with autopep8_context(line, options=['--experimental']) as result:
            self.assertEqual(fixed, result)


@contextlib.contextmanager
def autopep8_context(line, options=None):
    if not options:
        options = []

    with temporary_file_context(line) as filename:
        options = autopep8.parse_args([filename] + list(options))
        yield autopep8.fix_file(filename=filename, options=options)


@contextlib.contextmanager
def autopep8_subprocess(line, options):
    with temporary_file_context(line) as filename:
        p = Popen(list(AUTOPEP8_CMD_TUPLE) + [filename] + options,
                  stdout=PIPE)
        yield p.communicate()[0].decode('utf-8')


@contextlib.contextmanager
def temporary_file_context(text, suffix='', prefix=''):
    temporary = mkstemp(suffix=suffix, prefix=prefix)
    os.close(temporary[0])
    with autopep8.open_with_encoding(temporary[1],
                                     encoding='utf-8',
                                     mode='w') as temp_file:
        temp_file.write(text)
    yield temporary[1]
    os.remove(temporary[1])


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

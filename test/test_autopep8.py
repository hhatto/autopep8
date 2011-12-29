import os
import unittest
from subprocess import Popen, PIPE
from tempfile import mkstemp


class TestFixPEP8Error(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line):
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        root_dir = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
        p = Popen([os.path.join(root_dir, 'autopep8.py'),
                   self.tempfile[1]], stdout=PIPE)
        self.result = p.communicate()[0].decode('utf8')

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

    def test_e111_multiple_levels(self):
        line = """
while True:
    if True:
       1
"""
        fixed = """
while True:
    if True:
        1
"""
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

    def test_e225(self):
        line = "1+1\n2 +2\n3+ 3\n"
        fixed = "1 + 1\n2 + 2\n3 + 3\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e251(self):
        line = "def a(arg = 1):\n    print arg\n"
        fixed = "def a(arg=1):\n    print arg\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e261(self):
        line = "print 'a b '# comment\n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e261_with_dictionary(self):
        line = "d = {# comment\n1: 2}\n"
        fixed = "d = {  # comment\n1: 2}\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_more_space(self):
        line = "print 'a b '  #  comment\n"
        fixed = "print 'a b '  # comment\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_e262_none_space(self):
        line = "print 'a b '  #comment\n"
        fixed = "print 'a b '  # comment\n"
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


class TestFixPEP8Warn(unittest.TestCase):

    def setUp(self):
        self.tempfile = mkstemp()

    def tearDown(self):
        os.remove(self.tempfile[1])

    def _inner_setup(self, line):
        f = open(self.tempfile[1], 'w')
        f.write(line)
        f.close()
        root_dir = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]
        p = Popen([os.path.join(root_dir, 'autopep8.py'),
                   self.tempfile[1]], stdout=PIPE)
        self.result = p.communicate()[0].decode('utf8')

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
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w391(self):
        line = "  \n"
        fixed = ""
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w601(self):
        line = "a = {0: 1}\na.has_key(0)\n"
        fixed = "a = {0: 1}\n0 in a\n"
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

    def test_w602_arg_is_tuple(self):
        line = "raise ValueError, ('a', 'b')\n"
        fixed = "raise ValueError('a', 'b')\n"
        self._inner_setup(line)
        self.assertEqual(self.result, fixed)

    def test_w602_skip_multiline(self):
        # We do not support this yet
        line = 'raise ValueError, """\nhello"""\n'
        self._inner_setup(line)
        self.assertEqual(self.result, line)

    def test_w602_skip_multiline_with_double_quote(self):
        # We do not support this yet
        line = "raise ValueError, '''\nhello'''\n"
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

    def test_w604_skip_multiple_instances(self):
        # We do not support this yet
        line = "``1`` + ``b``\n"
        self._inner_setup(line)
        self.assertEqual(self.result, line)

if __name__ == '__main__':
    unittest.main()

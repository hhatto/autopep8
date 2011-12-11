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
        self.result = p.stdout.read()

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

if __name__ == '__main__':
    unittest.main()

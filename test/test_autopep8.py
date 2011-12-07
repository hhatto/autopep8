import os
import unittest
from subprocess import Popen, PIPE
from tempfile import mkstemp


class TestFixPEP8Error(unittest.TestCase):

    def _inner_setup(self, line):
        tempfile = mkstemp()
        f = open(tempfile[1], 'w')
        f.write(line)
        f.close()
        p = Popen(['autopep8', tempfile[1]], stdout=PIPE)
        self.result = p.stdout.read()
        os.remove(tempfile[1])

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

if __name__ == '__main__':
    unittest.main()

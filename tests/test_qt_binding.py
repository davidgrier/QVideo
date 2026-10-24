'''Unit tests for the error raised when no Qt binding is installed.'''
import subprocess
import sys
import unittest

_BLOCK = """
import sys
from importlib.abc import MetaPathFinder


class Block(MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6'):
            raise ModuleNotFoundError(name)


sys.meta_path.insert(0, Block())
"""


def run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-c', _BLOCK + code],
                          capture_output=True, text=True)


class TestMissingQtBinding(unittest.TestCase):

    def test_import_raises_import_error_naming_the_extra(self):
        result = run('import QVideo')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ImportError', result.stderr)
        self.assertIn('QVideo[pyqt6]', result.stderr)
        self.assertIn('QVideo[pyqt5]', result.stderr)

    def test_original_error_is_chained(self):
        result = run('import QVideo')
        self.assertIn('No Qt bindings could be found', result.stderr)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

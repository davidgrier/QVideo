'''qtpy must select the Qt binding before pyqtgraph can.

``qtpy`` honors ``QT_API``.  ``pyqtgraph`` chooses a binding of its own when
it is imported first, and ``qtpy`` then follows it, so ``QT_API`` is
ignored.  ``import QVideo`` imports ``qtpy`` first, so QVideo may stand in
for it.  The check reads the text of every source file, the scripts and
examples that sit in strings and documents included.
'''
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = ('.py', '.rst', '.md')
PYQTGRAPH = re.compile(r'^\s*(import pyqtgraph|from pyqtgraph)')
SELECTS = re.compile(r'^\s*(import qtpy|from qtpy|import QVideo|from QVideo)')


def sources():
    '''Yield the source files of the repository, not scratch directories.'''
    for path in sorted(ROOT.rglob('*')):
        parts = path.relative_to(ROOT).parts
        if (path.suffix in SUFFIXES and path.is_file()
                and not any(part.startswith('.') or part in
                            ('devel', 'build', '_build') or
                            part.endswith('.egg-info') for part in parts)):
            yield path


def first(pattern: re.Pattern, lines: list[str]) -> int | None:
    '''Return the number of the first line that matches *pattern*.'''
    for number, line in enumerate(lines, 1):
        if pattern.match(line):
            return number
    return None


class TestQtpyComesBeforePyqtgraph(unittest.TestCase):

    def test_no_file_imports_pyqtgraph_first(self):
        late = []
        for path in sources():
            lines = path.read_text(errors='replace').splitlines()
            graph = first(PYQTGRAPH, lines)
            if graph is None:
                continue
            select = first(SELECTS, lines)
            if select is None or graph < select:
                late.append(f'{path.relative_to(ROOT)}:{graph}')
        self.assertEqual(late, [], 'import qtpy (or QVideo) before pyqtgraph')

    def test_the_check_sees_a_late_import(self):
        lines = ['import pyqtgraph as pg', 'from qtpy import QtCore']
        self.assertLess(first(PYQTGRAPH, lines), first(SELECTS, lines))
        self.assertIsNone(first(SELECTS, ['import numpy']))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

'''The code in the quickstart must run.'''
import os
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


QUICKSTART = Path(__file__).parents[1] / 'docs' / 'quickstart.rst'

# Run for a moment, then quit and stop the source, instead of forever.
HARNESS = '''
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qtpy import QtCore
{code}
'''
QUIT = ('QtCore.QTimer.singleShot(300, app.quit)\n'
        'app.exec()\n'
        'source.stop()\n'
        'source.wait()\n')


def blocks() -> list[str]:
    '''Return the python code blocks of the quickstart.'''
    text = QUICKSTART.read_text()
    found = re.findall(r'\.\. code-block:: python\n\n((?:   .*\n|\n)+)', text)
    return [textwrap.dedent(block) for block in found]


class TestQuickstart(unittest.TestCase):

    def run_block(self, block: str) -> subprocess.CompletedProcess:
        code = HARNESS.format(code=block.replace('app.exec()\n', QUIT))
        return subprocess.run([sys.executable, '-c', code],
                              capture_output=True, text=True, timeout=60)

    def test_the_minimal_display_runs(self):
        block = next(b for b in blocks() if 'QVideoScreen()' in b
                     and 'QNoiseSource()' in b)
        result = self.run_block(block)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])

    def test_the_camera_controls_run(self):
        block = next(b for b in blocks() if 'QNoiseTree()' in b)
        result = self.run_block(block)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])


if __name__ == '__main__':
    unittest.main()

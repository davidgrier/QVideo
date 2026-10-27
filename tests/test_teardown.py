'''A window that holds running threads can be deleted while the app runs.

Qt aborts the process when it destroys a running thread, so the checks run
in a subprocess: the exit must be clean both when the application follows
the procedure in the "Shutting down" section of the architecture chapter
and when it only deletes the window.
'''
import os
import subprocess
import sys
import unittest

try:
    import trackpy  # noqa: F401
except ImportError:  # pragma: no cover
    trackpy = None


SCRIPT = '''
import sys
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets
from QVideo.cameras.Noise import QNoiseTree
from QVideo.demos.trackpydemo import TrackpyDemo

app = pg.mkQApp()
tree = QNoiseTree().start()
demo = TrackpyDemo(tree)
window = QtWidgets.QMainWindow()
window.setCentralWidget(demo)
window.show()
demo.trackpy.setChecked(True)


def teardown():
    if sys.argv[1] == 'stop-first':
        tree.stop()
        demo.trackpy.stop()
    window.deleteLater()
    QtCore.QTimer.singleShot(200, app.quit)


QtCore.QTimer.singleShot(500, teardown)
app.exec()
tree.stop()
print('clean exit')
'''


@unittest.skipIf(trackpy is None, 'trackpy is not installed')
class TestTeardown(unittest.TestCase):

    def deleteWindow(self, how: str) -> None:
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', SCRIPT, how],
                                capture_output=True, text=True,
                                timeout=60, env=env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn('clean exit', result.stdout)

    def test_stopping_before_deleting(self):
        self.deleteWindow('stop-first')

    def test_deleting_without_stopping(self):
        self.deleteWindow('delete-only')


SAVE_SCRIPT = '''
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
import pyqtgraph as pg
from qtpy import QtCore
from QVideo.dvr import QCircularDVRWidget, QDVRWidget
from QVideo.lib.videotypes import FrameInfo

app = pg.mkQApp()
done = Path(tempfile.mkdtemp()) / 'done'


class Slow(QtCore.QObject):
    """A writer that takes its time and leaves a mark when it is closed."""
    finished = QtCore.Signal()

    def __init__(self, filename, **kwargs):
        super().__init__()

    def write(self, frame, info=None):
        time.sleep(0.2)

    def close(self):
        done.write_text('closed')


QDVRWidget.Writer['.slow'] = Slow
widget = QCircularDVRWidget()
for i in range(3):
    widget.buffer.append(np.zeros((2, 2), np.uint8), FrameInfo(i, float(i)))
widget._fileEdit.setText('x.slow')
widget._save()
QtCore.QTimer.singleShot(100, app.quit if sys.argv[1] == 'quit' else
                         lambda: (widget.deleteLater(),
                                  QtCore.QTimer.singleShot(1000, app.quit)))
app.exec()
print('clean exit; the file was finished:', done.exists())
'''


class TestSavingTeardown(unittest.TestCase):
    '''Quitting, or deleting the widget, waits for a save that is running.'''

    def run_script(self, how: str) -> None:
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', SAVE_SCRIPT, how],
                                capture_output=True, text=True,
                                timeout=60, env=env)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertNotIn('Destroyed while thread', result.stderr)
        self.assertIn('the file was finished: True', result.stdout)

    def test_quitting_during_a_save(self):
        self.run_script('quit')

    def test_deleting_the_widget_during_a_save(self):
        self.run_script('delete')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

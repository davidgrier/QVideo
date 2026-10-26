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


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

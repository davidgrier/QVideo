'''Unit tests for dvr/icons_rc.py'''
import unittest
from pyqtgraph.Qt import QtWidgets
import QVideo.dvr.icons_rc as icons_rc


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestIconsRc(unittest.TestCase):

    def test_qInitResources_is_callable(self):
        self.assertTrue(callable(icons_rc.qInitResources))

    def test_qCleanupResources_is_callable(self):
        self.assertTrue(callable(icons_rc.qCleanupResources))

    def test_cleanup_and_reinit(self):
        icons_rc.qCleanupResources()
        icons_rc.qInitResources()


if __name__ == '__main__':
    unittest.main()

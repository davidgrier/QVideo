'''Unit tests for lib/_qapp.py.'''
import unittest
from unittest.mock import MagicMock, patch

from qtpy import QtCore, QtWidgets

from QVideo.lib import _qapp
from QVideo.lib._qapp import stopAtQuit


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestStopAtQuit(unittest.TestCase):

    def test_the_slot_runs_when_the_application_is_about_to_quit(self):
        called = []
        stopAtQuit(lambda: called.append(True))
        app.aboutToQuit.emit()
        self.assertEqual(called, [True])

    def test_a_bound_method_of_a_deleted_object_is_not_called(self):
        class Owner(QtCore.QObject):
            calls = 0

            def stop(self):
                Owner.calls += 1
        owner = Owner()
        stopAtQuit(owner.stop)
        owner.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(
            None, QtCore.QEvent.Type.DeferredDelete)
        app.aboutToQuit.emit()
        self.assertEqual(Owner.calls, 0)

    def test_without_an_application_it_does_nothing(self):
        slot = MagicMock()
        with patch.object(_qapp.QtCore.QCoreApplication, 'instance',
                          return_value=None):
            stopAtQuit(slot)
        app.aboutToQuit.emit()
        slot.assert_not_called()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

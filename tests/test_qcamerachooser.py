'''Unit tests for QCameraChooser.'''
import sys
import threading
import unittest
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.tests.fakes import until
from QVideo.tests.signals import record
from QVideo.widgets import QCameraChooser


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_MODULE = sys.modules['QVideo.widgets.QCameraChooser']
_CAMERAS = [('OpenCV', 0, 'FaceTime HD Camera'),
            ('OpenCV', 1, 'USB Camera'),
            ('Flir', 0, 'Flir'),
            ('Noise', 0, 'Noise')]


def scanning(cameras=_CAMERAS):
    '''Make a search find *cameras* at once.'''
    return patch.object(_MODULE, 'available_cameras', return_value=cameras)


def make_chooser(cameras=_CAMERAS, **kwargs) -> QCameraChooser:
    with scanning(cameras):
        chooser = QCameraChooser(**kwargs)
        until(lambda: chooser._scanner is None)
    return chooser


class TestScan(unittest.TestCase):

    def test_it_lists_the_cameras_that_were_found(self):
        chooser = make_chooser()
        self.assertEqual(chooser.count(), 4)
        self.assertTrue(chooser.isEnabled())

    def test_an_entry_names_the_model_the_id_and_the_device(self):
        chooser = make_chooser()
        self.assertEqual(chooser.itemText(0), 'OpenCV 0: FaceTime HD Camera')
        self.assertEqual(chooser.itemText(1), 'OpenCV 1: USB Camera')

    def test_a_device_that_has_only_its_model_for_a_name_is_not_repeated(self):
        chooser = make_chooser()
        self.assertEqual(chooser.itemText(2), 'Flir 0')
        self.assertEqual(chooser.itemText(3), 'Noise 0')

    def test_it_says_that_it_is_looking_while_it_looks(self):
        gate = threading.Event()

        def slowly():
            gate.wait(5)
            return _CAMERAS

        with patch.object(_MODULE, 'available_cameras', slowly):
            chooser = QCameraChooser()
            self.assertEqual(chooser.itemText(0), 'Looking for cameras...')
            self.assertFalse(chooser.isEnabled())
            self.assertIsNone(chooser.camera())
            gate.set()
            self.assertTrue(until(lambda: chooser._scanner is None))
        self.assertTrue(chooser.isEnabled())

    def test_the_window_is_not_blocked_while_it_looks(self):
        gate = threading.Event()
        with patch.object(_MODULE, 'available_cameras',
                          lambda: (gate.wait(5), _CAMERAS)[1]):
            chooser = QCameraChooser()
            QtWidgets.QApplication.processEvents()  # returns at once
            self.assertTrue(chooser._scanner.isRunning())
            gate.set()
            until(lambda: chooser._scanner is None)

    def test_scanned_is_emitted_when_the_list_is_complete(self):
        with scanning():
            chooser = QCameraChooser(scan=False)
            spy = record(chooser.scanned)
            chooser.refresh()
            until(lambda: len(spy) == 1)
        self.assertEqual(len(spy), 1)

    def test_a_chooser_made_without_a_scan_has_no_entries(self):
        chooser = QCameraChooser(scan=False)
        self.assertEqual(chooser.count(), 0)
        self.assertIsNone(chooser.camera())

    def test_refresh_looks_again(self):
        chooser = make_chooser()
        with scanning([('Noise', 0, 'Noise')]):
            chooser.refresh()
            until(lambda: chooser._scanner is None)
        self.assertEqual(chooser.count(), 1)

    def test_refresh_does_nothing_while_it_is_looking(self):
        gate = threading.Event()
        calls = []

        def slowly():
            calls.append(1)
            gate.wait(5)
            return _CAMERAS

        with patch.object(_MODULE, 'available_cameras', slowly):
            chooser = QCameraChooser()
            chooser.refresh()
            chooser.refresh()
            gate.set()
            until(lambda: chooser._scanner is None)
        self.assertEqual(len(calls), 1)


class TestChoice(unittest.TestCase):

    def test_camera_is_the_model_and_the_id(self):
        chooser = make_chooser()
        chooser.setCurrentIndex(1)
        self.assertEqual(chooser.camera(), ('OpenCV', 1))

    def test_choosing_emits_the_arguments_of_Camera(self):
        chooser = make_chooser()
        spy = record(chooser.cameraSelected)
        chooser.setCurrentIndex(1)
        chooser.activated.emit(1)
        self.assertEqual(spy, [('OpenCV', 1)])

    def test_nothing_is_emitted_while_it_looks(self):
        chooser = QCameraChooser(scan=False)
        chooser.addItem('Looking for cameras...')
        spy = record(chooser.cameraSelected)
        chooser.activated.emit(0)
        self.assertEqual(spy, [])

    def test_finding_cameras_does_not_choose_one(self):
        with scanning():
            chooser = QCameraChooser(scan=False)
            spy = record(chooser.cameraSelected)
            chooser.refresh()
            until(lambda: chooser._scanner is None)
        self.assertEqual(spy, [])


class TestStop(unittest.TestCase):

    def test_stop_ends_the_search_and_drops_its_result(self):
        gate = threading.Event()
        with patch.object(_MODULE, 'available_cameras',
                          lambda: (gate.wait(5), _CAMERAS)[1]):
            chooser = QCameraChooser()
            gate.set()
            chooser.stop()
        self.assertIsNone(chooser._scanner)
        QtWidgets.QApplication.processEvents()
        self.assertFalse(chooser.isEnabled())  # still 'looking': no result

    def test_stop_twice_is_safe(self):
        chooser = make_chooser()
        chooser.stop()
        chooser.stop()

    def test_a_result_that_arrives_after_stop_is_ignored(self):
        chooser = make_chooser(scan=False)
        chooser._setCameras(_CAMERAS)  # no scanner: it was stopped
        self.assertEqual(chooser.count(), 0)

    def test_deleting_the_chooser_during_a_search_is_safe(self):
        gate = threading.Event()
        with patch.object(_MODULE, 'available_cameras',
                          lambda: (gate.wait(5), _CAMERAS)[1]):
            chooser = QCameraChooser()
            scanner = chooser._scanner
            gate.set()
            chooser.deleteLater()
            QtCore.QCoreApplication.sendPostedEvents(
                None, QtCore.QEvent.Type.DeferredDelete)
        self.assertFalse(scanner.isRunning())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
